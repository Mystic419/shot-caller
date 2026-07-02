from __future__ import annotations

from typing import Any

from shot_caller.cache import load_json_cache, save_json_cache
from shot_caller.config import CACHE_MAX_AGE_SECONDS, CACHE_PATH
from shot_caller.wg_api import WargamingAPIClient


REQUIRED_TANKOPEDIA_FIELDS = {"tank_id", "name", "tier", "type", "nation", "is_premium"}


def tankopedia_has_required_fields(tankopedia: dict[int, dict[str, Any]]) -> bool:
    if not tankopedia:
        return False

    sample = next(iter(tankopedia.values()))
    return REQUIRED_TANKOPEDIA_FIELDS.issubset(sample.keys())


def load_tankopedia(client: WargamingAPIClient | None) -> dict[int, dict[str, Any]]:
    cached = load_json_cache(CACHE_PATH, CACHE_MAX_AGE_SECONDS)
    cached_tankopedia: dict[int, dict[str, Any]] | None = None
    if cached is not None:
        cached_tankopedia = {int(tank_id): tank for tank_id, tank in cached.items()}
        if tankopedia_has_required_fields(cached_tankopedia):
            return cached_tankopedia

    if client is None:
        if cached_tankopedia is not None:
            return cached_tankopedia
        raise RuntimeError("Tankopedia cache is missing and no API client is available.")

    try:
        tankopedia = client.get_tankopedia()
    except Exception:
        if cached_tankopedia is not None:
            return cached_tankopedia
        raise

    save_json_cache(CACHE_PATH, {str(tank_id): tank for tank_id, tank in tankopedia.items()})
    return tankopedia
