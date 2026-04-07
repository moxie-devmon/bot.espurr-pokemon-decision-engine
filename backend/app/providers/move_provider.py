from __future__ import annotations

import json
from typing import Any, Dict, Optional

from app.domain.actions import MoveAction
from app.providers.provider_utils import MOVES_PATH
from app.services.name_normalize import normalize_key

_moves_cache: Dict[str, Any] | None = None
_moves_index: Dict[str, str] | None = None


def load_moves_data() -> Dict[str, Any]:
    global _moves_cache, _moves_index

    if _moves_cache is None:
        with open(MOVES_PATH, "r", encoding="utf-8") as f:
            _moves_cache = json.load(f)

        _moves_index = {
            normalize_key(name): name
            for name in _moves_cache.keys()
        }

    return _moves_cache


def get_moves_index() -> Dict[str, str]:
    load_moves_data()
    assert _moves_index is not None
    return _moves_index


def resolve_move_name(name: str) -> str | None:
    index = get_moves_index()
    return index.get(normalize_key(name))


def get_move_data(name: str) -> Optional[Dict[str, Any]]:
    moves = load_moves_data()
    resolved = resolve_move_name(name)
    if resolved is None:
        return None
    return moves.get(resolved)


def build_move_action_from_name(name: str) -> MoveAction | None:
    move_data = get_move_data(name)
    if move_data is None:
        return None

    resolved_name = resolve_move_name(name) or name

    move_type = move_data.get("type") or "Normal"
    category = (move_data.get("category") or "Physical").lower()
    if category not in {"physical", "special", "status"}:
        category = "physical"

    base_power = int(move_data.get("power") or 0)
    priority = int(move_data.get("priority") or 0)

    return MoveAction(
        move_name=resolved_name,
        move_type=move_type,
        move_category=category,
        base_power=base_power,
        priority=priority,
    )