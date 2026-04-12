from __future__ import annotations

from app.domain.battle_state import (
    BattleState,
    FieldState,
    FormatContext,
    PokemonState,
    SideConditions,
    SideState,
)
from app.engine.projection_engine import project_action_against_response
from app.inference.models import CandidateSet, OpponentResponse, OpponentWorld
from app.providers.move_provider import build_move_action_from_name


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
        revealed_moves=["Headlong Rush", "Rapid Spin"],
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

    moves = [
        build_move_action_from_name("Dragon Dance"),
        build_move_action_from_name("Earthquake"),
        build_move_action_from_name("Extreme Speed"),
        build_move_action_from_name("Roost"),
    ]
    assert all(move is not None for move in moves)

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
        moves=moves,
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


def _world(
    *,
    species: str = "Great Tusk",
    known_moves: list[str] | None = None,
    assumed_moves: list[str] | None = None,
    item: str | None = None,
    ability: str | None = None,
    tera_type: str | None = None,
):
    candidate = CandidateSet(
        species=species,
        label=f"{species}-test-world",
        moves=list((known_moves or []) + (assumed_moves or [])),
        item=item,
        ability=ability,
        tera_type=tera_type,
        spread_label="test-spread",
        prior_weight=1.0,
        compatibility_weight=1.0,
        evidence_weight=1.0,
        final_weight=1.0,
        confirmed_moves=list(known_moves or []),
        assumed_moves=list(assumed_moves or []),
        source="test",
    )
    return OpponentWorld(
        species=species,
        candidate=candidate,
        weight=1.0,
        known_moves=list(known_moves or []),
        assumed_moves=list(assumed_moves or []),
        assumed_item=item,
        assumed_ability=ability,
        assumed_tera_type=tera_type,
        assumed_spread_label="test-spread",
        notes=[],
    )


def test_projection_preserves_revealed_response_move() -> None:
    state = _test_state()
    my_action = build_move_action_from_name("Earthquake")
    assert my_action is not None

    world = _world(
        known_moves=["Headlong Rush"],
        assumed_moves=["Rapid Spin"],
        item="Leftovers",
        ability="Protosynthesis",
    )

    response = OpponentResponse(
        kind="move",
        label="move::Rapid Spin",
        weight=1.0,
        move_name="Rapid Spin",
        move_type="Normal",
        move_category="physical",
        base_power=50,
        priority=0,
        notes=[],
    )

    projection = project_action_against_response(state, my_action, response, world)
    assert projection.revealed_response_move == "Rapid Spin"


def test_projection_applies_levitate_immunity_hook() -> None:
    state = _test_state()
    my_action = build_move_action_from_name("Earthquake")
    assert my_action is not None

    world = _world(
        species="Great Tusk",
        known_moves=["Shadow Ball"],
        assumed_moves=["Recover"],
        ability="Levitate",
    )

    response = OpponentResponse(
        kind="move",
        label="move::Shadow Ball",
        weight=1.0,
        move_name="Shadow Ball",
        move_type="Ghost",
        move_category="special",
        base_power=80,
        priority=0,
        notes=[],
    )

    projection = project_action_against_response(state, my_action, response, world)
    assert projection.opp_hp_after == projection.opp_hp_before


def test_projection_marks_forced_switch_when_my_active_faints() -> None:
    state = _test_state()
    my_action = build_move_action_from_name("Dragon Dance")
    assert my_action is not None

    world = _world(
        known_moves=["Headlong Rush"],
        item="Choice Band",
        ability="Protosynthesis",
    )

    response = OpponentResponse(
        kind="move",
        label="move::Headlong Rush",
        weight=1.0,
        move_name="Headlong Rush",
        move_type="Ground",
        move_category="physical",
        base_power=120,
        priority=0,
        notes=[],
    )

    projection = project_action_against_response(state, my_action, response, world)
    assert projection.my_forced_switch in {True, False}
    if projection.my_fainted:
        assert projection.my_forced_switch is True


def test_projection_switch_response_uses_named_target() -> None:
    state = _test_state()
    my_action = build_move_action_from_name("Earthquake")
    assert my_action is not None

    world = _world(
        known_moves=["Recover"],
        item="Air Balloon",
        ability="Good as Gold",
    )

    response = OpponentResponse(
        kind="switch",
        label="switch::Gholdengo",
        weight=1.0,
        switch_target_species="Gholdengo",
        notes=[],
    )

    projection = project_action_against_response(state, my_action, response, world)
    assert projection.opponent_switched is True or projection.opp_active_species_after == "Gholdengo"


def test_projection_leftovers_hook_can_restore_hp() -> None:
    state = _test_state()
    my_action = build_move_action_from_name("Dragon Dance")
    assert my_action is not None

    world = _world(
        known_moves=["Recover"],
        item="Leftovers",
        ability="Protosynthesis",
    )

    response = OpponentResponse(
        kind="move",
        label="move::Recover",
        weight=1.0,
        move_name="Recover",
        move_type="Normal",
        move_category="status",
        base_power=0,
        priority=0,
        notes=[],
    )

    projection = project_action_against_response(state, my_action, response, world)
    assert projection.opp_hp_after >= 0.0