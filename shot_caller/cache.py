from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def load_json_cache(path: Path, max_age_seconds: int) -> dict[str, Any] | None:
    if not path.exists():
        return None

    age_seconds = time.time() - path.stat().st_mtime
    if age_seconds > max_age_seconds:
        return None

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def save_json_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle)

