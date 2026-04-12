from __future__ import annotations

from typing import Any, Dict, Optional

from app.providers.canonical_loader import load_items_data
from app.providers.provider_utils import build_name_index
from app.services.name_normalize import normalize_key

_items_index: Dict[str, str] | None = None


def load_items_data_map() -> Dict[str, Any]:
    return load_items_data()


def get_items_index() -> Dict[str, str]:
    global _items_index
    if _items_index is None:
        _items_index = build_name_index(list(load_items_data_map().keys()))
    return _items_index


def resolve_item_name(name: str) -> str | None:
    return get_items_index().get(normalize_key(name))


def get_item_data(name: str) -> Optional[Dict[str, Any]]:
    items = load_items_data_map()
    resolved = resolve_item_name(name)
    if resolved is None:
        return None
    return items.get(resolved)