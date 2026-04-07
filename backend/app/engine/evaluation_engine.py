from __future__ import annotations

import math
from typing import Dict, List, Tuple

from app.engine.lookahead_engine import estimate_lookahead_bonus
from app.domain.actions import EvaluatedAction, MoveAction, ScoreBreakdown, SwitchAction
from app.domain.battle_state import BattleState
from app.engine.projection_engine import project_action_against_response
from app.engine.response_engine import generate_opponent_responses
from app.engine.switch_engine import score_switch
from app.explain.explanation_engine import (
    build_assumptions,
    build_inference_summary,
    build_reasoning_summary,
    build_recommendation_explanation,
)
from app.inference.models import (
    ActionWorldEvaluation,
    AggregatedActionValue,
    InferenceResult,
    OpponentWorld,
)
from app.inference.set_inference import infer_opposing_active_set


def softmax(values: Dict[str, float], temperature: float = 8.0) -> Dict[str, float]:
    if not values:
        return {}

    max_v = max(values.values())
    exps = {k: math.exp((v - max_v) / max(temperature, 1e-6)) for k, v in values.items()}
    total = sum(exps.values()) or 1.0
    return {k: exps[k] / total for k in values}


def build_opponent_worlds(
    state: BattleState,
    inference_result: InferenceResult,
) -> List[OpponentWorld]:
    if not inference_result.candidates:
        return []

    normalized = inference_result.normalized_weights()
    revealed = list(state.opponent_side.active.revealed_moves)

    worlds: List[OpponentWorld] = []
    for candidate in inference_result.candidates:
        assumed_moves = []
        for move_name in candidate.moves:
            if move_name not in assumed_moves:
                assumed_moves.append(move_name)

        notes = [
            f"Opponent world derived from candidate '{candidate.label}'.",
            f"Candidate source: {candidate.source}.",
        ]
        if candidate.item:
            notes.append(f"Assumed item: {candidate.item}.")
        if candidate.ability:
            notes.append(f"Assumed ability: {candidate.ability}.")
        if candidate.tera_type:
            notes.append(f"Assumed Tera type: {candidate.tera_type}.")

        worlds.append(
            OpponentWorld(
                species=candidate.species,
                candidate=candidate,
                weight=normalized.get(candidate.label, 0.0),
                known_moves=revealed,
                assumed_moves=assumed_moves,
                assumed_item=candidate.item,
                assumed_ability=candidate.ability,
                assumed_tera_type=candidate.tera_type,
                notes=notes,
            )
        )

    return worlds


def score_projection_summary(
    projection,
    my_action,
    state: BattleState,
    continuation_bonus: float = 0.0,
) -> Tuple[ScoreBreakdown, List[str]]:
    notes = list(projection.notes)

    tactical = 0.0
    positional = 0.0
    strategic = 0.0
    uncertainty = 0.0

    opp_damage_pct = projection.opp_damage_taken_pct_current
    my_damage_pct = projection.my_damage_taken_pct_current

    tactical += opp_damage_pct * 0.9
    tactical -= my_damage_pct * 0.8

    if projection.opp_fainted:
        tactical += 35.0
        notes.append("Major boost: projected line KOs the opposing active Pokémon.")
    if projection.my_fainted:
        tactical -= 40.0
        notes.append("Heavy penalty: projected line loses the current active Pokémon.")

    if isinstance(my_action, MoveAction):
        if projection.order_context == "attacker_first" and not projection.my_fainted:
            tactical += 3.0
            notes.append("Small boost: projected line acts first.")
        elif projection.order_context == "attacker_second":
            tactical -= 3.0
            notes.append("Penalty: projected line absorbs pressure before acting.")
        elif projection.order_context == "speed_tie":
            uncertainty -= 2.0
            notes.append("Uncertainty penalty: speed tie / uncertain turn order.")

    if isinstance(my_action, SwitchAction):
        switch_target = next(
            (pokemon for pokemon in state.my_side.bench if pokemon.species == my_action.target_species),
            None,
        )
        if switch_target is not None:
            base_switch_score, switch_notes = score_switch(
                switch_target=switch_target,
                opposing_active=state.opponent_side.active,
                entry_side_conditions=state.my_side.side_conditions,
            )
            positional += base_switch_score
            notes.extend(switch_notes)

        if projection.my_damage_taken_pct_current >= 75.0:
            positional -= 10.0
            notes.append("Penalty: switch target is projected to take heavy immediate punishment.")
        elif projection.my_damage_taken_pct_current <= 25.0:
            positional += 4.0
            notes.append("Boost: switch target is projected to enter relatively safely.")

    hp_swing = projection.opp_damage_taken - projection.my_damage_taken
    positional += hp_swing * 0.1

    strategic += continuation_bonus
    if continuation_bonus != 0.0:
        notes.append(f"Strategic bucket includes shallow-lookahead bonus: {continuation_bonus:.1f}.")

    return (
        ScoreBreakdown(
            tactical=tactical,
            positional=positional,
            strategic=strategic,
            uncertainty=uncertainty,
        ),
        notes,
    )


def aggregate_response_scores(
    response_scores: List[tuple[float, float, dict]],
) -> Tuple[float, float, float]:
    if not response_scores:
        return 0.0, 0.0, 0.0

    expected = sum(score * weight for score, weight, _ in response_scores)
    worst = min(score for score, _, _ in response_scores)
    best = max(score for score, _, _ in response_scores)
    return expected, worst, best


def evaluate_action_in_world(
    state: BattleState,
    my_action,
    world: OpponentWorld,
    all_worlds: List[OpponentWorld],
    response_limit: int = 2,
    continuation_discount: float = 0.35,
) -> ActionWorldEvaluation:
    responses = generate_opponent_responses(state=state, world=world, my_action=my_action)

    response_scores: list[tuple[float, float, dict]] = []
    notes: list[str] = list(world.notes)
    notes.append(
        f"Evaluating against opponent world '{world.candidate.label}' (weight {world.weight:.2f})."
    )

    lookahead_bonus, lookahead_notes = estimate_lookahead_bonus(
        state=state,
        my_action=my_action,
        world=world,
        all_worlds=all_worlds,
        response_limit=response_limit,
        continuation_discount=continuation_discount,
    )
    notes.extend(lookahead_notes[:3])

    for response in responses:
        projection = project_action_against_response(
            state=state,
            my_action=my_action,
            response=response,
            world=world,
        )
        score_breakdown, projection_notes = score_projection_summary(
            projection=projection,
            my_action=my_action,
            state=state,
            continuation_bonus=lookahead_bonus,
        )
        response_total = score_breakdown.total

        response_dict = {
            "responseLabel": response.label,
            "responseWeight": response.weight,
            "score": response_total,
            "scoreBreakdown": score_breakdown.to_dict(),
            "notes": projection_notes[:6],
        }
        response_scores.append((response_total, response.weight, response_dict))

    expected, worst, best = aggregate_response_scores(response_scores)
    response_breakdown = [payload for _, _, payload in response_scores]

    notes.append(
        f"World aggregation -> expected {expected:.1f}, worst {worst:.1f}, best {best:.1f}."
    )

    return ActionWorldEvaluation(
        world=world,
        expected_score=expected,
        worst_score=worst,
        best_score=best,
        response_breakdown=response_breakdown,
        notes=notes,
    )

def aggregate_world_evaluations(
    world_evaluations: List[ActionWorldEvaluation],
) -> AggregatedActionValue:
    if not world_evaluations:
        return AggregatedActionValue(
            expected_score=0.0,
            worst_score=0.0,
            best_score=0.0,
            stability=0.0,
            notes=["No opponent worlds were available for aggregation."],
        )

    expected = sum(world_eval.expected_score * world_eval.world.weight for world_eval in world_evaluations)
    worst = min(world_eval.worst_score for world_eval in world_evaluations)
    best = max(world_eval.best_score for world_eval in world_evaluations)

    # Stability = how tight the band is; smaller spread => higher stability.
    spread = max(0.0, best - worst)
    stability = max(0.0, 1.0 - min(spread / 100.0, 1.0))

    notes: list[str] = []
    for world_eval in world_evaluations[:3]:
        notes.extend(world_eval.notes[:2])

    notes.append(
        f"Cross-world aggregation -> expected {expected:.1f}, worst {worst:.1f}, best {best:.1f}, stability {stability:.2f}."
    )

    return AggregatedActionValue(
        expected_score=expected,
        worst_score=worst,
        best_score=best,
        stability=stability,
        notes=notes,
    )

def build_move_evaluated_action(
    move,
    aggregated: AggregatedActionValue,
    top_world_label: str | None = None,
    top_world_weight: float | None = None,
) -> EvaluatedAction:
    action = MoveAction(
        move_name=(move.name or "Unknown move").strip(),
        move_type=move.type,
        move_category=move.category,
        base_power=move.power or 0,
        priority=int(getattr(move, "priority", 0) or 0),
    )

    notes = list(aggregated.notes)

    return EvaluatedAction(
        action=action,
        score_breakdown=ScoreBreakdown(
            tactical=aggregated.expected_score,
            positional=0.0,
            strategic=0.0,
            uncertainty=-(1.0 - aggregated.stability) * 5.0,
        ),
        confidence=0.0,
        notes=notes,
        type_multiplier=None,
        min_damage=None,
        max_damage=None,
        min_damage_percent=None,
        max_damage_percent=None,
        expected_score=aggregated.expected_score,
        worst_score=aggregated.worst_score,
        best_score=aggregated.best_score,
        stability=aggregated.stability,
        top_world_label=top_world_label,
        top_world_weight=top_world_weight,
    )


def evaluate_move_actions(
    state: BattleState,
    worlds: List[OpponentWorld],
) -> List[EvaluatedAction]:
    results: List[EvaluatedAction] = []

    for move in state.moves:
        my_action = MoveAction(
            move_name=(move.name or "Unknown move").strip(),
            move_type=move.type,
            move_category=move.category,
            base_power=move.power or 0,
            priority=int(getattr(move, "priority", 0) or 0),
        )

        world_evaluations = [
            evaluate_action_in_world(state=state, my_action=my_action, world=world, all_worlds=worlds,)
            for world in worlds
        ]
        aggregated = aggregate_world_evaluations(world_evaluations)
        top_world_label, top_world_weight = top_influential_world(world_evaluations)

        results.append(
            build_move_evaluated_action(
                move=move,
                aggregated=aggregated,
                top_world_label=top_world_label,
                top_world_weight=top_world_weight,
            )
        )

    return results

def evaluate_switch_actions(
    state: BattleState,
    worlds: List[OpponentWorld],
) -> List[EvaluatedAction]:
    results: List[EvaluatedAction] = []

    for switch_target in state.my_side.bench:
        species = switch_target.species or "Unknown switch target"
        action = SwitchAction(target_species=species)

        world_evaluations = [
            evaluate_action_in_world(state=state, my_action=action, world=world, all_worlds=worlds,)
            for world in worlds
        ]
        aggregated = aggregate_world_evaluations(world_evaluations)
        top_world_label, top_world_weight = top_influential_world(world_evaluations)

        results.append(
            build_switch_evaluated_action(
                target_species=species,
                aggregated=aggregated,
                top_world_label=top_world_label,
                top_world_weight=top_world_weight,
            )
        )

    return results


def build_switch_evaluated_action(
    target_species: str,
    aggregated: AggregatedActionValue,
    top_world_label: str | None = None,
    top_world_weight: float | None = None,
) -> EvaluatedAction:
    action = SwitchAction(target_species=target_species)

    notes = list(aggregated.notes)

    return EvaluatedAction(
        action=action,
        score_breakdown=ScoreBreakdown(
            tactical=0.0,
            positional=aggregated.expected_score,
            strategic=0.0,
            uncertainty=-(1.0 - aggregated.stability) * 5.0,
        ),
        confidence=0.0,
        notes=notes,
        expected_score=aggregated.expected_score,
        worst_score=aggregated.worst_score,
        best_score=aggregated.best_score,
        stability=aggregated.stability,
        top_world_label=top_world_label,
        top_world_weight=top_world_weight,
    )


def evaluate_battle_state(
    state: BattleState,
    temperature: float = 8.0,
) -> Tuple[str, float, List[dict], str, List[str]]:
    evaluated_actions: List[EvaluatedAction] = []
    raw_scores: Dict[str, float] = {}

    inference_result = infer_opposing_active_set(state)
    assumptions_used = build_assumptions(state, inference=inference_result)

    worlds = build_opponent_worlds(state=state, inference_result=inference_result)
    if not worlds:
        assumptions_used.append("No opponent worlds were built; evaluator is falling back to empty aggregation.")

    evaluated_actions.extend(evaluate_move_actions(state=state, worlds=worlds))
    evaluated_actions.extend(evaluate_switch_actions(state=state, worlds=worlds))

    if not evaluated_actions:
        return (
            "No action",
            0.0,
            [],
            "No legal actions were available to evaluate.",
            assumptions_used,
        )

    for evaluated in evaluated_actions:
        raw_scores[f"{evaluated.action_type}::{evaluated.name}"] = evaluated.score

    confidences = softmax(raw_scores, temperature=temperature)

    for evaluated in evaluated_actions:
        evaluated.confidence = confidences.get(f"{evaluated.action_type}::{evaluated.name}", 0.0)

    evaluated_actions.sort(key=lambda x: x.score, reverse=True)

    top = evaluated_actions[0]
    best_action = top.name
    best_conf = top.confidence

    recommendation = build_recommendation_explanation(top)
    reasoning_summary = build_reasoning_summary(top)
    inference_summary = build_inference_summary(inference_result)
    explanation = f"{recommendation} {reasoning_summary} {inference_summary}"

    ranked_actions = [evaluated.to_dict() for evaluated in evaluated_actions]

    return best_action, best_conf, ranked_actions, explanation, assumptions_used

def top_influential_world(
    world_evaluations: List[ActionWorldEvaluation],
) -> tuple[str | None, float | None]:
    if not world_evaluations:
        return None, None

    top_world = max(
        world_evaluations,
        key=lambda world_eval: world_eval.world.weight,
    )
    return top_world.world.candidate.label, top_world.world.weight