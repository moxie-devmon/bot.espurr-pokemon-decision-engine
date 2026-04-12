from __future__ import annotations

from typing import Any, Dict

from app.providers.canonical_loader import load_type_chart_data


def load_type_chart() -> Dict[str, Any]:
    return load_type_chart_data()