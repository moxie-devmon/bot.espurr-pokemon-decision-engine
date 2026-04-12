from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
LEGACY_DATA_DIR = ROOT / "data_legacy_bootstrap"
CANONICAL_DATA_DIR = ROOT / "app" / "data" / "canonical"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False, sort_keys=True)


def _extract_base_stats(data: dict[str, Any]) -> dict[str, int]:
    candidates = [
        data.get("baseStats"),
        data.get("base_stats"),
        data.get("stats"),
        data.get("base"),
    ]

    stats: dict[str, Any] = {}
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            stats = candidate
            break

    return {
        "hp": int(stats.get("hp", data.get("hp", 0)) or 0),
        "atk": int(stats.get("atk", data.get("atk", 0)) or 0),
        "def": int(stats.get("def", data.get("def", 0)) or 0),
        "spa": int(stats.get("spa", data.get("spa", 0)) or 0),
        "spd": int(stats.get("spd", data.get("spd", 0)) or 0),
        "spe": int(stats.get("spe", data.get("spe", 0)) or 0),
    }


def _extract_abilities(data: dict[str, Any]) -> dict[str, Any]:
    abilities = data.get("abilities", {})
    if isinstance(abilities, dict):
        return {
            "0": abilities.get("0"),
            "1": abilities.get("1"),
            "H": abilities.get("H"),
            "S": abilities.get("S"),
        }

    if isinstance(abilities, list):
        result: dict[str, Any] = {}
        for idx, ability in enumerate(abilities):
            if idx == 0:
                result["0"] = ability
            elif idx == 1:
                result["1"] = ability
        return result

    return {"0": None, "1": None, "H": None, "S": None}


def _bootstrap_species(legacy_pokemon: dict[str, Any]) -> dict[str, Any]:
    species: dict[str, Any] = {}

    for name, data in legacy_pokemon.items():
        species[name] = {
            "name": name,
            "num": data.get("num"),
            "types": list(data.get("types", [])),
            "base_stats": _extract_base_stats(data),
            "abilities": _extract_abilities(data),
            "weightkg": data.get("weightkg"),
            "forme": data.get("forme"),
            "base_species": data.get("baseSpecies"),
        }

    return species

def _canonical_move_category(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if text == "physical":
        return "Physical"
    if text == "special":
        return "Special"
    if text == "status":
        return "Status"
    return str(value)


def _bootstrap_moves(legacy_moves: dict[str, Any]) -> dict[str, Any]:
    moves: dict[str, Any] = {}

    for name, data in legacy_moves.items():
        moves[name] = {
            "name": name,
            "type": data.get("type"),
            "category": _canonical_move_category(data.get("category")),
            "power": int(data.get("power", 0) or 0),
            "accuracy": data.get("accuracy"),
            "pp": data.get("pp"),
            "priority": int(data.get("priority", 0) or 0),
            "target": data.get("target"),
            "flags": dict(data.get("flags", {})),
            "drain": data.get("drain"),
            "recoil": data.get("recoil"),
            "heal": data.get("heal"),
            "multihit": data.get("multihit"),
            "self_switch": data.get("selfSwitch"),
            "status": data.get("status"),
            "volatile_status": data.get("volatileStatus"),
            "weather": data.get("weather"),
            "terrain": data.get("terrain"),
            "breaks_protect": data.get("breaksProtect", False),
            "thaws_target": data.get("thawsTarget", False),
            "will_crit": data.get("willCrit", False),
        }

    return moves

def _bootstrap_type_chart(legacy_type_chart: dict[str, Any]) -> dict[str, Any]:
    return legacy_type_chart


def _bootstrap_items() -> dict[str, Any]:
    return {
        "Air Balloon": {"name": "Air Balloon", "effect_family": "ground_immunity"},
        "Assault Vest": {"name": "Assault Vest", "effect_family": "special_bulk"},
        "Black Glasses": {"name": "Black Glasses", "effect_family": "type_boost_dark"},
        "Booster Energy": {"name": "Booster Energy", "effect_family": "quark_proto_boost"},
        "Choice Band": {"name": "Choice Band", "effect_family": "choice_attack"},
        "Choice Scarf": {"name": "Choice Scarf", "effect_family": "choice_speed"},
        "Choice Specs": {"name": "Choice Specs", "effect_family": "choice_special_attack"},
        "Focus Sash": {"name": "Focus Sash", "effect_family": "survive_at_1hp"},
        "Grassy Seed": {"name": "Grassy Seed", "effect_family": "terrain_seed"},
        "Heavy-Duty Boots": {"name": "Heavy-Duty Boots", "effect_family": "ignore_hazards"},
        "Leftovers": {"name": "Leftovers", "effect_family": "end_of_turn_recovery"},
        "Life Orb": {"name": "Life Orb", "effect_family": "damage_boost_recoil"},
        "Loaded Dice": {"name": "Loaded Dice", "effect_family": "multihit_bias"},
        "Lum Berry": {"name": "Lum Berry", "effect_family": "status_cure_once"},
        "Metal Coat": {"name": "Metal Coat", "effect_family": "type_boost_steel"},
        "Miracle Seed": {"name": "Miracle Seed", "effect_family": "type_boost_grass"},
        "Rocky Helmet": {"name": "Rocky Helmet", "effect_family": "contact_chip"},
        "Shuca Berry": {"name": "Shuca Berry", "effect_family": "ground_resist_once"},
        "Silk Scarf": {"name": "Silk Scarf", "effect_family": "type_boost_normal"},
        "Terrain Extender": {"name": "Terrain Extender", "effect_family": "extend_terrain"},
    }


def _bootstrap_abilities() -> dict[str, Any]:
    return {
        "Contrary": {"name": "Contrary", "effect_family": "stat_inversion"},
        "Defiant": {"name": "Defiant", "effect_family": "stat_drop_punish"},
        "Good as Gold": {"name": "Good as Gold", "effect_family": "status_immunity"},
        "Grassy Surge": {"name": "Grassy Surge", "effect_family": "set_terrain"},
        "Inner Focus": {"name": "Inner Focus", "effect_family": "flinch_immunity"},
        "Intimidate": {"name": "Intimidate", "effect_family": "attack_drop_on_switchin"},
        "Levitate": {"name": "Levitate", "effect_family": "ground_immunity"},
        "Multiscale": {"name": "Multiscale", "effect_family": "full_hp_damage_reduction"},
        "Overgrow": {"name": "Overgrow", "effect_family": "low_hp_type_boost"},
        "Pressure": {"name": "Pressure", "effect_family": "pp_pressure"},
        "Protosynthesis": {"name": "Protosynthesis", "effect_family": "sun_or_booster_boost"},
        "Supreme Overlord": {"name": "Supreme Overlord", "effect_family": "ally_faint_boost"},
    }


def _bootstrap_natures() -> dict[str, Any]:
    raw = {
        "Adamant": {"plus": "atk", "minus": "spa"},
        "Bashful": {"plus": None, "minus": None},
        "Bold": {"plus": "def", "minus": "atk"},
        "Brave": {"plus": "atk", "minus": "spe"},
        "Calm": {"plus": "spd", "minus": "atk"},
        "Careful": {"plus": "spd", "minus": "spa"},
        "Docile": {"plus": None, "minus": None},
        "Gentle": {"plus": "spd", "minus": "def"},
        "Hardy": {"plus": None, "minus": None},
        "Hasty": {"plus": "spe", "minus": "def"},
        "Impish": {"plus": "def", "minus": "spa"},
        "Jolly": {"plus": "spe", "minus": "spa"},
        "Lax": {"plus": "def", "minus": "spd"},
        "Lonely": {"plus": "atk", "minus": "def"},
        "Mild": {"plus": "spa", "minus": "def"},
        "Modest": {"plus": "spa", "minus": "atk"},
        "Naive": {"plus": "spe", "minus": "spd"},
        "Naughty": {"plus": "atk", "minus": "spd"},
        "Quiet": {"plus": "spa", "minus": "spe"},
        "Quirky": {"plus": None, "minus": None},
        "Rash": {"plus": "spa", "minus": "spd"},
        "Relaxed": {"plus": "def", "minus": "spe"},
        "Sassy": {"plus": "spd", "minus": "spe"},
        "Serious": {"plus": None, "minus": None},
        "Timid": {"plus": "spe", "minus": "atk"},
    }
    return {
        name: {"name": name, **payload}
        for name, payload in raw.items()
    }


def _bootstrap_formats() -> dict[str, Any]:
    return {
        "gen9ou": {
            "format_id": "gen9ou",
            "display_name": "Gen 9 OU",
            "generation": 9,
            "battle_type": "singles",
            "tera_allowed": True,
            "rules": [
                "Species Clause",
                "Sleep Moves Clause",
                "Evasion Moves Clause",
                "OHKO Clause",
                "Endless Battle Clause",
            ],
        }
    }


def _bootstrap_field_effects() -> dict[str, Any]:
    return {
        "weathers": {
            "sun": {},
            "rain": {},
            "sand": {},
            "snow": {},
        },
        "terrains": {
            "electric": {},
            "grassy": {},
            "misty": {},
            "psychic": {},
        },
        "side_conditions": {
            "stealthrock": {},
            "spikes": {},
            "toxicspikes": {},
            "stickyweb": {},
            "reflect": {},
            "lightscreen": {},
            "auroraveil": {},
            "tailwind": {},
        },
        "room_effects": {
            "trickroom": {},
        },
    }


def _bootstrap_statuses() -> dict[str, Any]:
    return {
        "brn": {"name": "Burn"},
        "par": {"name": "Paralysis"},
        "psn": {"name": "Poison"},
        "tox": {"name": "Toxic Poison"},
        "slp": {"name": "Sleep"},
        "frz": {"name": "Freeze"},
    }


def main() -> None:
    legacy_pokemon = _read_json(LEGACY_DATA_DIR / "pokemon.json")
    legacy_moves = _read_json(LEGACY_DATA_DIR / "moves.json")
    legacy_type_chart = _read_json(LEGACY_DATA_DIR / "typeChart.json")

    _write_json(CANONICAL_DATA_DIR / "species.json", _bootstrap_species(legacy_pokemon))
    _write_json(CANONICAL_DATA_DIR / "moves.json", _bootstrap_moves(legacy_moves))
    _write_json(CANONICAL_DATA_DIR / "type_chart.json", _bootstrap_type_chart(legacy_type_chart))
    _write_json(CANONICAL_DATA_DIR / "items.json", _bootstrap_items())
    _write_json(CANONICAL_DATA_DIR / "abilities.json", _bootstrap_abilities())
    _write_json(CANONICAL_DATA_DIR / "natures.json", _bootstrap_natures())
    _write_json(CANONICAL_DATA_DIR / "formats.json", _bootstrap_formats())
    _write_json(CANONICAL_DATA_DIR / "field_effects.json", _bootstrap_field_effects())
    _write_json(CANONICAL_DATA_DIR / "statuses.json", _bootstrap_statuses())

    print(f"Bootstrapped canonical data into: {CANONICAL_DATA_DIR}")


if __name__ == "__main__":
    main()