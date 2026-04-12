from __future__ import annotations

from typing import List

from app.domain.actions import EvaluatedAction
from app.domain.battle_state import BattleState
from app.inference.models import InferenceResult


def build_assumptions(
    state: BattleState,
    inference: InferenceResult | None = None,
) -> List[str]:
    assumptions: List[str] = [
        f"Format context placeholder: Gen {state.format_context.generation} / {state.format_context.format_name}.",
        "Evaluator now combines immediate projected outcomes with shallow continuation scoring.",
        "Recommendations aggregate projected outcomes across multiple plausible opponent worlds and responses.",
        "Strategic score can now include shallow lookahead, branch evidence updates, and branch-reweighted continuation pressure.",
        "Only relevant offensive/defensive stat boosts are currently applied.",
    ]

    if state.field.weather:
        assumptions.append(
            "Weather currently models only standard Fire/Water power changes for sun and rain."
        )

    if state.field.terrain:
        assumptions.append(
            "Terrain currently models offensive type boosts only; groundedness and other terrain effects are not yet modeled."
        )

    assumptions.append(
        "Turn order currently uses move priority, Speed stat, and Speed boosts."
    )
    assumptions.append(
        "Opponent responses are generated from revealed or assumed moves, with fallback proxy move characteristics when exact move details are unavailable."
    )
    assumptions.append(
        "Switch scoring remains a first-pass heuristic based on matchup, HP, rough speed context, and entry hazards."
    )
    assumptions.append(
        "Hazard handling currently models Stealth Rock, Spikes, Sticky Web, and Toxic Spikes with simplified groundedness/status logic."
    )
    assumptions.append(
        "Branch evidence can reinforce revealed moves and some high-impact item / ability hooks during continuation scoring."
    )
    assumptions.append(
        "Items, abilities, exact coverage prediction, and deeper multi-turn planning are still only partially modeled."
    )

    if inference is not None:
        assumptions.append(
            f"Inference confidence is currently '{inference.confidence_label}' for the opposing active Pokémon."
        )
        assumptions.extend(inference.notes)

    return assumptions


def _risk_band_text(top_action: EvaluatedAction) -> str:
    if top_action.worst_score is None or top_action.best_score is None:
        return "Risk band is not yet available."

    spread = top_action.best_score - top_action.worst_score
    if spread <= 8:
        return "This line looks relatively stable across plausible opponent worlds."
    if spread <= 20:
        return "This line has some meaningful variance across plausible opponent worlds."
    return "This line has a wide risk band, with noticeably different outcomes across plausible opponent worlds."


def _stability_text(top_action: EvaluatedAction) -> str:
    if top_action.stability is None:
        return "Stability is not yet available."

    if top_action.stability >= 0.8:
        return "The recommendation is relatively stable."
    if top_action.stability >= 0.5:
        return "The recommendation has moderate stability."
    return "The recommendation is volatile and depends more heavily on opponent assumptions."


def _bucket_driver_text(top_action: EvaluatedAction) -> str:
    breakdown = top_action.score_breakdown
    bucket_pairs = [
        ("tactical", breakdown.tactical),
        ("positional", breakdown.positional),
        ("strategic", breakdown.strategic),
        ("uncertainty", breakdown.uncertainty),
    ]
    dominant_bucket, dominant_value = max(bucket_pairs, key=lambda item: abs(item[1]))

    if dominant_bucket == "tactical":
        return "This recommendation is driven mostly by immediate projected combat value."
    if dominant_bucket == "positional":
        return "This recommendation is driven mostly by board-position value."
    if dominant_bucket == "strategic":
        return "This recommendation is driven mostly by continuation/search value rather than immediate damage alone."
    return "This recommendation is being shaped significantly by uncertainty handling."


def _continuation_signal_text(top_action: EvaluatedAction) -> str:
    strategic = top_action.score_breakdown.strategic
    tactical = top_action.score_breakdown.tactical
    positional = top_action.score_breakdown.positional

    if strategic >= 8.0:
        return "Continuation scoring plays a major role here."
    if strategic >= 3.0:
        return "Continuation scoring provides a meaningful boost here."
    if strategic <= -5.0:
        return "Continuation scoring is warning that the immediate line degrades badly afterward."
    if strategic <= -2.0:
        return "Continuation scoring is somewhat skeptical of the followup position."

    if abs(strategic) < 1.0 and abs(tactical) > abs(positional):
        return "This line is winning more on immediate value than on followup search."
    if abs(strategic) < 1.0 and abs(positional) > abs(tactical):
        return "This line is winning more on board positioning than on deeper continuation."

    return "Continuation impact is present but not dominant."


def _immediate_vs_followup_text(top_action: EvaluatedAction) -> str:
    tactical = top_action.score_breakdown.tactical
    strategic = top_action.score_breakdown.strategic

    if tactical >= 10.0 and strategic >= 5.0:
        return "This line looks strong both immediately and on continuation."
    if tactical >= 10.0 and strategic <= 0.0:
        return "This line looks good immediately, but its followup is less convincing."
    if tactical <= 5.0 and strategic >= 5.0:
        return "This line is not the strongest immediately, but it improves on continuation."
    if tactical < 0.0 and strategic > 0.0:
        return "Immediate pressure is weak, but the search layer still sees strategic compensation."
    return "Immediate and followup considerations are more balanced here."


def _world_influence_text(top_action: EvaluatedAction) -> str:
    if top_action.top_world_label is None or top_action.top_world_weight is None:
        return "No dominant opponent world was surfaced."

    weight = top_action.top_world_weight
    if weight >= 0.7:
        return (
            f"The recommendation is strongly influenced by the inferred opponent world "
            f"'{top_action.top_world_label}'."
        )
    if weight >= 0.45:
        return (
            f"The recommendation is meaningfully influenced by the inferred opponent world "
            f"'{top_action.top_world_label}'."
        )
    return (
        f"No single opponent world dominates; '{top_action.top_world_label}' is only the largest current contributor."
    )


def build_recommendation_explanation(top_action: EvaluatedAction) -> str:
    expected = top_action.expected_score
    worst = top_action.worst_score
    best = top_action.best_score
    stability = top_action.stability

    metric_text = ""
    if expected is not None and worst is not None and best is not None:
        metric_text = (
            f" Expected / worst / best scores: "
            f"{expected:.1f} / {worst:.1f} / {best:.1f}."
        )

    stability_text = ""
    if stability is not None:
        stability_text = f" Stability: {stability:.2f}."

    bucket_text = f" {_bucket_driver_text(top_action)}"
    continuation_text = f" {_continuation_signal_text(top_action)}"
    immediate_vs_followup = f" {_immediate_vs_followup_text(top_action)}"

    world_text = ""
    if top_action.top_world_label is not None and top_action.top_world_weight is not None:
        world_text = (
            f" The most influential inferred opponent world was "
            f"'{top_action.top_world_label}' ({top_action.top_world_weight:.2f})."
        )

    if top_action.action_type == "move":
        return (
            f"Recommended action: use {top_action.name}. "
            f"It currently has the best expected outcome across plausible opponent worlds."
            f"{metric_text}{stability_text}{bucket_text}{continuation_text}{immediate_vs_followup}{world_text}"
        )

    return (
        f"Recommended action: switch to {top_action.name}. "
        f"It currently has the best expected board outcome across plausible opponent worlds."
        f"{metric_text}{stability_text}{bucket_text}{continuation_text}{immediate_vs_followup}{world_text}"
    )


def summarize_top_action_notes(
    top_action: EvaluatedAction,
    limit: int = 4,
) -> List[str]:
    notes = [note.strip() for note in top_action.notes if note and note.strip()]
    return notes[:limit]


def build_reasoning_summary(
    top_action: EvaluatedAction,
    limit: int = 4,
) -> str:
    top_notes = summarize_top_action_notes(top_action, limit=limit)
    risk_band = _risk_band_text(top_action)
    stability = _stability_text(top_action)
    world_influence = _world_influence_text(top_action)

    continuation_lines = [
        note for note in top_notes
        if any(
            marker in note.lower()
            for marker in [
                "lookahead",
                "continuation",
                "strategic bucket",
                "branch",
                "threat adjustment",
                "second-ply",
            ]
        )
    ]

    if continuation_lines:
        joined = " ".join(continuation_lines[:2])
        return f"Key reasoning: {joined} {risk_band} {stability} {world_influence}"

    if not top_notes:
        return f"Key reasoning: {risk_band} {stability} {world_influence}"

    joined = " ".join(top_notes[:3])
    return f"Key reasoning: {joined} {risk_band} {stability} {world_influence}"


def build_inference_summary(inference: InferenceResult | None) -> str:
    if inference is None:
        return "No opponent-set inference summary is currently available."

    if not inference.candidates:
        return "No plausible opposing active set candidates are currently available."

    normalized = inference.normalized_weights()
    live_candidates = [candidate for candidate in inference.candidates if not candidate.is_eliminated]
    if not live_candidates:
        return "No non-eliminated opposing set candidates remain."

    normalized = inference.normalized_weights()
    top_candidate = max(live_candidates, key=lambda candidate: candidate.final_weight)
    top_weight = normalized.get(top_candidate.label, 0.0)

    return (
        f"Opponent active inference: top candidate is '{top_candidate.label}' "
        f"with normalized weight {top_weight:.2f}."
    )