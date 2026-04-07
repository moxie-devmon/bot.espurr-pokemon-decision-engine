from __future__ import annotations

from dataclasses import replace

from app.domain.actions import MoveAction, SwitchAction
from app.domain.battle_state import BattleState, PokemonState, SideState
from app.engine.damage_engine import estimate_damage
from app.engine.field_engine import apply_field_modifiers, hazard_on_entry_context
from app.engine.response_engine import response_to_move_action
from app.engine.speed_engine import turn_order_context
from app.inference.models import OpponentResponse, OpponentWorld, ProjectionSummary


def _current_hp_value(pokemon: PokemonState) -> float:
    if pokemon.current_hp is not None:
        return max(0.0, float(pokemon.current_hp))
    return max(0.0, float(pokemon.hp or 100))


def _max_hp_value(pokemon: PokemonState) -> float:
    return max(1.0, float(pokemon.hp or 100))


def _apply_damage_to_pokemon(pokemon: PokemonState, damage: float) -> PokemonState:
    before = _current_hp_value(pokemon)
    after = max(0.0, before - max(0.0, float(damage)))
    return replace(pokemon, current_hp=after)


def _heal_pokemon_percent(pokemon: PokemonState, heal_percent: float) -> PokemonState:
    before = _current_hp_value(pokemon)
    max_hp = _max_hp_value(pokemon)
    heal_amount = max_hp * (heal_percent / 100.0)
    after = min(max_hp, before + heal_amount)
    return replace(pokemon, current_hp=after)


def _power_multiplier_from_item(item: str | None, category: str) -> float:
    if not item:
        return 1.0

    normalized = item.strip().lower()
    if normalized == "choice band" and category == "physical":
        return 1.5
    if normalized == "choice specs" and category == "special":
        return 1.5
    return 1.0


def _speed_multiplier_from_item(item: str | None) -> float:
    if not item:
        return 1.0
    normalized = item.strip().lower()
    if normalized == "choice scarf":
        return 1.5
    return 1.0


def _apply_focus_sash_if_applicable(
    defender_before: PokemonState,
    defender_after: PokemonState,
    defender_item: str | None,
) -> tuple[PokemonState, bool]:
    if not defender_item or defender_item.strip().lower() != "focus sash":
        return defender_after, False

    before_hp = _current_hp_value(defender_before)
    max_hp = _max_hp_value(defender_before)
    after_hp = _current_hp_value(defender_after)

    if before_hp >= max_hp and after_hp <= 0:
        return replace(defender_after, current_hp=1.0), True

    return defender_after, False


def _is_immune_by_ability(
    move_action: MoveAction,
    defender_world: OpponentWorld | None,
) -> bool:
    if defender_world is None or not defender_world.assumed_ability:
        return False

    ability = defender_world.assumed_ability.strip().lower()
    if ability == "levitate" and move_action.move_type.lower() == "ground":
        return True

    return False


def _prepare_my_attacker_against_world(
    attacker: PokemonState,
    my_action,
    world: OpponentWorld,
    notes: list[str],
) -> PokemonState:
    if not isinstance(my_action, MoveAction):
        return attacker

    if my_action.move_category != "physical":
        return attacker

    if not world.assumed_ability:
        return attacker

    if world.assumed_ability.strip().lower() != "intimidate":
        return attacker

    adjusted = replace(attacker, atk=float(attacker.atk or 100) * (2 / 3))
    notes.append(
        "First-pass Intimidate hook applied: inferred opposing ability reduces projected physical damage pressure."
    )
    return adjusted


def _prepare_opponent_attacker_from_world(
    attacker: PokemonState,
    move_action: MoveAction,
    world: OpponentWorld,
    notes: list[str],
) -> PokemonState:
    power_mult = _power_multiplier_from_item(world.assumed_item, move_action.move_category)

    if power_mult == 1.0:
        return attacker

    if move_action.move_category == "physical":
        adjusted = replace(attacker, atk=float(attacker.atk or 100) * power_mult)
    elif move_action.move_category == "special":
        adjusted = replace(attacker, spa=float(attacker.spa or 100) * power_mult)
    else:
        adjusted = attacker

    if adjusted is not attacker:
        notes.append(
            f"Opponent item hook applied: {world.assumed_item} boosts projected {move_action.move_category} damage."
        )
    return adjusted


def _prepare_opponent_speed_from_world(
    pokemon: PokemonState,
    world: OpponentWorld,
    notes: list[str],
) -> PokemonState:
    speed_mult = _speed_multiplier_from_item(world.assumed_item)
    if speed_mult == 1.0:
        return pokemon

    adjusted = replace(pokemon, spe=float(pokemon.spe or 100) * speed_mult)
    notes.append(f"Opponent item hook applied: {world.assumed_item} boosts projected Speed.")
    return adjusted


def _apply_move_damage(
    attacker: PokemonState,
    defender: PokemonState,
    move_action: MoveAction,
    state: BattleState,
    *,
    attacker_world: OpponentWorld | None = None,
    defender_world: OpponentWorld | None = None,
    notes: list[str] | None = None,
) -> tuple[PokemonState, dict, list[str]]:
    field_notes: list[str] = []
    hook_notes = notes if notes is not None else []

    if defender_world is not None and _is_immune_by_ability(move_action, defender_world):
        defender_after = replace(defender, current_hp=_current_hp_value(defender))
        field_notes.append(
            f"Projected immunity applied: {defender_world.assumed_ability} blocks {move_action.move_type}-type damage."
        )
        return defender_after, {
            "minDamage": 0.0,
            "maxDamage": 0.0,
            "minPercent": 0.0,
            "maxPercent": 0.0,
            "typeMultiplier": 0.0,
            "notes": ["Immunity applied by inferred ability hook."],
        }, field_notes

    prepared_attacker = attacker
    if attacker_world is not None:
        prepared_attacker = _prepare_opponent_attacker_from_world(
            attacker=prepared_attacker,
            move_action=move_action,
            world=attacker_world,
            notes=hook_notes,
        )

    move_ns = type(
        "EvalMove",
        (),
        {
            "name": move_action.move_name,
            "type": move_action.move_type,
            "category": move_action.move_category,
            "power": move_action.base_power,
            "priority": move_action.priority,
            "crit": False,
            "level": prepared_attacker.level,
        },
    )()

    dmg = estimate_damage(attacker=prepared_attacker, defender=defender, move=move_ns)
    dmg, extra_field_notes = apply_field_modifiers(
        dmg=dmg,
        move=move_ns,
        field=state.field,
        defender_hp=_max_hp_value(defender),
    )
    field_notes.extend(extra_field_notes)

    defender_after = _apply_damage_to_pokemon(defender, float(dmg["maxDamage"]))

    if defender_world is not None:
        defender_after, sash_triggered = _apply_focus_sash_if_applicable(
            defender_before=defender,
            defender_after=defender_after,
            defender_item=defender_world.assumed_item,
        )
        if sash_triggered:
            field_notes.append(
                f"Projected survival hook applied: {defender_world.assumed_item} lets the defender survive at 1 HP."
            )

    return defender_after, dmg, field_notes


def _find_switch_target(side: SideState, species: str) -> PokemonState | None:
    for pokemon in side.bench:
        if pokemon.species == species:
            return pokemon
    return None


def _apply_my_switch(
    state: BattleState,
    switch_action: SwitchAction,
) -> tuple[BattleState, PokemonState | None, list[str]]:
    notes: list[str] = []
    target = _find_switch_target(state.my_side, switch_action.target_species)
    if target is None:
        notes.append(f"Switch target {switch_action.target_species} was not found on bench.")
        return state, None, notes

    hazard_context, hazard_notes = hazard_on_entry_context(
        switch_target=target,
        side_conditions=state.my_side.side_conditions,
    )
    notes.extend(hazard_notes)

    total_entry_pct = float(hazard_context["totalEntryPercent"])
    entry_damage = (_max_hp_value(target) * total_entry_pct) / 100.0
    entered_target = _apply_damage_to_pokemon(target, entry_damage)

    remaining_bench = [p for p in state.my_side.bench if p.species != target.species]
    old_active = state.my_side.active
    remaining_bench.append(old_active)

    new_state = replace(
        state,
        my_side=replace(
            state.my_side,
            active=entered_target,
            bench=remaining_bench,
        ),
    )

    notes.append(
        f"Applied switch to {target.species or 'Unknown'} with {total_entry_pct:.1f}% estimated entry hazard damage."
    )
    return new_state, entered_target, notes


def _apply_opponent_switch(
    state: BattleState,
    target_species: str | None,
) -> tuple[BattleState, PokemonState | None, list[str]]:
    notes: list[str] = []
    if not target_species:
        notes.append("Opponent switch response did not specify a switch target.")
        return state, None, notes

    target = _find_switch_target(state.opponent_side, target_species)
    if target is None:
        notes.append(f"Opponent switch target {target_species} was not found on bench.")
        return state, None, notes

    remaining_bench = [p for p in state.opponent_side.bench if p.species != target.species]
    old_active = state.opponent_side.active
    remaining_bench.append(old_active)

    new_state = replace(
        state,
        opponent_side=replace(
            state.opponent_side,
            active=target,
            bench=remaining_bench,
        ),
    )
    notes.append(f"Opponent switch response applied to {target.species or 'Unknown'}.")
    return new_state, target, notes


def _apply_end_of_line_world_effects(
    opp_after: PokemonState,
    world: OpponentWorld,
    notes: list[str],
) -> PokemonState:
    if not world.assumed_item:
        return opp_after

    if world.assumed_item.strip().lower() == "leftovers" and _current_hp_value(opp_after) > 0:
        healed = _heal_pokemon_percent(opp_after, 6.25)
        if _current_hp_value(healed) > _current_hp_value(opp_after):
            notes.append("Projected end-of-line recovery applied: inferred Leftovers restored HP.")
        return healed

    return opp_after


def project_action_against_response(
    state: BattleState,
    my_action,
    response: OpponentResponse,
    world: OpponentWorld,
) -> ProjectionSummary:
    my_before = _current_hp_value(state.my_side.active)
    opp_before = _current_hp_value(state.opponent_side.active)
    notes: list[str] = []

    my_active = state.my_side.active
    opp_active = state.opponent_side.active

    my_active_species_after = my_active.species
    opp_active_species_after = opp_active.species
    my_forced_switch = False
    opp_forced_switch = False
    opponent_switched = False
    revealed_response_move = response.move_name if response.kind == "move" else None

    if isinstance(my_action, SwitchAction):
        switched_state, switched_target, switch_notes = _apply_my_switch(state, my_action)
        notes.extend(switch_notes)

        if switched_target is None:
            return ProjectionSummary(
                my_hp_before=my_before,
                my_hp_after=my_before,
                opp_hp_before=opp_before,
                opp_hp_after=opp_before,
                my_fainted=False,
                opp_fainted=False,
                order_context="switch_failed",
                notes=notes,
                my_active_species_after=my_active.species,
                opp_active_species_after=opp_active.species,
                my_forced_switch=False,
                opp_forced_switch=False,
                opponent_switched=False,
                revealed_response_move=revealed_response_move,
            )

        my_active_species_after = switched_target.species

        response_move = response_to_move_action(response)
        if response_move is None:
            notes.extend(response.notes)

            opponent_switch_state, new_opp_active, opp_switch_notes = _apply_opponent_switch(
                switched_state,
                response.switch_target_species,
            )
            notes.extend(opp_switch_notes)
            if new_opp_active is not None:
                opponent_switched = True
                opp_active_species_after = new_opp_active.species

            return ProjectionSummary(
                my_hp_before=my_before,
                my_hp_after=_current_hp_value(switched_target),
                opp_hp_before=opp_before,
                opp_hp_after=_current_hp_value(opponent_switch_state.opponent_side.active),
                my_fainted=_current_hp_value(switched_target) <= 0,
                opp_fainted=_current_hp_value(opponent_switch_state.opponent_side.active) <= 0,
                order_context="switch_then_nonmove_response",
                notes=notes,
                my_active_species_after=my_active_species_after,
                opp_active_species_after=opp_active_species_after,
                my_forced_switch=_current_hp_value(switched_target) <= 0,
                opp_forced_switch=False,
                opponent_switched=opponent_switched,
                revealed_response_move=revealed_response_move,
            )

        post_switch_target, dmg, field_notes = _apply_move_damage(
            attacker=switched_state.opponent_side.active,
            defender=switched_state.my_side.active,
            move_action=response_move,
            state=switched_state,
            attacker_world=world,
            defender_world=None,
            notes=notes,
        )
        notes.extend(response.notes)
        notes.extend(field_notes)
        notes.append(
            f"Opponent response after switch estimated {dmg['minPercent']:.1f}–{dmg['maxPercent']:.1f}% into the switch target."
        )

        opp_after_final = _apply_end_of_line_world_effects(switched_state.opponent_side.active, world, notes)

        if _current_hp_value(post_switch_target) <= 0:
            my_forced_switch = True

        return ProjectionSummary(
            my_hp_before=my_before,
            my_hp_after=_current_hp_value(post_switch_target),
            opp_hp_before=opp_before,
            opp_hp_after=_current_hp_value(opp_after_final),
            my_fainted=_current_hp_value(post_switch_target) <= 0,
            opp_fainted=_current_hp_value(opp_after_final) <= 0,
            order_context="switch_then_response",
            notes=notes,
            my_active_species_after=my_active_species_after,
            opp_active_species_after=opp_active_species_after,
            my_forced_switch=my_forced_switch,
            opp_forced_switch=False,
            opponent_switched=False,
            revealed_response_move=revealed_response_move,
        )

    response_move = response_to_move_action(response)
    if response_move is None:
        prepared_my_active = _prepare_my_attacker_against_world(
            attacker=my_active,
            my_action=my_action,
            world=world,
            notes=notes,
        )

        opp_after, my_dmg, my_field_notes = _apply_move_damage(
            attacker=prepared_my_active,
            defender=opp_active,
            move_action=my_action,
            state=state,
            attacker_world=None,
            defender_world=world,
            notes=notes,
        )
        notes.extend(my_field_notes)
        notes.extend(response.notes)
        notes.append("Opponent switch response is currently approximated after my attack lands on the current active slot.")

        switched_state, new_opp_active, opp_switch_notes = _apply_opponent_switch(
            replace(state, opponent_side=replace(state.opponent_side, active=opp_after)),
            response.switch_target_species,
        )
        notes.extend(opp_switch_notes)

        if new_opp_active is not None and _current_hp_value(opp_after) > 0:
            opponent_switched = True
            opp_active_species_after = new_opp_active.species
            opp_after_final = new_opp_active
        else:
            opp_after_final = _apply_end_of_line_world_effects(opp_after, world, notes)
            opp_active_species_after = opp_after_final.species

        if _current_hp_value(opp_after_final) <= 0:
            opp_forced_switch = True

        return ProjectionSummary(
            my_hp_before=my_before,
            my_hp_after=my_before,
            opp_hp_before=opp_before,
            opp_hp_after=_current_hp_value(opp_after_final),
            my_fainted=False,
            opp_fainted=_current_hp_value(opp_after_final) <= 0,
            order_context="attacker_first_vs_switch_response",
            notes=notes,
            my_active_species_after=my_active_species_after,
            opp_active_species_after=opp_active_species_after,
            my_forced_switch=False,
            opp_forced_switch=opp_forced_switch,
            opponent_switched=opponent_switched,
            revealed_response_move=None,
        )

    prepared_my_active = _prepare_my_attacker_against_world(
        attacker=my_active,
        my_action=my_action,
        world=world,
        notes=notes,
    )
    prepared_opp_active_for_order = _prepare_opponent_speed_from_world(
        pokemon=opp_active,
        world=world,
        notes=notes,
    )

    order_context, order_notes = turn_order_context(
        attacking_pokemon=prepared_my_active,
        defending_pokemon=prepared_opp_active_for_order,
        move=type(
            "EvalMoveOrder",
            (),
            {
                "priority": my_action.priority,
            },
        )(),
    )
    notes.extend(order_notes)
    notes.extend(response.notes)

    my_after = my_active
    opp_after = opp_active

    if order_context == "attacker_first":
        opp_after, my_dmg, my_field_notes = _apply_move_damage(
            attacker=prepared_my_active,
            defender=opp_after,
            move_action=my_action,
            state=state,
            attacker_world=None,
            defender_world=world,
            notes=notes,
        )
        notes.extend(my_field_notes)
        notes.append(
            f"My action estimated {my_dmg['minPercent']:.1f}–{my_dmg['maxPercent']:.1f}% into the opposing active."
        )

        if _current_hp_value(opp_after) > 0:
            my_after, opp_dmg, opp_field_notes = _apply_move_damage(
                attacker=opp_active,
                defender=my_after,
                move_action=response_move,
                state=state,
                attacker_world=world,
                defender_world=None,
                notes=notes,
            )
            notes.extend(opp_field_notes)
            notes.append(
                f"Opponent response estimated {opp_dmg['minPercent']:.1f}–{opp_dmg['maxPercent']:.1f}% into my active."
            )
        else:
            notes.append("Opponent active is projected to faint before responding.")

    elif order_context == "attacker_second":
        my_after, opp_dmg, opp_field_notes = _apply_move_damage(
            attacker=opp_active,
            defender=my_after,
            move_action=response_move,
            state=state,
            attacker_world=world,
            defender_world=None,
            notes=notes,
        )
        notes.extend(opp_field_notes)
        notes.append(
            f"Opponent response estimated {opp_dmg['minPercent']:.1f}–{opp_dmg['maxPercent']:.1f}% into my active before my move."
        )

        if _current_hp_value(my_after) > 0:
            opp_after, my_dmg, my_field_notes = _apply_move_damage(
                attacker=prepared_my_active,
                defender=opp_after,
                move_action=my_action,
                state=state,
                attacker_world=None,
                defender_world=world,
                notes=notes,
            )
            notes.extend(my_field_notes)
            notes.append(
                f"My action estimated {my_dmg['minPercent']:.1f}–{my_dmg['maxPercent']:.1f}% into the opposing active."
            )
        else:
            notes.append("My active is projected to faint before acting.")

    else:
        opp_after, my_dmg, my_field_notes = _apply_move_damage(
            attacker=prepared_my_active,
            defender=opp_after,
            move_action=my_action,
            state=state,
            attacker_world=None,
            defender_world=world,
            notes=notes,
        )
        my_after, opp_dmg, opp_field_notes = _apply_move_damage(
            attacker=opp_active,
            defender=my_after,
            move_action=response_move,
            state=state,
            attacker_world=world,
            defender_world=None,
            notes=notes,
        )
        notes.extend(my_field_notes)
        notes.extend(opp_field_notes)
        notes.append("Speed tie / uncertain order approximated as both actions resolving.")

    opp_after = _apply_end_of_line_world_effects(opp_after, world, notes)

    if _current_hp_value(my_after) <= 0:
        my_forced_switch = True
    if _current_hp_value(opp_after) <= 0:
        opp_forced_switch = True

    my_active_species_after = my_after.species
    opp_active_species_after = opp_after.species

    return ProjectionSummary(
        my_hp_before=my_before,
        my_hp_after=_current_hp_value(my_after),
        opp_hp_before=opp_before,
        opp_hp_after=_current_hp_value(opp_after),
        my_fainted=_current_hp_value(my_after) <= 0,
        opp_fainted=_current_hp_value(opp_after) <= 0,
        order_context=order_context,
        notes=notes,
        my_active_species_after=my_active_species_after,
        opp_active_species_after=opp_active_species_after,
        my_forced_switch=my_forced_switch,
        opp_forced_switch=opp_forced_switch,
        opponent_switched=opponent_switched,
        revealed_response_move=revealed_response_move,
    )