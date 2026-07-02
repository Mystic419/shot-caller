from __future__ import annotations

from shot_caller.lookup import (
    BatchLookupResult,
    LookupResult,
    PlayerLookupOutcome,
    TYPE_LABELS,
    TankRecord,
)
from shot_caller.tank_search import TankSearchResult, get_tank_type_label


def format_grouped_tanks(grouped_tanks: dict[str, list[TankRecord]]) -> list[str]:
    lines: list[str] = []
    for tank_type, tanks in grouped_tanks.items():
        lines.append("")
        lines.append(TYPE_LABELS.get(tank_type, tank_type.upper()))
        for tank in tanks:
            battle_word = "battle" if tank.battles == 1 else "battles"
            suffix = f" [{tank.note}]" if tank.note else ""
            lines.append(f"  {tank.name} - {tank.battles} {battle_word}{suffix}")
    return lines


def format_excluded_section(grouped_tanks: dict[str, list[TankRecord]]) -> list[str]:
    lines: list[str] = []
    if not grouped_tanks:
        return lines

    lines.append("")
    lines.append("EXCLUDED TANKS")
    lines.append("-" * 40)
    lines.extend(format_grouped_tanks(grouped_tanks))
    return lines


def format_lookup_result(result: LookupResult, debug: bool = False, show_excluded: bool = False) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append(f"{result.nickname} - known Tier {result.tier} tanks")
    lines.append("=" * 40)
    if result.grouped_tanks:
        lines.extend(format_grouped_tanks(result.grouped_tanks))
    else:
        lines.append("No known tanks remain after exclusions for the selected tier.")

    if show_excluded:
        lines.extend(format_excluded_section(result.excluded_grouped_tanks))

    if debug:
        lines.append("")
        lines.append("DEBUG TIMINGS")
        lines.append(f"  account lookup: {result.timings['account_lookup']:.3f}s")
        lines.append(f"  Tankopedia load/fetch: {result.timings['tankopedia']:.3f}s")
        lines.append(f"  player tank stats: {result.timings['player_tank_stats']:.3f}s")
        lines.append(f"  excluded tanks config found: {'yes' if result.excluded_config_found else 'no'}")
        lines.append(f"  excluded tank IDs loaded count: {result.excluded_tank_ids_loaded_count}")
        lines.append(f"  tanks hidden by exclusion count: {result.tanks_hidden_by_exclusion_count}")
        lines.append(f"  total runtime: {result.timings['total']:.3f}s")

    return "\n".join(lines)


def format_player_outcome(result: PlayerLookupOutcome, show_excluded: bool = False) -> list[str]:
    lines: list[str] = []
    lines.append("")
    lines.append(f"{result.nickname} - known Tier {result.tier} tanks")
    lines.append("=" * 40)

    if result.error_message:
        lines.append(result.error_message)
        return lines

    if result.grouped_tanks:
        lines.extend(format_grouped_tanks(result.grouped_tanks))
    else:
        lines.append("No known tanks remain after exclusions for the selected tier.")

    if show_excluded:
        lines.extend(format_excluded_section(result.excluded_grouped_tanks))
    return lines


def format_batch_lookup_result(
    result: BatchLookupResult,
    debug: bool = False,
    show_excluded: bool = False,
) -> str:
    lines: list[str] = []
    lines.append("")
    lines.append(f"Batch known Tier {result.tier} tanks")
    lines.append("=" * 40)

    for player_result in result.players:
        lines.extend(format_player_outcome(player_result, show_excluded=show_excluded))

    if debug:
        lines.append("")
        lines.append("DEBUG TIMINGS")
        lines.append(f"  Tankopedia load/fetch: {result.timings['tankopedia']:.3f}s")
        lines.append(f"  workers used: {result.workers_used}")
        lines.append(f"  players requested: {result.players_requested}")
        lines.append(f"  players resolved: {result.players_resolved}")
        lines.append(f"  account lookup total: {result.timings['account_lookup']:.3f}s")
        lines.append(f"  tank stats total: {result.timings['player_tank_stats']:.3f}s")
        lines.append(f"  tank stat requests attempted: {result.tank_stat_requests_attempted}")
        lines.append(f"  tank stat requests failed: {result.tank_stat_requests_failed}")
        lines.append(f"  excluded tanks config found: {'yes' if result.excluded_config_found else 'no'}")
        lines.append(f"  excluded tank IDs loaded count: {result.excluded_tank_ids_loaded_count}")
        lines.append(f"  tanks hidden by exclusion count: {result.tanks_hidden_by_exclusion_count}")
        lines.append(f"  total runtime: {result.timings['total']:.3f}s")

    return "\n".join(lines)


def format_tank_search_results(
    query: str,
    results: list[TankSearchResult],
    tier: int | None = None,
) -> str:
    lines: list[str] = []
    lines.append("")
    if tier is None:
        lines.append(f'Tank search: "{query}"')
    else:
        lines.append(f'Tank search: "{query}" (Tier {tier})')
    lines.append("=" * 40)

    if not results:
        lines.append("No matching tanks found.")
        return "\n".join(lines)

    for result in results:
        premium_label = "premium" if result.is_premium else "standard"
        lines.append(
            f"{result.tank_id} | {result.name} | Tier {result.tier} | "
            f"{get_tank_type_label(result.tank_type)} | {premium_label}"
        )

    return "\n".join(lines)
