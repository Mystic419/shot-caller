from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import perf_counter

from shot_caller.exclusions import ExcludedTanksConfig
from shot_caller.tankopedia import load_tankopedia
from shot_caller.wg_api import (
    APITimeoutError,
    NoTanksFoundError,
    PlayerNotFoundError,
    WargamingAPIClient,
    WargamingAPIError,
)


TYPE_ORDER = ["heavyTank", "mediumTank", "lightTank", "AT-SPG", "SPG"]
TYPE_LABELS = {
    "heavyTank": "HEAVY",
    "mediumTank": "MEDIUM",
    "lightTank": "LIGHT",
    "AT-SPG": "TD",
    "SPG": "ARTY",
}


@dataclass
class LookupResult:
    nickname: str
    tier: int
    grouped_tanks: dict[str, list["TankRecord"]]
    excluded_grouped_tanks: dict[str, list["TankRecord"]]
    timings: dict[str, float]
    excluded_config_found: bool
    excluded_tank_ids_loaded_count: int
    tanks_hidden_by_exclusion_count: int


@dataclass
class PlayerLookupOutcome:
    nickname: str
    tier: int
    grouped_tanks: dict[str, list["TankRecord"]]
    excluded_grouped_tanks: dict[str, list["TankRecord"]]
    tanks_hidden_by_exclusion_count: int
    error_message: str | None = None


@dataclass
class BatchLookupResult:
    tier: int
    players: list[PlayerLookupOutcome]
    timings: dict[str, float]
    workers_used: int
    players_requested: int
    players_resolved: int
    tank_stat_requests_attempted: int
    tank_stat_requests_failed: int
    excluded_config_found: bool
    excluded_tank_ids_loaded_count: int
    tanks_hidden_by_exclusion_count: int


@dataclass
class TankRecord:
    tank_id: int
    name: str
    battles: int
    note: str | None = None


def build_grouped_tanks(
    stats: list[dict[str, object]],
    tankopedia: dict[int, dict[str, object]],
    tier: int,
    exclusions: ExcludedTanksConfig,
) -> tuple[dict[str, list[TankRecord]], dict[str, list[TankRecord]], int]:
    visible_grouped: dict[str, list[TankRecord]] = defaultdict(list)
    excluded_grouped: dict[str, list[TankRecord]] = defaultdict(list)
    hidden_count = 0

    for record in stats:
        tank_id = int(record["tank_id"])
        tank = tankopedia.get(tank_id)
        if not tank:
            continue

        if int(tank["tier"]) != tier:
            continue

        battles = int(record.get("all", {}).get("battles", 0))
        tank_type = str(tank.get("type", "unknown"))
        name = str(tank.get("name", f"Tank {tank_id}"))
        tank_record = TankRecord(
            tank_id=tank_id,
            name=name,
            battles=battles,
            note=exclusions.notes.get(tank_id) if tank_id in exclusions.excluded_tank_ids else None,
        )

        if tank_id in exclusions.excluded_tank_ids:
            excluded_grouped[tank_type].append(tank_record)
            hidden_count += 1
            continue

        visible_grouped[tank_type].append(tank_record)

    ordered_grouped: dict[str, list[TankRecord]] = {}
    ordered_excluded_grouped: dict[str, list[TankRecord]] = {}
    for tank_type in TYPE_ORDER:
        tanks = visible_grouped.get(tank_type)
        excluded_tanks = excluded_grouped.get(tank_type)
        if tanks:
            ordered_grouped[tank_type] = sorted(tanks, key=lambda item: item.battles, reverse=True)
        if excluded_tanks:
            ordered_excluded_grouped[tank_type] = sorted(
                excluded_tanks,
                key=lambda item: item.battles,
                reverse=True,
            )

    return ordered_grouped, ordered_excluded_grouped, hidden_count


def lookup_player_tanks(
    client: WargamingAPIClient,
    nickname: str,
    tier: int,
    exclusions: ExcludedTanksConfig,
) -> LookupResult:
    started = perf_counter()

    account_lookup_started = perf_counter()
    account_id = client.find_account_id(nickname)
    account_lookup_seconds = perf_counter() - account_lookup_started

    tankopedia_started = perf_counter()
    tankopedia = load_tankopedia(client)
    tankopedia_seconds = perf_counter() - tankopedia_started

    stats_started = perf_counter()
    stats = client.get_player_tank_stats(account_id)
    stats_seconds = perf_counter() - stats_started

    ordered_grouped, excluded_grouped, hidden_count = build_grouped_tanks(
        stats,
        tankopedia,
        tier,
        exclusions,
    )

    if not ordered_grouped and not excluded_grouped:
        raise NoTanksFoundError("No public tank history found for this tier.")

    total_seconds = perf_counter() - started
    timings = {
        "account_lookup": account_lookup_seconds,
        "tankopedia": tankopedia_seconds,
        "player_tank_stats": stats_seconds,
        "total": total_seconds,
    }

    return LookupResult(
        nickname=nickname,
        tier=tier,
        grouped_tanks=ordered_grouped,
        excluded_grouped_tanks=excluded_grouped,
        timings=timings,
        excluded_config_found=exclusions.found,
        excluded_tank_ids_loaded_count=exclusions.loaded_count,
        tanks_hidden_by_exclusion_count=hidden_count,
    )


def lookup_batch_player_tanks(
    client: WargamingAPIClient,
    nicknames: list[str],
    tier: int,
    exclusions: ExcludedTanksConfig,
    max_workers: int = 4,
) -> BatchLookupResult:
    started = perf_counter()

    tankopedia_started = perf_counter()
    tankopedia = load_tankopedia(client)
    tankopedia_seconds = perf_counter() - tankopedia_started

    requested_nicknames = [nickname for nickname in nicknames if nickname]
    unique_nicknames: list[str] = list(dict.fromkeys(requested_nicknames))
    workers_used = max(1, min(max_workers, 8))

    account_lookup_started = perf_counter()
    resolved_accounts: dict[str, int] = {}
    account_errors: dict[str, str] = {}

    def resolve_account(nickname: str) -> tuple[str, int]:
        return nickname, client.find_account_id(nickname)

    with ThreadPoolExecutor(max_workers=workers_used) as executor:
        future_to_nickname = {
            executor.submit(resolve_account, nickname): nickname
            for nickname in unique_nicknames
        }
        for future in as_completed(future_to_nickname):
            nickname = future_to_nickname[future]
            try:
                _, account_id = future.result()
                resolved_accounts[nickname] = account_id
            except PlayerNotFoundError:
                account_errors[nickname] = f'No account found for nickname: "{nickname}"'
            except (APITimeoutError, WargamingAPIError) as exc:
                account_errors[nickname] = f"Account lookup failed: {exc}"
    account_lookup_seconds = perf_counter() - account_lookup_started

    stats_started = perf_counter()
    stats_by_nickname: dict[str, list[dict[str, object]]] = {}
    stats_errors: dict[str, str] = {}
    tank_stat_requests_attempted = 0
    tank_stat_requests_failed = 0

    def fetch_tank_stats(nickname: str, account_id: int) -> tuple[str, list[dict[str, object]]]:
        return nickname, client.get_player_tank_stats(account_id)

    stats_targets = [
        (nickname, resolved_accounts[nickname])
        for nickname in unique_nicknames
        if nickname not in account_errors
    ]
    tank_stat_requests_attempted = len(stats_targets)

    with ThreadPoolExecutor(max_workers=workers_used) as executor:
        future_to_nickname = {
            executor.submit(fetch_tank_stats, nickname, account_id): nickname
            for nickname, account_id in stats_targets
        }
        for future in as_completed(future_to_nickname):
            nickname = future_to_nickname[future]
            try:
                _, stats = future.result()
                stats_by_nickname[nickname] = stats
            except (APITimeoutError, WargamingAPIError) as exc:
                tank_stat_requests_failed += 1
                stats_errors[nickname] = f"Tank stats lookup failed: {exc}"
    stats_seconds = perf_counter() - stats_started

    players: list[PlayerLookupOutcome] = []
    total_hidden_count = 0
    for nickname in requested_nicknames:
        if nickname in account_errors:
            players.append(
                PlayerLookupOutcome(
                    nickname=nickname,
                    tier=tier,
                    grouped_tanks={},
                    excluded_grouped_tanks={},
                    tanks_hidden_by_exclusion_count=0,
                    error_message=account_errors[nickname],
                )
            )
            continue

        if nickname in stats_errors:
            players.append(
                PlayerLookupOutcome(
                    nickname=nickname,
                    tier=tier,
                    grouped_tanks={},
                    excluded_grouped_tanks={},
                    tanks_hidden_by_exclusion_count=0,
                    error_message=stats_errors[nickname],
                )
            )
            continue

        stats = stats_by_nickname.get(nickname, [])
        grouped_tanks, excluded_grouped_tanks, hidden_count = build_grouped_tanks(
            stats,
            tankopedia,
            tier,
            exclusions,
        )
        total_hidden_count += hidden_count

        if not grouped_tanks and not excluded_grouped_tanks:
            players.append(
                PlayerLookupOutcome(
                    nickname=nickname,
                    tier=tier,
                    grouped_tanks={},
                    excluded_grouped_tanks={},
                    tanks_hidden_by_exclusion_count=0,
                    error_message="No public tank history found for the selected tier.",
                )
            )
            continue

        players.append(
            PlayerLookupOutcome(
                nickname=nickname,
                tier=tier,
                grouped_tanks=grouped_tanks,
                excluded_grouped_tanks=excluded_grouped_tanks,
                tanks_hidden_by_exclusion_count=hidden_count,
            )
        )

    total_seconds = perf_counter() - started
    timings = {
        "tankopedia": tankopedia_seconds,
        "account_lookup": account_lookup_seconds,
        "player_tank_stats": stats_seconds,
        "total": total_seconds,
    }

    return BatchLookupResult(
        tier=tier,
        players=players,
        timings=timings,
        workers_used=workers_used,
        players_requested=len(requested_nicknames),
        players_resolved=len(resolved_accounts),
        tank_stat_requests_attempted=tank_stat_requests_attempted,
        tank_stat_requests_failed=tank_stat_requests_failed,
        excluded_config_found=exclusions.found,
        excluded_tank_ids_loaded_count=exclusions.loaded_count,
        tanks_hidden_by_exclusion_count=total_hidden_count,
    )
