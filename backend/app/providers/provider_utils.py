from __future__ import annotations

from typing import Dict, List

from app.services.name_normalize import normalize_key


def build_name_index(names: list[str]) -> Dict[str, str]:
    return {
        normalize_key(name): name
        for name in names
    }


def search_keys(index: Dict[str, str], query: str, limit: int = 10) -> List[str]:
    q = normalize_key(query)
    if not q:
        return []

    starts: List[str] = []
    contains: List[str] = []

    for norm, canonical in index.items():
        if norm.startswith(q):
            starts.append(canonical)
        elif q in norm:
            contains.append(canonical)

    starts.sort()
    contains.sort()

    return (starts + contains)[:limit]