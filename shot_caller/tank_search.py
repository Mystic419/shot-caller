from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any

from shot_caller.tankopedia import load_tankopedia
from shot_caller.wg_api import WargamingAPIClient


TYPE_LABELS = {
    "heavyTank": "HEAVY",
    "mediumTank": "MEDIUM",
    "lightTank": "LIGHT",
    "AT-SPG": "TD",
    "SPG": "ARTY",
}


@dataclass
class TankSearchResult:
    tank_id: int
    name: str
    tier: int
    tank_type: str
    is_premium: bool
    score: tuple[int, int, int, str]


def normalize_search_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    lowered = ascii_only.lower()
    cleaned = "".join(char if char.isalnum() else " " for char in lowered)
    return " ".join(cleaned.split())


def score_match(query: str, name: str) -> tuple[int, int, int, str] | None:
    normalized_query = normalize_search_text(query)
    normalized_name = normalize_search_text(name)

    if not normalized_query:
        return None

    if normalized_query == normalized_name:
        return (0, 0, 0, normalized_name)

    if normalized_name.startswith(normalized_query):
        return (0, 1, len(normalized_name), normalized_name)

    if normalized_query in normalized_name:
        return (1, normalized_name.find(normalized_query), len(normalized_name), normalized_name)

    query_compact = normalized_query.replace(" ", "")
    name_compact = normalized_name.replace(" ", "")

    if query_compact and query_compact == name_compact:
        return (0, 2, len(normalized_name), normalized_name)

    if query_compact and name_compact.startswith(query_compact):
        return (1, 0, len(normalized_name), normalized_name)

    if query_compact and query_compact in name_compact:
        return (2, name_compact.find(query_compact), len(normalized_name), normalized_name)

    return None


def find_tanks(
    client: WargamingAPIClient | None,
    query: str,
    tier: int | None = None,
) -> list[TankSearchResult]:
    tankopedia = load_tankopedia(client)
    matches: list[TankSearchResult] = []

    for tank_id, tank in tankopedia.items():
        tank_tier = int(tank.get("tier", 0))
        if tier is not None and tank_tier != tier:
            continue

        name = str(tank.get("name", f"Tank {tank_id}"))
        score = score_match(query, name)
        if score is None:
            continue

        matches.append(
            TankSearchResult(
                tank_id=tank_id,
                name=name,
                tier=tank_tier,
                tank_type=str(tank.get("type", "unknown")),
                is_premium=bool(tank.get("is_premium", False)),
                score=score,
            )
        )

    return sorted(matches, key=lambda item: (item.score, item.tier, item.name.lower()))


def get_tank_type_label(tank_type: str) -> str:
    return TYPE_LABELS.get(tank_type, tank_type.upper())
