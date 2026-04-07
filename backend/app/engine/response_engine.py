from __future__ import annotations

from typing import List, Tuple

from app.domain.actions import MoveAction
from app.domain.battle_state import BattleState, PokemonState
from app.inference.models import OpponentResponse, OpponentWorld
from app.engine.type_engine import combined_multiplier
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
    is_revealed: bool,
) -> float:
    weight = 1.0

    if is_revealed:
        weight += 0.75

    if move_action.move_type in opposing_active.types:
        weight += 0.60

    type_mult, _ = combined_multiplier(move_action.move_type, my_active.types)
    if type_mult >= 4.0:
        weight += 1.10
    elif type_mult >= 2.0:
        weight += 0.75
    elif type_mult == 0.0:
        weight -= 0.80
    elif 0.0 < type_mult < 1.0:
        weight -= 0.25

    if move_action.priority > 0:
        weight += 0.30

    if move_action.base_power >= 100:
        weight += 0.35
    elif move_action.base_power == 0 and move_action.move_category == "status":
        weight -= 0.20

    return max(0.10, weight)


def _build_hydrated_move_response(
    move_action: MoveAction,
    weight: float,
    *,
    is_revealed: bool,
    move_source: str,
) -> OpponentResponse:
    notes = [
        f"Opponent response is hydrated from move metadata for {move_action.move_name}.",
        f"Move source: {move_source}.",
    ]
    if is_revealed:
        notes.append("This move is already revealed, so its response weight is boosted.")

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
    """
    Returns (move_name, is_revealed) pairs in priority order:
    revealed moves first, then assumed moves.
    """
    ordered: list[tuple[str, bool]] = []
    seen: set[str] = set()

    for move_name in world.known_moves:
        key = move_name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append((move_name, True))

    for move_name in world.assumed_moves:
        key = move_name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            ordered.append((move_name, False))

    return ordered


def generate_opponent_responses(
    state: BattleState,
    world: OpponentWorld,
    my_action,
) -> List[OpponentResponse]:
    """
    Generate plausible opponent replies under one inferred world.

    This version hydrates candidate move names using move-provider metadata
    when possible, then applies simple inference-aware weighting.
    """
    responses: List[OpponentResponse] = []

    opposing_active = state.opponent_side.active
    my_active = state.my_side.active

    hydrated_candidates: list[tuple[MoveAction, float, bool]] = []
    move_name_pairs = _dedupe_move_names(world)

    for move_name, is_revealed in move_name_pairs[:4]:
        move_action = build_move_action_from_name(move_name)
        if move_action is None:
            continue

        response_weight = _estimate_response_weight(
            move_action=move_action,
            opposing_active=opposing_active,
            my_active=my_active,
            is_revealed=is_revealed,
        )
        hydrated_candidates.append((move_action, response_weight, is_revealed))

    if hydrated_candidates:
        move_weight_total = 0.85
        raw_total = sum(weight for _, weight, _ in hydrated_candidates) or 1.0

        for move_action, raw_weight, is_revealed in hydrated_candidates:
            normalized_move_weight = move_weight_total * (raw_weight / raw_total)
            responses.append(
                _build_hydrated_move_response(
                    move_action=move_action,
                    weight=normalized_move_weight,
                    is_revealed=is_revealed,
                    move_source=world.candidate.source,
                )
            )
    else:
        responses.append(
            _proxy_response_from_world(
                opposing_active=opposing_active,
                my_active=my_active,
                label="move::proxy-stab",
                weight=0.85,
            )
        )

    if state.opponent_side.bench:
        switch_weight = 0.15
        bench_target = state.opponent_side.bench[0]
        responses.append(
            OpponentResponse(
                kind="switch",
                label=f"switch::{bench_target.species or 'Unknown'}",
                weight=switch_weight,
                switch_target_species=bench_target.species,
                notes=[
                    "First-pass response generator includes a generic opponent switch option.",
                    "Switch target selection is currently simplistic and bench-order based.",
                ],
            )
        )

    total = sum(response.weight for response in responses) or 1.0
    for response in responses:
        response.weight = response.weight / total

    return responses


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