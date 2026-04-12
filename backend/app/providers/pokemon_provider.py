from __future__ import annotations

from typing import Any, Dict, Optional

from app.providers.canonical_loader import load_species_data
from app.providers.provider_utils import build_name_index
from app.services.name_normalize import normalize_key

_pokemon_index: Dict[str, str] | None = None


def load_pokemon_data() -> Dict[str, Any]:
    return load_species_data()


def get_pokemon_index() -> Dict[str, str]:
    global _pokemon_index
    if _pokemon_index is None:
        _pokemon_index = build_name_index(list(load_pokemon_data().keys()))
    return _pokemon_index


def resolve_pokemon_name(name: str) -> str | None:
    index = get_pokemon_index()
    return index.get(normalize_key(name))


def get_pokemon_data(name: str) -> Optional[Dict[str, Any]]:
    pokemon = load_pokemon_data()
    resolved = resolve_pokemon_name(name)
    if resolved is None:
        return None
    return pokemon.get(resolved)