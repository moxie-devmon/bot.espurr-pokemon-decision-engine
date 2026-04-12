from __future__ import annotations


def normalized_name(value: str | None) -> str:
    return (value or "").strip().lower()


CHOICE_ITEMS = {
    "choice scarf",
    "choice band",
    "choice specs",
}

SETUP_MOVES = {
    "swords dance",
    "nasty plot",
    "calm mind",
    "dragon dance",
    "bulk up",
    "agility",
    "trailblaze",
    "iron defense",
    "curse",
    "quiver dance",
}

RECOVERY_MOVES = {
    "recover",
    "roost",
    "slack off",
    "soft-boiled",
    "moonlight",
    "morning sun",
    "synthesis",
    "wish",
    "pain split",
}

PIVOT_MOVES = {
    "u-turn",
    "volt switch",
    "flip turn",
    "parting shot",
    "chilly reception",
    "teleport",
}

HAZARD_MOVES = {
    "stealth rock",
    "spikes",
    "toxic spikes",
    "sticky web",
}

DISRUPTION_MOVES = {
    "trick",
    "encore",
    "taunt",
    "thunder wave",
    "will-o-wisp",
    "toxic",
    "knock off",
}

HIGH_SIGNAL_PRIORITY_MOVES = {
    "sucker punch",
    "extreme speed",
    "ice shard",
    "mach punch",
    "bullet punch",
    "shadow sneak",
    "vacuum wave",
}


def is_choice_item(item_name: str | None) -> bool:
    return normalized_name(item_name) in CHOICE_ITEMS


def is_setup_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in SETUP_MOVES


def is_recovery_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in RECOVERY_MOVES


def is_pivot_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in PIVOT_MOVES


def is_hazard_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in HAZARD_MOVES


def is_disruption_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in DISRUPTION_MOVES


def is_priority_signal_move(move_name: str | None) -> bool:
    return normalized_name(move_name) in HIGH_SIGNAL_PRIORITY_MOVES