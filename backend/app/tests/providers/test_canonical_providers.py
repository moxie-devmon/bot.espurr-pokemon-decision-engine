from __future__ import annotations

from app.providers.ability_provider import get_ability_data, resolve_ability_name
from app.providers.format_provider import get_format_data
from app.providers.item_provider import get_item_data, resolve_item_name
from app.providers.move_provider import (
    build_move_action_from_name,
    get_move_data,
    resolve_move_name,
)
from app.providers.nature_provider import get_nature_data, resolve_nature_name
from app.providers.pokemon_provider import get_pokemon_data, resolve_pokemon_name
from app.providers.type_chart_provider import load_type_chart


def test_resolve_pokemon_name_great_tusk() -> None:
    assert resolve_pokemon_name("great tusk") == "Great Tusk"


def test_get_pokemon_data_great_tusk_has_core_fields() -> None:
    data = get_pokemon_data("Great Tusk")
    assert data is not None
    assert data["name"] == "Great Tusk"
    assert data["types"] == ["Ground", "Fighting"]
    assert data["base_stats"]["atk"] > 0
    assert data["base_stats"]["spe"] > 0


def test_resolve_move_name_make_it_rain() -> None:
    assert resolve_move_name("make it rain") == "Make It Rain"


def test_get_move_data_make_it_rain_has_core_fields() -> None:
    data = get_move_data("Make It Rain")
    assert data is not None
    assert data["name"] == "Make It Rain"
    assert data["type"] == "Steel"
    assert data["category"] == "Special"
    assert data["power"] > 0


def test_build_move_action_from_name_make_it_rain() -> None:
    action = build_move_action_from_name("Make It Rain")
    assert action is not None
    assert action.move_name == "Make It Rain"
    assert action.move_type == "Steel"
    assert action.move_category == "special"
    assert action.base_power > 0


def test_resolve_item_name_choice_scarf() -> None:
    assert resolve_item_name("choice scarf") == "Choice Scarf"


def test_get_item_data_choice_scarf_exists() -> None:
    data = get_item_data("Choice Scarf")
    assert data is not None
    assert data["name"] == "Choice Scarf"


def test_resolve_ability_name_good_as_gold() -> None:
    assert resolve_ability_name("good as gold") == "Good as Gold"


def test_get_ability_data_good_as_gold_exists() -> None:
    data = get_ability_data("Good as Gold")
    assert data is not None
    assert data["name"] == "Good as Gold"


def test_resolve_nature_name_jolly() -> None:
    assert resolve_nature_name("jolly") == "Jolly"


def test_get_nature_data_jolly_has_stat_modifiers() -> None:
    data = get_nature_data("Jolly")
    assert data is not None
    assert data["name"] == "Jolly"
    assert data["plus"] == "spe"
    assert data["minus"] == "spa"


def test_get_format_data_gen9ou_exists() -> None:
    data = get_format_data("gen9ou")
    assert data is not None
    assert data["format_id"] == "gen9ou"
    assert data["generation"] == 9
    assert data["tera_allowed"] is True


def test_load_type_chart_has_basic_entries() -> None:
    chart = load_type_chart()
    assert chart
    assert "Fire" in chart
    assert "Water" in chart


def test_unknown_pokemon_returns_none() -> None:
    assert resolve_pokemon_name("not-a-real-mon") is None
    assert get_pokemon_data("not-a-real-mon") is None


def test_unknown_move_returns_none() -> None:
    assert resolve_move_name("not-a-real-move") is None
    assert get_move_data("not-a-real-move") is None
    assert build_move_action_from_name("not-a-real-move") is None


def test_unknown_item_ability_nature_return_none() -> None:
    assert resolve_item_name("not-a-real-item") is None
    assert get_item_data("not-a-real-item") is None

    assert resolve_ability_name("not-a-real-ability") is None
    assert get_ability_data("not-a-real-ability") is None

    assert resolve_nature_name("not-a-real-nature") is None
    assert get_nature_data("not-a-real-nature") is None