from __future__ import annotations

from typing import Any, Dict, Optional

from app.domain.actions import MoveAction
from app.providers.canonical_loader import load_moves_data
from app.providers.provider_utils import build_name_index
from app.services.name_normalize import normalize_key

_moves_index: Dict[str, str] | None = None


def load_moves_data_map() -> Dict[str, Any]:
    return load_moves_data()


def get_moves_index() -> Dict[str, str]:
    global _moves_index
    if _moves_index is None:
        _moves_index = build_name_index(list(load_moves_data_map().keys()))
    return _moves_index


def resolve_move_name(name: str) -> str | None:
    index = get_moves_index()
    return index.get(normalize_key(name))


def get_move_data(name: str) -> Optional[Dict[str, Any]]:
    moves = load_moves_data_map()
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