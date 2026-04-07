from __future__ import annotations

from dataclasses import replace
from typing import List, Optional, Tuple

from app.domain.actions import MoveAction, SwitchAction
from app.domain.battle_state import BattleState
from app.engine.projection_engine import project_action_against_response
from app.engine.response_engine import generate_opponent_responses
from app.engine.switch_engine import score_switch
from app.engine.type_engine import combined_multiplier
from app.inference.belief_updater import (
    apply_branch_evidence,
    inference_to_worlds,
    worlds_to_inference,
)
from app.inference.models import OpponentResponse, OpponentWorld, ProjectionSummary
from app.providers.move_provider import build_move_action_from_name


def _top_responses(
    responses: List[OpponentResponse],
    limit: int = 2,
) -> List[OpponentResponse]:
    ordered = sorted(responses, key=lambda response: response.weight, reverse=True)
    return ordered[:limit]


def build_followup_state_from_projection(
    state: BattleState,
    projection: ProjectionSummary,
) -> BattleState:
    my_side = state.my_side
    opp_side = state.opponent_side

    my_active = replace(
        my_side.active,
        current_hp=max(0.0, float(projection.my_hp_after)),
    )
    opp_active = replace(
        opp_side.active,
        current_hp=max(0.0, float(projection.opp_hp_after)),
    )

    my_bench = list(my_side.bench)
    opp_bench = list(opp_side.bench)

    if projection.opponent_switched and projection.opp_active_species_after:
        switch_target = next(
            (pokemon for pokemon in opp_bench if pokemon.species == projection.opp_active_species_after),
            None,
        )
        if switch_target is not None:
            opp_bench = [pokemon for pokemon in opp_bench if pokemon.species != switch_target.species]
            previous_opp_active = opp_active
            opp_active = replace(
                switch_target,
                current_hp=max(
                    0.0,
                    float(
                        switch_target.current_hp
                        if switch_target.current_hp is not None
                        else switch_target.hp or 100
                    ),
                ),
            )
            opp_bench.append(previous_opp_active)

    if projection.my_forced_switch and my_bench:
        replacement = my_bench[0]
        my_bench = my_bench[1:]
        my_active = replace(
            replacement,
            current_hp=max(
                0.0,
                float(
                    replacement.current_hp
                    if replacement.current_hp is not None
                    else replacement.hp or 100
                ),
            ),
        )

    if projection.opp_forced_switch and opp_bench:
        replacement = opp_bench[0]
        opp_bench = opp_bench[1:]
        opp_active = replace(
            replacement,
            current_hp=max(
                0.0,
                float(
                    replacement.current_hp
                    if replacement.current_hp is not None
                    else replacement.hp or 100
                ),
            ),
        )

    if projection.revealed_response_move:
        revealed_moves = list(opp_active.revealed_moves)
        if projection.revealed_response_move not in revealed_moves:
            revealed_moves.append(projection.revealed_response_move)
            opp_active = replace(opp_active, revealed_moves=revealed_moves)

    return replace(
        state,
        my_side=replace(
            my_side,
            active=my_active,
            bench=my_bench,
        ),
        opponent_side=replace(
            opp_side,
            active=opp_active,
            bench=opp_bench,
        ),
    )


def _score_followup_move_simple(
    followup_state: BattleState,
    move,
) -> float:
    my_active = followup_state.my_side.active
    opp_active = followup_state.opponent_side.active

    opp_hp = float(
        opp_active.current_hp if opp_active.current_hp is not None else opp_active.hp or 100
    )
    opp_max_hp = max(1.0, float(opp_active.hp or 100))
    opp_hp_pct = (opp_hp / opp_max_hp) * 100.0

    score = 0.0
    score += float(getattr(move, "power", 0) or 0) * 0.15

    move_type = getattr(move, "type", None)
    if move_type and move_type in my_active.types:
        score += 6.0

    if opp_hp_pct <= 25.0:
        score += 10.0
    elif opp_hp_pct <= 50.0:
        score += 5.0

    if (getattr(move, "priority", 0) or 0) > 0:
        score += 2.0

    category = str(getattr(move, "category", "") or "").lower()
    if category == "status":
        score -= 4.0

    return score


def _world_to_inference(world: OpponentWorld):
    return worlds_to_inference([world])


def _extract_item_evidence_from_projection(
    projection: ProjectionSummary,
    world: OpponentWorld,
) -> Optional[str]:
    if not world.assumed_item:
        return None

    evidence_items = {
        "choice scarf",
        "choice band",
        "choice specs",
        "focus sash",
        "leftovers",
    }
    normalized_item = world.assumed_item.strip().lower()
    if normalized_item not in evidence_items:
        return None

    joined_notes = " ".join(projection.notes).lower()
    if normalized_item in joined_notes:
        return world.assumed_item

    return None


def _extract_ability_evidence_from_projection(
    projection: ProjectionSummary,
    world: OpponentWorld,
) -> Optional[str]:
    if not world.assumed_ability:
        return None

    evidence_abilities = {
        "levitate",
        "intimidate",
    }
    normalized_ability = world.assumed_ability.strip().lower()
    if normalized_ability not in evidence_abilities:
        return None

    joined_notes = " ".join(projection.notes).lower()
    if normalized_ability in joined_notes:
        return world.assumed_ability

    return None


def reweight_world_distribution_from_branch_evidence(
    worlds: list[OpponentWorld],
    projection: ProjectionSummary,
    source_world: OpponentWorld,
) -> Tuple[list[OpponentWorld], List[str]]:
    notes: List[str] = []

    inference = worlds_to_inference(worlds)

    revealed_move = projection.revealed_response_move
    item_evidence = _extract_item_evidence_from_projection(projection, source_world)
    ability_evidence = _extract_ability_evidence_from_projection(projection, source_world)

    updated_inference = apply_branch_evidence(
        inference,
        revealed_move=revealed_move,
        item_evidence=item_evidence,
        ability_evidence=ability_evidence,
    )

    updated_worlds = inference_to_worlds(updated_inference, worlds)

    if revealed_move:
        notes.append(f"Cross-world branch reweighting applied revealed move evidence: {revealed_move}.")
    if item_evidence:
        notes.append(f"Cross-world branch reweighting applied item evidence: {item_evidence}.")
    if ability_evidence:
        notes.append(f"Cross-world branch reweighting applied ability evidence: {ability_evidence}.")

    if updated_worlds:
        ranked = sorted(updated_worlds, key=lambda world: world.weight, reverse=True)
        top_world = ranked[0]
        notes.append(
            f"Updated branch distribution now favors '{top_world.candidate.label}' at weight {top_world.weight:.2f}."
        )

    return updated_worlds, notes + updated_inference.notes[-3:]


def _estimate_distribution_threat_adjustment(
    followup_state: BattleState,
    updated_worlds: list[OpponentWorld],
) -> Tuple[float, List[str]]:
    notes: List[str] = []

    if not updated_worlds:
        return 0.0, ["No updated worlds available for continuation threat adjustment."]

    my_active = followup_state.my_side.active
    total_pressure = 0.0

    for world in updated_worlds:
        candidate_move_names: list[str] = []
        for move_name in world.known_moves:
            if move_name not in candidate_move_names:
                candidate_move_names.append(move_name)
        for move_name in world.assumed_moves:
            if move_name not in candidate_move_names:
                candidate_move_names.append(move_name)

        worst_pressure = 0.0
        worst_label = None

        for move_name in candidate_move_names[:4]:
            move_action = build_move_action_from_name(move_name)
            if move_action is None:
                continue

            type_mult, _ = combined_multiplier(move_action.move_type, my_active.types)
            pressure = 0.0
            pressure += move_action.base_power * 0.08

            if type_mult >= 4.0:
                pressure += 12.0
            elif type_mult >= 2.0:
                pressure += 8.0
            elif type_mult == 0.0:
                pressure -= 6.0
            elif 0.0 < type_mult < 1.0:
                pressure -= 2.0

            if move_action.priority > 0:
                pressure += 2.5

            if move_name in world.known_moves:
                pressure += 2.0

            if pressure > worst_pressure:
                worst_pressure = pressure
                worst_label = move_name

        if world.assumed_item and world.assumed_item.strip().lower() == "choice scarf":
            worst_pressure += 2.0
        if world.assumed_item and world.assumed_item.strip().lower() == "leftovers":
            worst_pressure += 1.0

        total_pressure += world.weight * worst_pressure

        if worst_label is not None:
            notes.append(
                f"World '{world.candidate.label}' contributes threat via '{worst_label}' "
                f"with weighted pressure {world.weight * worst_pressure:.1f}."
            )

    return -total_pressure * 0.25, notes[:3]


def _candidate_next_actions(
    followup_state: BattleState,
) -> List[tuple[object, float, str]]:
    """
    Return candidate next actions with cheap heuristic pre-scores.
    """
    candidates: List[tuple[object, float, str]] = []

    for move in followup_state.moves:
        score = _score_followup_move_simple(followup_state, move)
        move_name = (getattr(move, "name", None) or "Unknown move").strip()
        move_action = MoveAction(
            move_name=move_name,
            move_type=getattr(move, "type", "Normal"),
            move_category=str(getattr(move, "category", "physical")).lower(),
            base_power=int(getattr(move, "power", 0) or 0),
            priority=int(getattr(move, "priority", 0) or 0),
        )
        candidates.append((move_action, score, move_name))

    for switch_target in followup_state.my_side.bench:
        switch_score, _ = score_switch(
            switch_target=switch_target,
            opposing_active=followup_state.opponent_side.active,
            entry_side_conditions=followup_state.my_side.side_conditions,
        )
        switch_action = SwitchAction(target_species=switch_target.species or "Unknown switch")
        candidates.append((switch_action, switch_score, switch_target.species or "Unknown switch"))

    candidates.sort(key=lambda item: item[1], reverse=True)
    return candidates


def _score_second_ply_projection(
    projection: ProjectionSummary,
    my_next_action,
) -> float:
    """
    Cheap second-ply projected-line scorer.
    """
    score = 0.0
    score += projection.opp_damage_taken_pct_current * 0.9
    score -= projection.my_damage_taken_pct_current * 0.8

    if projection.opp_fainted:
        score += 30.0
    if projection.my_fainted:
        score -= 35.0

    if isinstance(my_next_action, MoveAction):
        if projection.order_context == "attacker_first" and not projection.my_fainted:
            score += 3.0
        elif projection.order_context == "attacker_second":
            score -= 3.0
        elif projection.order_context == "speed_tie":
            score -= 1.0
    else:
        if projection.my_damage_taken_pct_current <= 25.0:
            score += 4.0
        elif projection.my_damage_taken_pct_current >= 75.0:
            score -= 8.0

    return score


def _evaluate_second_ply_against_updated_worlds(
    followup_state: BattleState,
    my_next_action,
    updated_worlds: list[OpponentWorld],
    response_limit: int = 2,
) -> Tuple[float, List[str]]:
    notes: List[str] = []

    if not updated_worlds:
        return 0.0, ["No updated worlds were available for second-ply response generation."]

    expected_total = 0.0

    for world in updated_worlds:
        responses = generate_opponent_responses(
            state=followup_state,
            world=world,
            my_action=my_next_action,
        )
        selected = _top_responses(responses, limit=response_limit)

        if not selected:
            continue

        total_selected_weight = sum(response.weight for response in selected) or 1.0
        world_expected = 0.0

        for response in selected:
            projection = project_action_against_response(
                state=followup_state,
                my_action=my_next_action,
                response=response,
                world=world,
            )
            branch_score = _score_second_ply_projection(projection, my_next_action)
            normalized_weight = response.weight / total_selected_weight
            world_expected += normalized_weight * branch_score

        expected_total += world.weight * world_expected
        notes.append(
            f"Second-ply updated world '{world.candidate.label}' contributes expected continuation {world.weight * world_expected:.1f}."
        )

    return expected_total, notes[:3]


def estimate_best_next_action_value(
    followup_state: BattleState,
    updated_worlds: list[OpponentWorld] | None = None,
) -> Tuple[float, List[str]]:
    notes: List[str] = []

    my_active_hp = float(
        followup_state.my_side.active.current_hp
        if followup_state.my_side.active.current_hp is not None
        else followup_state.my_side.active.hp or 100
    )
    opp_active_hp = float(
        followup_state.opponent_side.active.current_hp
        if followup_state.opponent_side.active.current_hp is not None
        else followup_state.opponent_side.active.hp or 100
    )

    if my_active_hp <= 0:
        notes.append("No continuation value: my active Pokémon is projected to faint.")
        return -25.0, notes

    if opp_active_hp <= 0:
        notes.append("Strong continuation value: opponent active is already projected to faint.")
        return 20.0, notes

    candidates = _candidate_next_actions(followup_state)
    if not candidates:
        return 0.0, ["No next-turn actions were available in followup state."]

    best_action, base_value, best_label = candidates[0]
    notes.append(f"Best next-step action candidate is '{best_label}' with base value {base_value:.1f}.")

    total_value = base_value

    if updated_worlds is not None:
        second_ply_value, second_ply_notes = _evaluate_second_ply_against_updated_worlds(
            followup_state=followup_state,
            my_next_action=best_action,
            updated_worlds=updated_worlds,
            response_limit=2,
        )
        total_value += second_ply_value
        notes.extend(second_ply_notes)

        threat_adjustment, threat_notes = _estimate_distribution_threat_adjustment(
            followup_state=followup_state,
            updated_worlds=updated_worlds,
        )
        total_value += threat_adjustment
        notes.extend(threat_notes)
        notes.append(
            f"Cross-world reweighted threat adjustment adds {threat_adjustment:.1f}; second-ply continuation adds {second_ply_value:.1f}."
        )

    return total_value, notes


def estimate_lookahead_bonus(
    state: BattleState,
    my_action,
    world: OpponentWorld,
    *,
    all_worlds: list[OpponentWorld] | None = None,
    response_limit: int = 2,
    continuation_discount: float = 0.35,
) -> Tuple[float, List[str]]:
    notes: List[str] = []

    responses = generate_opponent_responses(state=state, world=world, my_action=my_action)
    selected = _top_responses(responses, limit=response_limit)

    if not selected:
        notes.append("No continuation responses were available for lookahead.")
        return 0.0, notes

    baseline_worlds = list(all_worlds) if all_worlds is not None else [world]

    total_selected_weight = sum(response.weight for response in selected) or 1.0
    weighted_bonus = 0.0

    for response in selected:
        projection = project_action_against_response(
            state=state,
            my_action=my_action,
            response=response,
            world=world,
        )
        followup_state = build_followup_state_from_projection(state=state, projection=projection)

        updated_worlds, update_notes = reweight_world_distribution_from_branch_evidence(
            worlds=baseline_worlds,
            projection=projection,
            source_world=world,
        )

        continuation_value, continuation_notes = estimate_best_next_action_value(
            followup_state,
            updated_worlds=updated_worlds,
        )
        normalized_weight = response.weight / total_selected_weight

        weighted_bonus += normalized_weight * continuation_value
        notes.append(
            f"Lookahead branch '{response.label}' contributes continuation value {continuation_value:.1f} "
            f"at normalized weight {normalized_weight:.2f}."
        )
        notes.extend(update_notes[:2])
        notes.extend(continuation_notes[:3])

    discounted = weighted_bonus * continuation_discount
    notes.append(
        f"Discounted shallow-lookahead bonus: {discounted:.1f} "
        f"(discount={continuation_discount:.2f}, responses={len(selected)})."
    )
    return discounted, notes