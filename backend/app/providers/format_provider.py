from __future__ import annotations

from typing import Any, Dict, Optional

from app.providers.canonical_loader import load_formats_data


def load_format_data_map() -> Dict[str, Any]:
    return load_formats_data()


def get_format_data(format_id: str) -> Optional[Dict[str, Any]]:
    return load_format_data_map().get(format_id)