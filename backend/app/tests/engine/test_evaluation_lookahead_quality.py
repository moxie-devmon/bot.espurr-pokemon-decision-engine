from __future__ import annotations

from app.domain.actions import MoveAction
from app.domain.battle_state import (
    BattleState,
    FieldState,
    FormatContext,
    PokemonState,
    SideConditions,
    SideState,
)
from app.engine.evaluation_engine import (
    aggregate_world_evaluations,
    build_opponent_worlds,
    evaluate_action_in_world,
    top_influential_world,
)
from app.engine.lookahead_engine import estimate_lookahead_bonus
from app.inference.models import (
    ActionWorldEvaluation,
    CandidateSet,
    InferenceResult,
    OpponentWorld,
)


def _test_state() -> BattleState:
    my_active = PokemonState(
        species="Dragonite",
        types=["Dragon", "Flying"],
        hp=100,
        current_hp=100,
        atk=134,
        def_=95,
        spa=100,
        spd=100,
        spe=80,
        level=100,
        revealed_moves=[],
    )

    opponent_active = PokemonState(
        species="Great Tusk",
        types=["Ground", "Fighting"],
        hp=100,
        current_hp=100,
        atk=131,
        def_=131,
        spa=53,
        spd=53,
        spe=87,
        level=100,
        revealed_moves=["Headlong Rush"],
    )

    my_bench = [
        PokemonState(
            species="Zapdos",
            types=["Electric", "Flying"],
            hp=100,
            current_hp=100,
            atk=90,
            def_=85,
            spa=125,
            spd=90,
            spe=100,
            level=100,
            revealed_moves=[],
        ),
        PokemonState(
            species="Kingambit",
            types=["Dark", "Steel"],
            hp=100,
            current_hp=100,
            atk=135,
            def_=120,
            spa=60,
            spd=85,
            spe=50,
            level=100,
            revealed_moves=[],
        ),
    ]

    opponent_bench = [
        PokemonState(
            species="Gholdengo",
            types=["Steel", "Ghost"],
            hp=100,
            current_hp=100,
            atk=60,
            def_=95,
            spa=133,
            spd=91,
            spe=84,
            level=100,
            revealed_moves=[],
        ),
        PokemonState(
            species="Rillaboom",
            types=["Grass"],
            hp=100,
            current_hp=100,
            atk=125,
            def_=90,
            spa=60,
            spd=70,
            spe=85,
            level=100,
            revealed_moves=[],
        ),
    ]

    return BattleState(
        my_side=SideState(
            active=my_active,
            bench=my_bench,
            side_conditions=SideConditions(),
        ),
        opponent_side=SideState(
            active=opponent_active,
            bench=opponent_bench,
            side_conditions=SideConditions(),
        ),
        moves=[],
        field=FieldState(
            weather=None,
            terrain=None,
        ),
        format_context=FormatContext(
            generation=9,
            format_name="gen9ou",
            ruleset=[],
        ),
    )


def _candidate(
    *,
    label: str,
    species: str = "Great Tusk",
    moves: list[str],
    confirmed_moves: list[str] | None = None,
    assumed_moves: list[str] | None = None,
    item: str | None = None,
    ability: str | None = None,
    tera_type: str | None = None,
    final_weight: float = 1.0,
) -> CandidateSet:
    return CandidateSet(
        species=species,
        label=label,
        moves=list(moves),
        item=item,
        ability=ability,
        tera_type=tera_type,
        spread_label="test-spread",
        prior_weight=1.0,
        compatibility_weight=1.0,
        evidence_weight=1.0,
        final_weight=final_weight,
        confirmed_moves=list(confirmed_moves or []),
        assumed_moves=list(assumed_moves or []),
        source="test",
    )


def _world(
    *,
    label: str,
    weight: float,
    species: str = "Great Tusk",
    known_moves: list[str],
    assumed_moves: list[str],
    item: str | None = None,
    ability: str | None = None,
    tera_type: str | None = None,
) -> OpponentWorld:
    candidate = _candidate(
        label=label,
        species=species,
        moves=list(known_moves) + list(assumed_moves),
        confirmed_moves=known_moves,
        assumed_moves=assumed_moves,
        item=item,
        ability=ability,
        tera_type=tera_type,
        final_weight=weight,
    )
    return OpponentWorld(
        species=species,
        candidate=candidate,
        weight=weight,
        known_moves=list(known_moves),
        assumed_moves=list(assumed_moves),
        assumed_item=item,
        assumed_ability=ability,
        assumed_tera_type=tera_type,
        assumed_spread_label="test-spread",
        notes=[],
    )


def test_build_opponent_worlds_preserves_confirmed_vs_assumed_move_split() -> None:
    state = _test_state()

    inference = InferenceResult(
        species="Great Tusk",
        candidates=[
            _candidate(
                label="gt-booster",
                moves=["Headlong Rush", "Rapid Spin", "Ice Spinner", "Bulk Up"],
                confirmed_moves=["Headlong Rush"],
                assumed_moves=["Rapid Spin", "Ice Spinner", "Bulk Up"],
                item="Booster Energy",
                ability="Protosynthesis",
                tera_type="Steel",
                final_weight=0.8,
            ),
            _candidate(
                label="gt-boots",
                moves=["Headlong Rush", "Rapid Spin", "Stealth Rock", "Knock Off"],
                confirmed_moves=["Headlong Rush"],
                assumed_moves=["Rapid Spin", "Stealth Rock", "Knock Off"],
                item="Heavy-Duty Boots",
                ability="Protosynthesis",
                tera_type="Water",
                final_weight=0.2,
            ),
        ],
        confidence_label="medium",
        notes=[],
    )

    worlds = build_opponent_worlds(state=state, inference_result=inference)

    assert len(worlds) == 2
    assert worlds[0].known_moves == ["Headlong Rush"]
    assert "Rapid Spin" in worlds[0].assumed_moves
    assert worlds[0].assumed_item in {"Booster Energy", "Heavy-Duty Boots"}


def test_aggregate_world_evaluations_respects_world_weights() -> None:
    world_a = _world(
        label="world-a",
        weight=0.75,
        known_moves=["Headlong Rush"],
        assumed_moves=["Rapid Spin"],
        item="Booster Energy",
        ability="Protosynthesis",
    )
    world_b = _world(
        label="world-b",
        weight=0.25,
        known_moves=["Headlong Rush"],
        assumed_moves=["Stealth Rock"],
        item="Heavy-Duty Boots",
        ability="Protosynthesis",
    )

    evaluations = [
        ActionWorldEvaluation(
            world=world_a,
            expected_score=20.0,
            worst_score=10.0,
            best_score=30.0,
            response_breakdown=[],
            notes=[],
        ),
        ActionWorldEvaluation(
            world=world_b,
            expected_score=0.0,
            worst_score=-5.0,
            best_score=8.0,
            response_breakdown=[],
            notes=[],
        ),
    ]

    aggregated = aggregate_world_evaluations(evaluations)

    assert aggregated.expected_score == 15.0
    assert aggregated.worst_score == -5.0
    assert aggregated.best_score == 30.0
    assert 0.0 <= aggregated.stability <= 1.0


def test_evaluate_action_in_world_returns_response_breakdown_and_ordered_scores() -> None:
    state = _test_state()
    my_action = MoveAction(
        move_name="Earthquake",
        move_type="Ground",
        move_category="physical",
        base_power=100,
        priority=0,
    )
    world = _world(
        label="gt-leftovers",
        weight=1.0,
        known_moves=["Headlong Rush"],
        assumed_moves=["Rapid Spin", "Stealth Rock", "Bulk Up"],
        item="Leftovers",
        ability="Protosynthesis",
    )

    evaluation = evaluate_action_in_world(
        state=state,
        my_action=my_action,
        world=world,
        all_worlds=[world],
    )

    assert evaluation.response_breakdown
    assert evaluation.worst_score <= evaluation.expected_score <= evaluation.best_score
    assert any("gt-leftovers" in note for note in evaluation.notes)


def test_top_influential_world_prefers_highest_weight_world() -> None:
    world_a = _world(
        label="world-a",
        weight=0.30,
        known_moves=["Headlong Rush"],
        assumed_moves=["Rapid Spin"],
    )
    world_b = _world(
        label="world-b",
        weight=0.70,
        known_moves=["Headlong Rush"],
        assumed_moves=["Stealth Rock"],
    )

    evaluations = [
        ActionWorldEvaluation(
            world=world_a,
            expected_score=5.0,
            worst_score=0.0,
            best_score=10.0,
            response_breakdown=[],
            notes=[],
        ),
        ActionWorldEvaluation(
            world=world_b,
            expected_score=4.0,
            worst_score=-2.0,
            best_score=8.0,
            response_breakdown=[],
            notes=[],
        ),
    ]

    label, weight = top_influential_world(evaluations)
    assert label == "world-b"
    assert weight == 0.70


def test_estimate_lookahead_bonus_returns_branch_notes_and_finite_value() -> None:
    state = _test_state()
    my_action = MoveAction(
        move_name="Earthquake",
        move_type="Ground",
        move_category="physical",
        base_power=100,
        priority=0,
    )

    world_primary = _world(
        label="gt-rapid-spin",
        weight=0.65,
        known_moves=["Headlong Rush"],
        assumed_moves=["Rapid Spin", "Stealth Rock"],
        item="Leftovers",
        ability="Protosynthesis",
    )
    world_secondary = _world(
        label="gt-bulk-up",
        weight=0.35,
        known_moves=["Headlong Rush"],
        assumed_moves=["Bulk Up", "Ice Spinner"],
        item="Booster Energy",
        ability="Protosynthesis",
    )

    bonus, notes = estimate_lookahead_bonus(
        state=state,
        my_action=my_action,
        world=world_primary,
        all_worlds=[world_primary, world_secondary],
        response_limit=2,
        continuation_discount=0.35,
    )

    assert isinstance(bonus, float)
    assert notes
    assert any("Lookahead branch" in note or "Discounted shallow-lookahead bonus" in note for note in notes)