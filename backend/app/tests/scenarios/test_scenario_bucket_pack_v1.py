from __future__ import annotations

from dataclasses import dataclass

from app.domain.battle_state import (
    BattleState,
    FieldState,
    FormatContext,
    PokemonState,
    SideConditions,
    SideState,
)
from app.engine.evaluation_engine import evaluate_battle_state


@dataclass
class ScenarioMove:
    name: str
    type: str
    category: str
    power: int
    priority: int = 0


def _pokemon(
    *,
    species: str,
    types: list[str],
    hp: float = 100,
    current_hp: float = 100,
    atk: float = 100,
    def_: float = 100,
    spa: float = 100,
    spd: float = 100,
    spe: float = 100,
    level: int = 100,
    revealed_moves: list[str] | None = None,
) -> PokemonState:
    return PokemonState(
        species=species,
        types=types,
        hp=hp,
        current_hp=current_hp,
        atk=atk,
        def_=def_,
        spa=spa,
        spd=spd,
        spe=spe,
        level=level,
        revealed_moves=list(revealed_moves or []),
    )


def _state(
    *,
    my_active: PokemonState,
    opponent_active: PokemonState,
    my_bench: list[PokemonState],
    opponent_bench: list[PokemonState],
    moves: list[ScenarioMove],
    my_side_conditions: SideConditions | None = None,
    opponent_side_conditions: SideConditions | None = None,
) -> BattleState:
    return BattleState(
        my_side=SideState(
            active=my_active,
            bench=my_bench,
            side_conditions=my_side_conditions or SideConditions(),
        ),
        opponent_side=SideState(
            active=opponent_active,
            bench=opponent_bench,
            side_conditions=opponent_side_conditions or SideConditions(),
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


def _evaluate(state: BattleState) -> tuple[str, float, list[dict], str, list[str]]:
    return evaluate_battle_state(state)


def test_scn_hz_02_hazard_tax_discourages_repeated_switching() -> None:
    """
    Bucket: Hazard / Positioning Value
    Idea: when my side is heavily punished by hazards, Espurr should not casually
    put a switch action on top over reasonable in-place moves.
    """
    state = _state(
        my_active=_pokemon(
            species="Dragonite",
            types=["Dragon", "Flying"],
            atk=134,
            def_=95,
            spa=100,
            spd=100,
            spe=80,
        ),
        opponent_active=_pokemon(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            revealed_moves=["Headlong Rush"],
        ),
        my_bench=[
            _pokemon(species="Zapdos", types=["Electric", "Flying"], spa=125, spe=100),
            _pokemon(species="Kingambit", types=["Dark", "Steel"], atk=135, def_=120, spe=50),
        ],
        opponent_bench=[
            _pokemon(species="Gholdengo", types=["Steel", "Ghost"], spa=133, spe=84),
            _pokemon(species="Rillaboom", types=["Grass"], atk=125, spe=85),
        ],
        moves=[
            ScenarioMove(name="Dragon Dance", type="Dragon", category="Status", power=0),
            ScenarioMove(name="Earthquake", type="Ground", category="Physical", power=100),
            ScenarioMove(name="Extreme Speed", type="Normal", category="Physical", power=80, priority=2),
            ScenarioMove(name="Roost", type="Flying", category="Status", power=0),
        ],
        my_side_conditions=SideConditions(
            stealth_rock=True,
            spikes_layers=2,
        ),
    )

    best_action, _, ranked_actions, _, _ = _evaluate(state)

    assert ranked_actions
    assert not best_action.startswith("Zapdos")
    assert not best_action.startswith("Kingambit")


def test_scn_st_01_setup_opportunity_keeps_setup_line_competitive() -> None:
    """
    Bucket: Setup / Tempo
    Idea: on a board where the active threat can potentially exploit momentum,
    setup should remain a competitive line instead of always being buried.
    """
    state = _state(
        my_active=_pokemon(
            species="Dragonite",
            types=["Dragon", "Flying"],
            atk=134,
            def_=95,
            spa=100,
            spd=100,
            spe=80,
        ),
        opponent_active=_pokemon(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            current_hp=55,
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            revealed_moves=["Rapid Spin"],
        ),
        my_bench=[
            _pokemon(species="Zapdos", types=["Electric", "Flying"], spa=125, spe=100),
        ],
        opponent_bench=[
            _pokemon(species="Gholdengo", types=["Steel", "Ghost"], spa=133, spe=84),
            _pokemon(species="Rillaboom", types=["Grass"], atk=125, spe=85),
        ],
        moves=[
            ScenarioMove(name="Dragon Dance", type="Dragon", category="Status", power=0),
            ScenarioMove(name="Earthquake", type="Ground", category="Physical", power=100),
            ScenarioMove(name="Extreme Speed", type="Normal", category="Physical", power=80, priority=2),
            ScenarioMove(name="Roost", type="Flying", category="Status", power=0),
        ],
    )

    _, _, ranked_actions, _, _ = _evaluate(state)
    top_two_names = [entry["name"] for entry in ranked_actions[:2]]

    assert ranked_actions
    assert "Dragon Dance" in top_two_names


def test_scn_sw_03_immunity_safe_line_should_beat_obvious_ground_commitment() -> None:
    """
    Bucket: Defensive Pivots / Switch Prediction
    Idea: if the opponent has an obvious Ground-immune pivot in the back,
    blindly committing to Earthquake should not dominate the recommendation.
    """
    state = _state(
        my_active=_pokemon(
            species="Dragonite",
            types=["Dragon", "Flying"],
            atk=134,
            def_=95,
            spa=100,
            spd=100,
            spe=80,
        ),
        opponent_active=_pokemon(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            revealed_moves=["Headlong Rush"],
        ),
        my_bench=[
            _pokemon(species="Zapdos", types=["Electric", "Flying"], spa=125, spe=100),
        ],
        opponent_bench=[
            _pokemon(species="Gholdengo", types=["Steel", "Ghost"], spa=133, spe=84),
        ],
        moves=[
            ScenarioMove(name="Earthquake", type="Ground", category="Physical", power=100),
            ScenarioMove(name="Dragon Dance", type="Dragon", category="Status", power=0),
            ScenarioMove(name="Extreme Speed", type="Normal", category="Physical", power=80, priority=2),
            ScenarioMove(name="Roost", type="Flying", category="Status", power=0),
        ],
    )

    best_action, _, ranked_actions, _, _ = _evaluate(state)

    assert ranked_actions
    # This is deliberately a strong competitive expectation.
    # If it fails, that likely points to weak pivot / immunity-switch modeling.
    assert best_action != "Earthquake"


def test_scn_ru_04_more_stable_line_can_outrank_flashier_line() -> None:
    """
    Bucket: Risk / Uncertainty Handling
    Idea: if two lines are close, the engine should be able to reward a more stable line.
    """
    state = _state(
        my_active=_pokemon(
            species="Dragonite",
            types=["Dragon", "Flying"],
            current_hp=60,
            atk=134,
            def_=95,
            spa=100,
            spd=100,
            spe=80,
        ),
        opponent_active=_pokemon(
            species="Great Tusk",
            types=["Ground", "Fighting"],
            current_hp=70,
            atk=131,
            def_=131,
            spa=53,
            spd=53,
            spe=87,
            revealed_moves=["Headlong Rush"],
        ),
        my_bench=[
            _pokemon(species="Kingambit", types=["Dark", "Steel"], atk=135, def_=120, spe=50),
        ],
        opponent_bench=[
            _pokemon(species="Gholdengo", types=["Steel", "Ghost"], spa=133, spe=84),
            _pokemon(species="Rillaboom", types=["Grass"], atk=125, spe=85),
        ],
        moves=[
            ScenarioMove(name="Dragon Dance", type="Dragon", category="Status", power=0),
            ScenarioMove(name="Earthquake", type="Ground", category="Physical", power=100),
            ScenarioMove(name="Extreme Speed", type="Normal", category="Physical", power=80, priority=2),
            ScenarioMove(name="Roost", type="Flying", category="Status", power=0),
        ],
    )

    _, _, ranked_actions, _, _ = _evaluate(state)

    by_name = {entry["name"]: entry for entry in ranked_actions}
    assert "Roost" in by_name
    assert "Dragon Dance" in by_name

    # This is a relatively soft stability-oriented regression check.
    assert by_name["Roost"]["stability"] >= by_name["Dragon Dance"]["stability"]