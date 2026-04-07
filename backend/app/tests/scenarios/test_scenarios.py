from app.domain.actions import MoveAction
from app.domain.battle_state import (
    BattleState,
    FieldState,
    FormatContext,
    PokemonState,
    SideConditions,
    SideState,
    StatBoosts,
)
from app.engine.projection_engine import project_action_against_response
from app.inference.models import CandidateSet, OpponentResponse, OpponentWorld


def _move_action(
    name: str,
    move_type: str,
    category: str,
    power: int,
    priority: int = 0,
) -> MoveAction:
    return MoveAction(
        move_name=name,
        move_type=move_type,
        move_category=category,
        base_power=power,
        priority=priority,
    )


def _basic_state(
    *,
    my_active: PokemonState,
    opp_active: PokemonState,
    my_bench: list[PokemonState] | None = None,
    opp_bench: list[PokemonState] | None = None,
) -> BattleState:
    return BattleState(
        my_side=SideState(
            active=my_active,
            bench=my_bench or [],
            side_conditions=SideConditions(),
        ),
        opponent_side=SideState(
            active=opp_active,
            bench=opp_bench or [],
            side_conditions=SideConditions(),
        ),
        moves=[],
        field=FieldState(),
        format_context=FormatContext(generation=9, format_name="gen9ou", ruleset=[]),
    )


def test_levitate_blocks_ground_projection():
    state = _basic_state(
        my_active=PokemonState(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
        opp_active=PokemonState(
            species="Rotom-Wash",
            types=["Electric", "Water"],
            atk=65,
            def_=107,
            spa=105,
            spd=107,
            spe=86,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
    )

    world = OpponentWorld(
        species="Rotom-Wash",
        candidate=CandidateSet(
            species="Rotom-Wash",
            label="levitate-set",
            moves=["Hydro Pump", "Volt Switch"],
            ability="Levitate",
            weight=1.0,
            source="test",
        ),
        weight=1.0,
        known_moves=[],
        assumed_moves=["Hydro Pump", "Volt Switch"],
        assumed_item=None,
        assumed_ability="Levitate",
        assumed_tera_type=None,
        notes=[],
    )

    response = OpponentResponse(
        kind="move",
        label="move::Hydro Pump",
        weight=1.0,
        move_name="Hydro Pump",
        move_type="Water",
        move_category="special",
        base_power=110,
        priority=0,
        notes=[],
    )

    my_action = _move_action("Headlong Rush", "Ground", "physical", 120)

    projection = project_action_against_response(
        state=state,
        my_action=my_action,
        response=response,
        world=world,
    )

    assert projection.opp_hp_after == projection.opp_hp_before
    assert any("Levitate" in note or "immunity" in note.lower() for note in projection.notes)


def test_choice_scarf_changes_projected_order():
    state = _basic_state(
        my_active=PokemonState(
            species="Gholdengo",
            types=["Steel", "Ghost"],
            atk=60,
            def_=95,
            spa=133,
            spd=91,
            spe=84,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
        opp_active=PokemonState(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
    )

    world = OpponentWorld(
        species="Great Tusk",
        candidate=CandidateSet(
            species="Great Tusk",
            label="scarf-set",
            moves=["Headlong Rush"],
            item="Choice Scarf",
            weight=1.0,
            source="test",
        ),
        weight=1.0,
        known_moves=[],
        assumed_moves=["Headlong Rush"],
        assumed_item="Choice Scarf",
        assumed_ability=None,
        assumed_tera_type=None,
        notes=[],
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

    my_action = _move_action("Shadow Ball", "Ghost", "special", 80)

    projection = project_action_against_response(
        state=state,
        my_action=my_action,
        response=response,
        world=world,
    )

    assert projection.order_context == "attacker_second"
    assert any("Choice Scarf" in note for note in projection.notes)


def test_focus_sash_prevents_projected_ko():
    state = _basic_state(
        my_active=PokemonState(
            species="Chien-Pao",
            types=["Dark", "Ice"],
            atk=135,
            def_=80,
            spa=90,
            spd=65,
            spe=135,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
        opp_active=PokemonState(
            species="Alakazam",
            types=["Psychic"],
            atk=50,
            def_=45,
            spa=135,
            spd=95,
            spe=120,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
    )

    world = OpponentWorld(
        species="Alakazam",
        candidate=CandidateSet(
            species="Alakazam",
            label="sash-set",
            moves=["Psychic"],
            item="Focus Sash",
            weight=1.0,
            source="test",
        ),
        weight=1.0,
        known_moves=[],
        assumed_moves=["Psychic"],
        assumed_item="Focus Sash",
        assumed_ability=None,
        assumed_tera_type=None,
        notes=[],
    )

    response = OpponentResponse(
        kind="move",
        label="move::Psychic",
        weight=1.0,
        move_name="Psychic",
        move_type="Psychic",
        move_category="special",
        base_power=90,
        priority=0,
        notes=[],
    )

    # Deliberately oversized to guarantee a lethal line in this simplified engine.
    my_action = _move_action("Night Slash", "Dark", "physical", 300)

    projection = project_action_against_response(
        state=state,
        my_action=my_action,
        response=response,
        world=world,
    )

    assert projection.opp_hp_after == 1.0
    assert not projection.opp_fainted
    assert any("Focus Sash" in note or "survive at 1 HP" in note for note in projection.notes)


def test_leftovers_applies_end_of_line_recovery():
    state = _basic_state(
        my_active=PokemonState(
            species="Zapdos",
            types=["Electric", "Flying"],
            atk=90,
            def_=85,
            spa=95,   # lowered to avoid accidental KO
            spd=90,
            spe=100,
            hp=100,
            current_hp=100,
            boosts=StatBoosts(),
        ),
        opp_active=PokemonState(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            atk=131,
            def_=160,  # boosted bulk to ensure survival
            spa=53,
            spd=120,   # boosted special bulk too
            spe=87,
            hp=140,    # boosted max HP
            current_hp=140,
            boosts=StatBoosts(),
        ),
    )

    response = OpponentResponse(
        kind="move",
        label="move::Ice Spinner",
        weight=1.0,
        move_name="Ice Spinner",
        move_type="Ice",
        move_category="physical",
        base_power=80,
        priority=0,
        notes=[],
    )

    my_action = _move_action("Air Slash", "Flying", "special", 40)

    world_without_leftovers = OpponentWorld(
        species="Great Tusk",
        candidate=CandidateSet(
            species="Great Tusk",
            label="no-item-set",
            moves=["Ice Spinner"],
            item=None,
            weight=1.0,
            source="test",
        ),
        weight=1.0,
        known_moves=[],
        assumed_moves=["Ice Spinner"],
        assumed_item=None,
        assumed_ability=None,
        assumed_tera_type=None,
        notes=[],
    )

    world_with_leftovers = OpponentWorld(
        species="Great Tusk",
        candidate=CandidateSet(
            species="Great Tusk",
            label="leftovers-set",
            moves=["Ice Spinner"],
            item="Leftovers",
            weight=1.0,
            source="test",
        ),
        weight=1.0,
        known_moves=[],
        assumed_moves=["Ice Spinner"],
        assumed_item="Leftovers",
        assumed_ability=None,
        assumed_tera_type=None,
        notes=[],
    )

    projection_without = project_action_against_response(
        state=state,
        my_action=my_action,
        response=response,
        world=world_without_leftovers,
    )

    projection_with = project_action_against_response(
        state=state,
        my_action=my_action,
        response=response,
        world=world_with_leftovers,
    )

    assert projection_without.opp_hp_after > 0
    assert projection_with.opp_hp_after > projection_without.opp_hp_after
    assert any("Leftovers" in note for note in projection_with.notes)