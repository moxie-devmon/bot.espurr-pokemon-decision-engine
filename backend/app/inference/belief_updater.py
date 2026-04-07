from __future__ import annotations

from typing import Iterable, Optional

from app.inference.models import CandidateSet, InferenceResult, OpponentWorld


def renormalize_candidates(candidates: Iterable[CandidateSet]) -> list[CandidateSet]:
    candidates = list(candidates)
    total = sum(max(0.0, candidate.weight) for candidate in candidates) or 1.0

    renormalized: list[CandidateSet] = []
    for candidate in candidates:
        renormalized.append(
            CandidateSet(
                species=candidate.species,
                label=candidate.label,
                moves=list(candidate.moves),
                item=candidate.item,
                ability=candidate.ability,
                tera_type=candidate.tera_type,
                weight=max(0.0, candidate.weight) / total,
                source=candidate.source,
            )
        )

    return renormalized


def apply_revealed_move(
    inference: InferenceResult,
    revealed_move: str,
) -> InferenceResult:
    updated_candidates: list[CandidateSet] = []

    for candidate in inference.candidates:
        updated_moves = list(candidate.moves)
        already_present = revealed_move in updated_moves
        if not already_present:
            updated_moves.append(revealed_move)

        weight_mult = 1.35 if already_present else 0.90

        updated_candidates.append(
            CandidateSet(
                species=candidate.species,
                label=candidate.label,
                moves=updated_moves,
                item=candidate.item,
                ability=candidate.ability,
                tera_type=candidate.tera_type,
                weight=candidate.weight * weight_mult,
                source=candidate.source,
            )
        )

    updated_candidates = renormalize_candidates(updated_candidates)

    updated_notes = list(inference.notes)
    updated_notes.append(
        f"Belief updater recorded revealed move evidence: {revealed_move}."
    )

    return InferenceResult(
        species=inference.species,
        candidates=updated_candidates,
        confidence_label=inference.confidence_label,
        notes=updated_notes,
    )


def apply_item_evidence(
    inference: InferenceResult,
    item_name: str,
) -> InferenceResult:
    normalized_item = item_name.strip().lower()
    updated_candidates: list[CandidateSet] = []

    for candidate in inference.candidates:
        candidate_item = (candidate.item or "").strip().lower()

        if candidate_item == normalized_item:
            weight_mult = 1.60
        elif candidate_item:
            weight_mult = 0.35
        else:
            weight_mult = 0.80

        updated_candidates.append(
            CandidateSet(
                species=candidate.species,
                label=candidate.label,
                moves=list(candidate.moves),
                item=candidate.item or item_name,
                ability=candidate.ability,
                tera_type=candidate.tera_type,
                weight=candidate.weight * weight_mult,
                source=candidate.source,
            )
        )

    updated_candidates = renormalize_candidates(updated_candidates)

    updated_notes = list(inference.notes)
    updated_notes.append(
        f"Belief updater recorded item evidence: {item_name}."
    )

    return InferenceResult(
        species=inference.species,
        candidates=updated_candidates,
        confidence_label=inference.confidence_label,
        notes=updated_notes,
    )


def apply_ability_evidence(
    inference: InferenceResult,
    ability_name: str,
) -> InferenceResult:
    normalized_ability = ability_name.strip().lower()
    updated_candidates: list[CandidateSet] = []

    for candidate in inference.candidates:
        candidate_ability = (candidate.ability or "").strip().lower()

        if candidate_ability == normalized_ability:
            weight_mult = 1.60
        elif candidate_ability:
            weight_mult = 0.35
        else:
            weight_mult = 0.80

        updated_candidates.append(
            CandidateSet(
                species=candidate.species,
                label=candidate.label,
                moves=list(candidate.moves),
                item=candidate.item,
                ability=candidate.ability or ability_name,
                tera_type=candidate.tera_type,
                weight=candidate.weight * weight_mult,
                source=candidate.source,
            )
        )

    updated_candidates = renormalize_candidates(updated_candidates)

    updated_notes = list(inference.notes)
    updated_notes.append(
        f"Belief updater recorded ability evidence: {ability_name}."
    )

    return InferenceResult(
        species=inference.species,
        candidates=updated_candidates,
        confidence_label=inference.confidence_label,
        notes=updated_notes,
    )


def apply_branch_evidence(
    inference: InferenceResult,
    *,
    revealed_move: Optional[str] = None,
    item_evidence: Optional[str] = None,
    ability_evidence: Optional[str] = None,
) -> InferenceResult:
    updated = inference

    if revealed_move:
        updated = apply_revealed_move(updated, revealed_move)
    if item_evidence:
        updated = apply_item_evidence(updated, item_evidence)
    if ability_evidence:
        updated = apply_ability_evidence(updated, ability_evidence)

    updated_notes = list(updated.notes)
    updated_notes.append("Branch evidence was applied to the followup opponent belief state.")

    return InferenceResult(
        species=updated.species,
        candidates=updated.candidates,
        confidence_label=updated.confidence_label,
        notes=updated_notes,
    )


def worlds_to_inference(worlds: list[OpponentWorld]) -> InferenceResult:
    if not worlds:
        return InferenceResult(
            species=None,
            candidates=[],
            confidence_label="empty",
            notes=["No worlds were available for belief conversion."],
        )

    candidates: list[CandidateSet] = []
    for world in worlds:
        candidates.append(
            CandidateSet(
                species=world.species,
                label=world.candidate.label,
                moves=list(world.assumed_moves),
                item=world.assumed_item if world.assumed_item is not None else world.candidate.item,
                ability=world.assumed_ability if world.assumed_ability is not None else world.candidate.ability,
                tera_type=world.assumed_tera_type if world.assumed_tera_type is not None else world.candidate.tera_type,
                weight=world.weight,
                source=world.candidate.source,
            )
        )

    candidates = renormalize_candidates(candidates)

    return InferenceResult(
        species=worlds[0].species,
        candidates=candidates,
        confidence_label="branch_distribution",
        notes=["Converted opponent world distribution into inference distribution for branch reweighting."],
    )


def inference_to_worlds(
    inference: InferenceResult,
    template_worlds: list[OpponentWorld],
) -> list[OpponentWorld]:
    if not inference.candidates:
        return []

    template_by_label = {
        world.candidate.label: world
        for world in template_worlds
    }

    normalized = inference.normalized_weights()
    updated_worlds: list[OpponentWorld] = []

    for candidate in inference.candidates:
        template = template_by_label.get(candidate.label)
        if template is None:
            continue

        updated_worlds.append(
            OpponentWorld(
                species=inference.species,
                candidate=candidate,
                weight=normalized.get(candidate.label, 0.0),
                known_moves=list(template.known_moves),
                assumed_moves=list(candidate.moves),
                assumed_item=candidate.item,
                assumed_ability=candidate.ability,
                assumed_tera_type=candidate.tera_type,
                notes=list(template.notes) + list(inference.notes[-3:]),
            )
        )

    return updated_worlds