from __future__ import annotations

from typing import Any, Dict, Optional

from app.providers.canonical_loader import load_natures_data
from app.providers.provider_utils import build_name_index
from app.services.name_normalize import normalize_key

_natures_index: Dict[str, str] | None = None


def load_natures_data_map() -> Dict[str, Any]:
    return load_natures_data()


def get_natures_index() -> Dict[str, str]:
    global _natures_index
    if _natures_index is None:
        _natures_index = build_name_index(list(load_natures_data_map().keys()))
    return _natures_index


def resolve_nature_name(name: str) -> str | None:
    return get_natures_index().get(normalize_key(name))


def get_nature_data(name: str) -> Optional[Dict[str, Any]]:
    natures = load_natures_data_map()
    resolved = resolve_nature_name(name)
    if resolved is None:
        return None
    return natures.get(resolved)