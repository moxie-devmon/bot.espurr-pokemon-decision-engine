from __future__ import annotations

from typing import List, Tuple

from app.domain.actions import MoveAction, SwitchAction
from app.domain.battle_state import BattleState, PokemonState
from app.domain.move_tags import (
    is_choice_item,
    is_disruption_move,
    is_hazard_move,
    is_pivot_move,
    is_priority_signal_move,
    is_recovery_move,
    is_setup_move,
    normalized_name,
)
from app.engine.field_engine import hazard_on_entry_context
from app.engine.type_engine import combined_multiplier
from app.inference.models import OpponentResponse, OpponentWorld
from app.providers.move_provider import build_move_action_from_name


def best_stab_type_into_target(
    attacking_pokemon: PokemonState,
    defending_pokemon: PokemonState,
) -> Tuple[str | None, float]:
    best_type = None
    best_mult = -1.0

    for stab_type in attacking_pokemon.types:
        mult, _ = combined_multiplier(stab_type, defending_pokemon.types)
        if mult > best_mult:
            best_mult = mult
            best_type = stab_type

    if best_type is None:
        return None, 1.0

    return best_type, best_mult


def _default_offense_category(pokemon: PokemonState) -> str:
    atk = float(pokemon.atk or 100)
    spa = float(pokemon.spa or 100)
    return "physical" if atk >= spa else "special"


def _power_from_multiplier(mult: float) -> int:
    if mult >= 4.0:
        return 110
    if mult >= 2.0:
        return 100
    if mult >= 1.0:
        return 85
    return 70


def _proxy_response_from_world(
    opposing_active: PokemonState,
    my_active: PokemonState,
    label: str,
    weight: float,
    assumed_move_name: str | None = None,
) -> OpponentResponse:
    best_stab_type, best_mult = best_stab_type_into_target(opposing_active, my_active)

    if best_stab_type is None:
        best_stab_type = opposing_active.types[0] if opposing_active.types else "Normal"
        best_mult = 1.0

    category = _default_offense_category(opposing_active)
    power = _power_from_multiplier(best_mult)

    return OpponentResponse(
        kind="move",
        label=label,
        weight=weight,
        move_name=assumed_move_name or f"Proxy {best_stab_type} STAB",
        move_type=best_stab_type,
        move_category=category,
        base_power=power,
        priority=0,
        notes=[
            f"Fallback response uses a proxy based on the opponent's likely STAB profile into {my_active.species or 'target'}.",
        ],
    )


def _estimate_response_weight(
    move_action: MoveAction,
    opposing_active: PokemonState,
    my_active: PokemonState,
    *,
    world: OpponentWorld,
    my_action,
    is_revealed: bool,
) -> float:
    move_name = move_action.move_name
    category = normalized_name(move_action.move_category)
    item_name = normalized_name(world.assumed_item)
    tera_type = world.assumed_tera_type

    weight = 1.0

    if is_revealed:
        weight += 0.85
    else:
        weight += 0.15

    if move_action.move_type in opposing_active.types:
        weight += 0.60

    type_mult, _ = combined_multiplier(move_action.move_type, my_active.types)
    if type_mult >= 4.0:
        weight += 1.30
    elif type_mult >= 2.0:
        weight += 0.95
    elif type_mult == 0.0:
        weight -= 0.95
    elif 0.0 < type_mult < 1.0:
        weight -= 0.30

    if move_action.base_power >= 120:
        weight += 0.40
    elif move_action.base_power >= 90:
        weight += 0.25
    elif move_action.base_power == 0 and category == "status":
        weight -= 0.10

    if move_action.priority > 0 or is_priority_signal_move(move_name):
        weight += 0.35

    if is_setup_move(move_name):
        if isinstance(my_action, SwitchAction):
            weight += 0.55
        else:
            weight += 0.20

    if is_recovery_move(move_name):
        opp_hp = float(
            opposing_active.current_hp if opposing_active.current_hp is not None else opposing_active.hp or 100
        )
        opp_max_hp = max(1.0, float(opposing_active.hp or 100))
        opp_hp_pct = (opp_hp / opp_max_hp) * 100.0

        if opp_hp_pct <= 45.0:
            weight += 0.55
        elif opp_hp_pct <= 70.0:
            weight += 0.20
        else:
            weight -= 0.10

    if is_pivot_move(move_name):
        weight += 0.25

    if is_hazard_move(move_name):
        if isinstance(my_action, SwitchAction):
            weight += 0.30
        else:
            weight -= 0.05

    if is_disruption_move(move_name):
        weight += 0.20
        if isinstance(my_action, SwitchAction):
            weight -= 0.10

    if item_name == "choice scarf":
        if move_action.base_power >= 80 or move_action.priority > 0:
            weight += 0.20
        if is_setup_move(move_name) or is_recovery_move(move_name):
            weight -= 0.25

    if item_name == "choice band" and category == "physical":
        weight += 0.25
    if item_name == "choice specs" and category == "special":
        weight += 0.25

    if item_name == "leftovers":
        if is_recovery_move(move_name) or is_setup_move(move_name):
            weight += 0.12

    if normalized_name(move_name) == "trick":
        if is_choice_item(item_name):
            weight += 0.70
        else:
            weight -= 0.30

    if normalized_name(move_name) == "tera blast":
        if tera_type:
            weight += 0.45
            if tera_type == move_action.move_type:
                weight += 0.20
        else:
            weight -= 0.35

    if tera_type and move_action.move_type == tera_type:
        weight += 0.10

    return max(0.05, weight)


def _build_hydrated_move_response(
    move_action: MoveAction,
    weight: float,
    *,
    world: OpponentWorld,
    is_revealed: bool,
    move_source: str,
) -> OpponentResponse:
    notes = [
        f"Opponent response is hydrated from move metadata for {move_action.move_name}.",
        f"Move source: {move_source}.",
    ]
    if is_revealed:
        notes.append("This move is already revealed, so its response weight is boosted.")
    else:
        notes.append("This move is inferred from the current candidate world.")

    if world.assumed_item:
        notes.append(f"Response weighting considered assumed item: {world.assumed_item}.")
    if world.assumed_tera_type and normalized_name(move_action.move_name) == "tera blast":
        notes.append(f"Response weighting considered assumed tera type: {world.assumed_tera_type}.")

    return OpponentResponse(
        kind="move",
        label=f"move::{move_action.move_name}",
        weight=weight,
        move_name=move_action.move_name,
        move_type=move_action.move_type,
        move_category=move_action.move_category,
        base_power=move_action.base_power,
        priority=move_action.priority,
        notes=notes,
    )


def _dedupe_move_names(world: OpponentWorld) -> list[tuple[str, bool]]:
    ordered: list[tuple[str, bool]] = []
    seen: set[str] = set()

    for move_name in world.known_moves:
        key = normalized_name(move_name)
        if key and key not in seen:
            seen.add(key)
            ordered.append((move_name, True))

    for move_name in world.assumed_moves:
        key = normalized_name(move_name)
        if key and key not in seen:
            seen.add(key)
            ordered.append((move_name, False))

    return ordered


def _switch_defensive_score(
    switch_target: PokemonState,
    move_type: str | None,
) -> float:
    if not move_type:
        return 1.0
    mult, _ = combined_multiplier(move_type, switch_target.types)
    if mult == 0.0:
        return 2.4
    if 0.0 < mult < 1.0:
        return 1.7
    if mult == 1.0:
        return 1.0
    if mult >= 4.0:
        return 0.15
    return 0.45


def _switch_offensive_score(
    switch_target: PokemonState,
    my_active: PokemonState,
) -> float:
    best_type, best_mult = best_stab_type_into_target(switch_target, my_active)
    if best_type is None:
        return 1.0
    if best_mult >= 4.0:
        return 2.0
    if best_mult >= 2.0:
        return 1.55
    if best_mult >= 1.0:
        return 1.10
    if best_mult == 0.0:
        return 0.45
    return 0.75


def _entry_hazard_penalty(
    switch_target: PokemonState,
    side_conditions,
) -> tuple[float, list[str]]:
    hazard_context, notes = hazard_on_entry_context(
        switch_target=switch_target,
        side_conditions=side_conditions,
    )
    total_entry_pct = float(hazard_context["totalEntryPercent"])
    if total_entry_pct <= 0:
        return 1.0, notes
    if total_entry_pct >= 40.0:
        return 0.35, notes
    if total_entry_pct >= 25.0:
        return 0.55, notes
    if total_entry_pct >= 12.5:
        return 0.75, notes
    return 0.90, notes


def _build_switch_responses(
    state: BattleState,
    world: OpponentWorld,
    my_action,
    *,
    max_switches: int = 2,
) -> list[OpponentResponse]:
    if not state.opponent_side.bench:
        return []

    responses: list[tuple[OpponentResponse, float]] = []
    threatening_move_type: str | None = None

    if isinstance(my_action, MoveAction):
        threatening_move_type = my_action.move_type

    for bench_target in state.opponent_side.bench:
        defensive_score = _switch_defensive_score(bench_target, threatening_move_type)
        offensive_score = _switch_offensive_score(bench_target, state.my_side.active)
        hazard_penalty, hazard_notes = _entry_hazard_penalty(
            bench_target,
            state.opponent_side.side_conditions,
        )

        raw_weight = defensive_score * offensive_score * hazard_penalty

        notes = [
            "Opponent switch response is ranked from bench candidates rather than using bench order.",
            f"Defensive matchup score={defensive_score:.2f}.",
            f"Offensive matchup score={offensive_score:.2f}.",
            f"Entry hazard penalty multiplier={hazard_penalty:.2f}.",
        ]
        notes.extend(hazard_notes[:2])

        responses.append(
            (
                OpponentResponse(
                    kind="switch",
                    label=f"switch::{bench_target.species or 'Unknown'}",
                    weight=raw_weight,
                    switch_target_species=bench_target.species,
                    notes=notes,
                ),
                raw_weight,
            )
        )

    responses.sort(key=lambda pair: pair[1], reverse=True)
    return [response for response, _ in responses[:max_switches]]


def _raw_move_responses(
    state: BattleState,
    world: OpponentWorld,
    my_action,
) -> list[OpponentResponse]:
    responses: list[OpponentResponse] = []

    opposing_active = state.opponent_side.active
    my_active = state.my_side.active

    hydrated_candidates: list[tuple[MoveAction, float, bool]] = []
    move_name_pairs = _dedupe_move_names(world)

    for move_name, is_revealed in move_name_pairs[:6]:
        move_action = build_move_action_from_name(move_name)
        if move_action is None:
            continue

        response_weight = _estimate_response_weight(
            move_action=move_action,
            opposing_active=opposing_active,
            my_active=my_active,
            world=world,
            my_action=my_action,
            is_revealed=is_revealed,
        )
        hydrated_candidates.append((move_action, response_weight, is_revealed))

    if hydrated_candidates:
        for move_action, raw_weight, is_revealed in hydrated_candidates:
            responses.append(
                _build_hydrated_move_response(
                    move_action=move_action,
                    weight=raw_weight,
                    world=world,
                    is_revealed=is_revealed,
                    move_source=world.candidate.source,
                )
            )
        return responses

    return [
        _proxy_response_from_world(
            opposing_active=opposing_active,
            my_active=my_active,
            label="move::proxy-stab",
            weight=1.0,
        )
    ]


def _normalize_responses(
    responses: list[OpponentResponse],
) -> list[OpponentResponse]:
    total = sum(max(0.0, response.weight) for response in responses) or 1.0
    for response in responses:
        response.weight = max(0.0, response.weight) / total
    return responses


def generate_opponent_responses(
    state: BattleState,
    world: OpponentWorld,
    my_action,
) -> List[OpponentResponse]:
    """
    Generate plausible opponent replies under one inferred world.

    This version:
    - hydrates multiple move responses from known + assumed moves
    - ranks multiple switch candidates instead of using bench order
    - uses item / tera / revealed-move confidence to shape raw response weights
    - normalizes only after all candidates are generated
    """
    move_responses = _raw_move_responses(state=state, world=world, my_action=my_action)
    switch_responses = _build_switch_responses(
        state=state,
        world=world,
        my_action=my_action,
        max_switches=2,
    )

    responses = move_responses + switch_responses
    if not responses:
        return []

    responses.sort(key=lambda response: response.weight, reverse=True)
    return _normalize_responses(responses)


def response_to_move_action(response: OpponentResponse) -> MoveAction | None:
    if response.kind != "move":
        return None

    return MoveAction(
        move_name=response.move_name or response.label,
        move_type=response.move_type or "Normal",
        move_category=response.move_category or "physical",
        base_power=response.base_power,
        priority=response.priority,
    )