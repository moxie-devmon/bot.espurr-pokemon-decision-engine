from __future__ import annotations

from app.domain.battle_state import BattleState, PokemonState
from app.inference.models import CandidateSet, InferenceResult


# First-pass local seeds.
# Replace later with a provider-backed meta snapshot.
SEEDED_OPPONENT_PRIORS: dict[str, list[CandidateSet]] = {
    "Great Tusk": [
        CandidateSet(
            species="Great Tusk",
            label="bulky-utility",
            moves=["Headlong Rush", "Earthquake", "Knock Off", "Rapid Spin", "Stealth Rock"],
            item="Leftovers",
            ability="Protosynthesis",
            weight=0.50,
            source="seed",
        ),
        CandidateSet(
            species="Great Tusk",
            label="offensive-spinner",
            moves=["Headlong Rush", "Close Combat", "Ice Spinner", "Rapid Spin"],
            item="Booster Energy",
            ability="Protosynthesis",
            weight=0.30,
            source="seed",
        ),
        CandidateSet(
            species="Great Tusk",
            label="scarf-attacker",
            moves=["Earthquake", "Close Combat", "Knock Off", "Ice Spinner"],
            item="Choice Scarf",
            ability="Protosynthesis",
            weight=0.20,
            source="seed",
        ),
    ],
    "Kingambit": [
        CandidateSet(
            species="Kingambit",
            label="black-glasses-sd",
            moves=["Kowtow Cleave", "Sucker Punch", "Iron Head", "Swords Dance"],
            item="Black Glasses",
            ability="Supreme Overlord",
            weight=0.45,
            source="seed",
        ),
        CandidateSet(
            species="Kingambit",
            label="leftovers-bulky",
            moves=["Kowtow Cleave", "Sucker Punch", "Iron Head", "Low Kick"],
            item="Leftovers",
            ability="Supreme Overlord",
            weight=0.30,
            source="seed",
        ),
        CandidateSet(
            species="Kingambit",
            label="banded-attacker",
            moves=["Kowtow Cleave", "Sucker Punch", "Iron Head", "Low Kick"],
            item="Choice Band",
            ability="Supreme Overlord",
            weight=0.25,
            source="seed",
        ),
    ],
}


def infer_opposing_active_set(state: BattleState) -> InferenceResult:
    opposing_active = state.opponent_side.active
    return infer_pokemon_state(opposing_active)


def infer_pokemon_state(pokemon: PokemonState) -> InferenceResult:
    species = pokemon.species

    if not species:
        return InferenceResult(
            species=None,
            candidates=[],
            confidence_label="unknown",
            notes=[
                "No species provided, so no candidate sets were generated.",
            ],
        )

    seeded = SEEDED_OPPONENT_PRIORS.get(species)
    if not seeded:
        placeholder_candidate = CandidateSet(
            species=species,
            label="generic-placeholder-set",
            moves=list(pokemon.revealed_moves),
            weight=1.0,
            source="placeholder",
        )
        return InferenceResult(
            species=species,
            candidates=[placeholder_candidate],
            confidence_label="placeholder",
            notes=[
                "No seeded priors found for this species.",
                "Fallback candidate preserves revealed moves only.",
                "Meta-provider integration is not loaded yet.",
            ],
        )

    candidates: list[CandidateSet] = []
    for candidate in seeded:
        merged_moves = list(candidate.moves)
        for revealed_move in pokemon.revealed_moves:
            if revealed_move not in merged_moves:
                merged_moves.append(revealed_move)

        candidates.append(
            CandidateSet(
                species=candidate.species,
                label=candidate.label,
                moves=merged_moves,
                item=candidate.item,
                ability=candidate.ability,
                tera_type=candidate.tera_type,
                weight=candidate.weight,
                source=candidate.source,
            )
        )

    notes = [
        f"Seeded priors loaded for {species}.",
        "Revealed moves were merged into all plausible candidate sets.",
        "Weights are still seed-level and not yet updated dynamically from battle evidence.",
    ]

    return InferenceResult(
        species=species,
        candidates=candidates,
        confidence_label="seeded",
        notes=notes,
    )