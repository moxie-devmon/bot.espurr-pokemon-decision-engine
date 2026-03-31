from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Dict, List, Tuple

from app.domain.actions import EvaluatedAction, MoveAction, ScoreBreakdown, SwitchAction
from app.domain.battle_state import BattleState, PokemonState
from app.explain.explanation_engine import (
    build_assumptions,
    build_inference_summary,
    build_reasoning_summary,
    build_recommendation_explanation,
)
from app.inference.set_inference import infer_opposing_active_set
from app.engine.damage_engine import estimate_damage
from app.engine.field_engine import apply_field_modifiers
from app.engine.speed_engine import (
    stage_multiplier,
    turn_order_context,
    turn_order_score_adjustment,
)
from app.engine.switch_engine import score_switch
from app.engine.type_engine import combined_multiplier


def softmax(values: Dict[str, float], temperature: float = 8.0) -> Dict[str, float]:
    if not values:
        return {}

    max_v = max(values.values())
    exps = {k: math.exp((v - max_v) / max(temperature, 1e-6)) for k, v in values.items()}
    total = sum(exps.values()) or 1.0
    return {k: exps[k] / total for k in values}


def score_move_tactical(
    min_pct: float,
    max_pct: float,
    type_mult: float,
    category: str,
    base_power: int,
) -> float:
    if category == "status" or base_power <= 0:
        return -5.0

    avg_pct = (min_pct + max_pct) / 2.0
    score = avg_pct

    if type_mult >= 2.0:
        score += 5.0
    elif 0.0 < type_mult < 1.0:
        score -= 3.0
    elif type_mult == 0.0:
        score -= 100.0

    if min_pct >= 100.0:
        score += 15.0
    elif max_pct >= 100.0:
        score += 8.0

    return score


def apply_relevant_boosts(
    attacking_pokemon: PokemonState,
    defending_pokemon: PokemonState,
    move_category: str,
) -> Tuple[PokemonState, PokemonState, List[str]]:
    notes: List[str] = []

    if move_category == "physical":
        atk_mult = stage_multiplier(attacking_pokemon.boosts.atk)
        def_mult = stage_multiplier(defending_pokemon.boosts.def_)

        boosted_attacker = replace(attacking_pokemon, atk=attacking_pokemon.atk * atk_mult)
        boosted_defender = replace(defending_pokemon, def_=defending_pokemon.def_ * def_mult)

        if attacking_pokemon.boosts.atk != 0:
            notes.append(f"Attacking Pokémon Attack boost stage applied: {attacking_pokemon.boosts.atk}.")
        if defending_pokemon.boosts.def_ != 0:
            notes.append(f"Defending Pokémon Defense boost stage applied: {defending_pokemon.boosts.def_}.")

        return boosted_attacker, boosted_defender, notes

    if move_category == "special":
        spa_mult = stage_multiplier(attacking_pokemon.boosts.spa)
        spd_mult = stage_multiplier(defending_pokemon.boosts.spd)

        boosted_attacker = replace(attacking_pokemon, spa=attacking_pokemon.spa * spa_mult)
        boosted_defender = replace(defending_pokemon, spd=defending_pokemon.spd * spd_mult)

        if attacking_pokemon.boosts.spa != 0:
            notes.append(f"Attacking Pokémon Special Attack boost stage applied: {attacking_pokemon.boosts.spa}.")
        if defending_pokemon.boosts.spd != 0:
            notes.append(f"Defending Pokémon Special Defense boost stage applied: {defending_pokemon.boosts.spd}.")

        return boosted_attacker, boosted_defender, notes

    return attacking_pokemon, defending_pokemon, notes


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


def proxy_retaliation_move(defending_pokemon: PokemonState, attacking_pokemon: PokemonState):
    best_stab_type, best_mult = best_stab_type_into_target(defending_pokemon, attacking_pokemon)

    if best_stab_type is None:
        best_stab_type = defending_pokemon.types[0] if defending_pokemon.types else "Normal"
        best_mult = 1.0

    defender_prefers_physical = float(defending_pokemon.atk or 100) >= float(defending_pokemon.spa or 100)
    category = "physical" if defender_prefers_physical else "special"
    power = 100 if best_mult >= 2.0 else 80

    return SimpleNamespace(
        name=f"Proxy {best_stab_type} STAB",
        type=best_stab_type,
        category=category,
        power=power,
        priority=0,
        crit=False,
        level=defending_pokemon.level,
    )


def retaliation_context(
    attacking_pokemon: PokemonState,
    defending_pokemon: PokemonState,
) -> Tuple[dict, List[str]]:
    notes: List[str] = []

    proxy_move = proxy_retaliation_move(defending_pokemon, attacking_pokemon)
    notes.append(
        f"Proxy retaliation assumes opposing active Pokémon can use a plausible {proxy_move.type}-type STAB attack "
        f"({proxy_move.category}, {proxy_move.power} BP)."
    )

    retaliation = estimate_damage(
        attacker=defending_pokemon,
        defender=attacking_pokemon,
        move=proxy_move,
    )

    attacker_current_hp = float(
        attacking_pokemon.current_hp if attacking_pokemon.current_hp is not None else attacking_pokemon.hp or 100
    )
    attacker_max_hp = max(1.0, float(attacking_pokemon.hp or 100))

    retaliation_min_pct_current = max(
        0.0,
        min((float(retaliation["minDamage"]) / max(1.0, attacker_current_hp)) * 100.0, 100.0),
    )
    retaliation_max_pct_current = max(
        0.0,
        min((float(retaliation["maxDamage"]) / max(1.0, attacker_current_hp)) * 100.0, 100.0),
    )

    context = {
        "moveType": proxy_move.type,
        "moveCategory": proxy_move.category,
        "power": proxy_move.power,
        "typeMultiplier": retaliation["typeMultiplier"],
        "minDamage": retaliation["minDamage"],
        "maxDamage": retaliation["maxDamage"],
        "minPercentMaxHp": retaliation["minPercent"],
        "maxPercentMaxHp": retaliation["maxPercent"],
        "minPercentCurrentHp": retaliation_min_pct_current,
        "maxPercentCurrentHp": retaliation_max_pct_current,
        "attackerCurrentHp": attacker_current_hp,
        "attackerMaxHp": attacker_max_hp,
    }

    return context, notes


def survivability_score_adjustment(
    order_context: str,
    retaliation: dict,
    category: str,
    base_power: int,
) -> Tuple[float, List[str]]:
    notes: List[str] = []

    if category == "status" or base_power <= 0:
        return 0.0, notes

    adjustment = 0.0
    max_pct_current = float(retaliation["maxPercentCurrentHp"])
    min_pct_current = float(retaliation["minPercentCurrentHp"])

    if order_context == "attacker_second":
        if min_pct_current >= 100.0:
            adjustment -= 45.0
            notes.append("Heavy penalty: attacker is likely KOed by proxy retaliation before moving.")
        elif max_pct_current >= 100.0:
            adjustment -= 30.0
            notes.append("Strong penalty: attacker may be KOed by proxy retaliation before moving.")
        elif max_pct_current >= 75.0:
            adjustment -= 16.0
            notes.append("Penalty: attacker risks taking very heavy proxy retaliation before moving.")
        elif max_pct_current >= 50.0:
            adjustment -= 8.0
            notes.append("Penalty: attacker risks substantial proxy retaliation before moving.")

    elif order_context == "speed_tie":
        if max_pct_current >= 100.0:
            adjustment -= 12.0
            notes.append("Penalty: speed tie plus proxy retaliation means attacker may be KOed before acting.")
        elif max_pct_current >= 75.0:
            adjustment -= 6.0
            notes.append("Penalty: speed tie makes heavy proxy retaliation risky.")

    return adjustment, notes


def build_move_score_breakdown(
    move,
    dmg: dict,
    order_context: str,
    retaliation: dict,
) -> Tuple[ScoreBreakdown, List[str]]:
    notes: List[str] = []
    base_power = move.power or 0

    tactical = score_move_tactical(
        min_pct=dmg["minPercent"],
        max_pct=dmg["maxPercent"],
        type_mult=dmg["typeMultiplier"],
        category=move.category,
        base_power=base_power,
    )

    turn_adjustment, turn_notes = turn_order_score_adjustment(
        order_context=order_context,
        min_pct=dmg["minPercent"],
        max_pct=dmg["maxPercent"],
        category=move.category,
        base_power=base_power,
    )
    tactical += turn_adjustment
    notes.extend(turn_notes)

    survivability_adjustment, survivability_notes = survivability_score_adjustment(
        order_context=order_context,
        retaliation=retaliation,
        category=move.category,
        base_power=base_power,
    )
    tactical += survivability_adjustment
    notes.extend(survivability_notes)

    return (
        ScoreBreakdown(
            tactical=tactical,
            positional=0.0,
            strategic=0.0,
            uncertainty=0.0,
        ),
        notes,
    )


def build_switch_score_breakdown(
    switch_target: PokemonState,
    state: BattleState,
) -> Tuple[ScoreBreakdown, List[str]]:
    switch_score, notes = score_switch(
        switch_target=switch_target,
        opposing_active=state.opponent_side.active,
        entry_side_conditions=state.my_side.side_conditions,
    )

    return (
        ScoreBreakdown(
            tactical=0.0,
            positional=switch_score,
            strategic=0.0,
            uncertainty=0.0,
        ),
        notes,
    )


def evaluate_move_actions(state: BattleState) -> List[EvaluatedAction]:
    results: List[EvaluatedAction] = []

    attacking_pokemon = state.my_side.active
    defending_pokemon = state.opponent_side.active

    for idx, move in enumerate(state.moves):
        move_name = (move.name or f"Move {idx+1}").strip()

        boosted_attacker, boosted_defender, boost_notes = apply_relevant_boosts(
            attacking_pokemon,
            defending_pokemon,
            move.category,
        )

        dmg = estimate_damage(
            attacker=boosted_attacker,
            defender=boosted_defender,
            move=move,
        )

        defender_hp = max(1.0, float(boosted_defender.hp or 100))
        dmg, field_notes = apply_field_modifiers(
            dmg=dmg,
            move=move,
            field=state.field,
            defender_hp=defender_hp,
        )

        order_context, turn_order_notes = turn_order_context(
            attacking_pokemon=attacking_pokemon,
            defending_pokemon=defending_pokemon,
            move=move,
        )

        retaliation, retaliation_notes = retaliation_context(
            attacking_pokemon=attacking_pokemon,
            defending_pokemon=defending_pokemon,
        )

        score_breakdown, breakdown_notes = build_move_score_breakdown(
            move=move,
            dmg=dmg,
            order_context=order_context,
            retaliation=retaliation,
        )

        extra_notes = list(retaliation_notes)
        extra_notes.append(
            f"Proxy retaliation estimate vs attacker current HP: "
            f"{retaliation['minPercentCurrentHp']:.1f}–{retaliation['maxPercentCurrentHp']:.1f}%."
        )

        action = MoveAction(
            move_name=move_name,
            move_type=move.type,
            move_category=move.category,
            base_power=move.power or 0,
            priority=int(getattr(move, "priority", 0) or 0),
        )

        results.append(
            EvaluatedAction(
                action=action,
                score_breakdown=score_breakdown,
                confidence=0.0,
                notes=(
                    dmg["notes"]
                    + boost_notes
                    + field_notes
                    + turn_order_notes
                    + extra_notes
                    + breakdown_notes
                ),
                type_multiplier=dmg["typeMultiplier"],
                min_damage=dmg["minDamage"],
                max_damage=dmg["maxDamage"],
                min_damage_percent=dmg["minPercent"],
                max_damage_percent=dmg["maxPercent"],
            )
        )

    return results


def evaluate_switch_actions(state: BattleState) -> List[EvaluatedAction]:
    results: List[EvaluatedAction] = []

    for switch_target in state.my_side.bench:
        species = switch_target.species or "Unknown switch target"
        score_breakdown, notes = build_switch_score_breakdown(
            switch_target=switch_target,
            state=state,
        )

        action = SwitchAction(target_species=species)

        results.append(
            EvaluatedAction(
                action=action,
                score_breakdown=score_breakdown,
                confidence=0.0,
                notes=notes,
            )
        )

    return results


def evaluate_battle_state(
    state: BattleState,
    temperature: float = 8.0,
) -> Tuple[str, float, List[dict], str, List[str]]:
    evaluated_actions: List[EvaluatedAction] = []
    raw_scores: Dict[str, float] = {}

    inference_result = infer_opposing_active_set(state)
    assumptions_used = build_assumptions(state, inference=inference_result)

    evaluated_actions.extend(evaluate_move_actions(state))
    evaluated_actions.extend(evaluate_switch_actions(state))

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