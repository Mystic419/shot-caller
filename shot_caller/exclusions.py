from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExcludedTanksConfig:
    found: bool
    excluded_tank_ids: set[int] = field(default_factory=set)
    notes: dict[int, str] = field(default_factory=dict)

    @property
    def loaded_count(self) -> int:
        return len(self.excluded_tank_ids)


def get_excluded_tanks_path() -> Path:
    return Path.cwd() / "excluded_tanks.json"


def load_excluded_tanks_config(path: Path | None = None) -> ExcludedTanksConfig:
    if path is None:
        path = get_excluded_tanks_path()

    if not path.exists():
        return ExcludedTanksConfig(found=False)

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ExcludedTanksConfig(found=True)

    raw_ids = payload.get("excluded_tank_ids", [])
    excluded_tank_ids = {
        int(tank_id)
        for tank_id in raw_ids
        if isinstance(tank_id, int) or (isinstance(tank_id, str) and tank_id.strip().isdigit())
    }

    raw_notes = payload.get("notes", {})
    notes: dict[int, str] = {}
    if isinstance(raw_notes, dict):
        for tank_id, note in raw_notes.items():
            if isinstance(note, str):
                try:
                    notes[int(tank_id)] = note.strip()
                except (TypeError, ValueError):
                    continue

    return ExcludedTanksConfig(
        found=True,
        excluded_tank_ids=excluded_tank_ids,
        notes=notes,
    )


def load_hidden_tank_ids(path: Path | None = None) -> set[int]:
    return set(load_excluded_tanks_config(path).excluded_tank_ids)


def save_hidden_tank_ids(tank_ids: set[int], path: Path | None = None) -> None:
    if path is None:
        path = get_excluded_tanks_path()

    existing_config = load_excluded_tanks_config(path)
    payload = {
        "excluded_tank_ids": sorted(int(tank_id) for tank_id in tank_ids),
        "notes": {
            str(tank_id): note
            for tank_id, note in sorted(existing_config.notes.items())
        },
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def set_tank_hidden(tank_id: int, hidden: bool) -> None:
    hidden_tank_ids = load_hidden_tank_ids()
    if hidden:
        hidden_tank_ids.add(int(tank_id))
    else:
        hidden_tank_ids.discard(int(tank_id))
    save_hidden_tank_ids(hidden_tank_ids)


def toggle_tank_hidden(tank_id: int) -> bool:
    hidden_tank_ids = load_hidden_tank_ids()
    normalized_tank_id = int(tank_id)
    if normalized_tank_id in hidden_tank_ids:
        hidden_tank_ids.remove(normalized_tank_id)
        new_hidden_state = False
    else:
        hidden_tank_ids.add(normalized_tank_id)
        new_hidden_state = True

    save_hidden_tank_ids(hidden_tank_ids)
    return new_hidden_state


def set_many_tanks_hidden(tank_ids: list[int], hidden: bool) -> None:
    hidden_tank_ids = load_hidden_tank_ids()
    normalized_tank_ids = {int(tank_id) for tank_id in tank_ids}
    if hidden:
        hidden_tank_ids.update(normalized_tank_ids)
    else:
        hidden_tank_ids.difference_update(normalized_tank_ids)
    save_hidden_tank_ids(hidden_tank_ids)
