from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANONICAL_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "canonical"

_species_cache: dict[str, Any] | None = None
_moves_cache: dict[str, Any] | None = None
_items_cache: dict[str, Any] | None = None
_abilities_cache: dict[str, Any] | None = None
_type_chart_cache: dict[str, Any] | None = None
_natures_cache: dict[str, Any] | None = None
_formats_cache: dict[str, Any] | None = None
_field_effects_cache: dict[str, Any] | None = None
_statuses_cache: dict[str, Any] | None = None


def _load_json(filename: str) -> dict[str, Any]:
    path = CANONICAL_DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw:
        raise ValueError(f"Canonical data file is empty: {path}")

    return json.loads(raw)


def load_species_data() -> dict[str, Any]:
    global _species_cache
    if _species_cache is None:
        _species_cache = _load_json("species.json")
    return _species_cache


def load_moves_data() -> dict[str, Any]:
    global _moves_cache
    if _moves_cache is None:
        _moves_cache = _load_json("moves.json")
    return _moves_cache


def load_items_data() -> dict[str, Any]:
    global _items_cache
    if _items_cache is None:
        _items_cache = _load_json("items.json")
    return _items_cache


def load_abilities_data() -> dict[str, Any]:
    global _abilities_cache
    if _abilities_cache is None:
        _abilities_cache = _load_json("abilities.json")
    return _abilities_cache


def load_type_chart_data() -> dict[str, Any]:
    global _type_chart_cache
    if _type_chart_cache is None:
        _type_chart_cache = _load_json("type_chart.json")
    return _type_chart_cache


def load_natures_data() -> dict[str, Any]:
    global _natures_cache
    if _natures_cache is None:
        _natures_cache = _load_json("natures.json")
    return _natures_cache


def load_formats_data() -> dict[str, Any]:
    global _formats_cache
    if _formats_cache is None:
        _formats_cache = _load_json("formats.json")
    return _formats_cache


def load_field_effects_data() -> dict[str, Any]:
    global _field_effects_cache
    if _field_effects_cache is None:
        _field_effects_cache = _load_json("field_effects.json")
    return _field_effects_cache


def load_statuses_data() -> dict[str, Any]:
    global _statuses_cache
    if _statuses_cache is None:
        _statuses_cache = _load_json("statuses.json")
    return _statuses_cache