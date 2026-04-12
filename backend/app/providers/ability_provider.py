from __future__ import annotations

from typing import Any, Dict, Optional

from app.providers.canonical_loader import load_abilities_data
from app.providers.provider_utils import build_name_index
from app.services.name_normalize import normalize_key

_abilities_index: Dict[str, str] | None = None


def load_abilities_data_map() -> Dict[str, Any]:
    return load_abilities_data()


def get_abilities_index() -> Dict[str, str]:
    global _abilities_index
    if _abilities_index is None:
        _abilities_index = build_name_index(list(load_abilities_data_map().keys()))
    return _abilities_index


def resolve_ability_name(name: str) -> str | None:
    return get_abilities_index().get(normalize_key(name))


def get_ability_data(name: str) -> Optional[Dict[str, Any]]:
    abilities = load_abilities_data_map()
    resolved = resolve_ability_name(name)
    if resolved is None:
        return None
    return abilities.get(resolved)