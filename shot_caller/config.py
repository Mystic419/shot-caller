from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

BASE_URL = "https://api.worldoftanks.com/wot"
REQUEST_TIMEOUT_SECONDS = 15
CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60
CACHE_PATH = Path(".cache") / "tankopedia_na.json"


class AppIDStatus(NamedTuple):
    found: bool
    source: str
    length: int


def get_env_file_path() -> Path:
    return Path.cwd() / ".env"


def normalize_env_value(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        normalized = normalized[1:-1].strip()

    return normalized or None


def parse_env_file(env_path: Path | None = None) -> dict[str, str]:
    if env_path is None:
        env_path = get_env_file_path()

    if not env_path.exists():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        normalized_value = normalize_env_value(value)

        if key and normalized_value is not None:
            parsed[key] = normalized_value

    return parsed


def load_local_env(env_path: Path | None = None) -> None:
    """Load KEY=VALUE pairs from a local .env file without extra dependencies."""
    if env_path is None:
        env_path = get_env_file_path()

    for key, value in parse_env_file(env_path).items():
        if key not in os.environ:
            os.environ[key] = value


def get_app_id() -> str | None:
    env_value = normalize_env_value(os.environ.get("WG_APP_ID"))
    if env_value is not None:
        return env_value

    env_file_values = parse_env_file()
    return normalize_env_value(env_file_values.get("WG_APP_ID"))


def get_app_id_status() -> AppIDStatus:
    env_value = normalize_env_value(os.environ.get("WG_APP_ID"))
    if env_value is not None:
        return AppIDStatus(found=True, source="environment", length=len(env_value))

    env_file = get_env_file_path()
    file_value = normalize_env_value(parse_env_file(env_file).get("WG_APP_ID"))
    if file_value is not None:
        return AppIDStatus(found=True, source=".env", length=len(file_value))

    return AppIDStatus(found=False, source="missing", length=0)
