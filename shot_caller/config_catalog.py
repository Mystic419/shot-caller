from __future__ import annotations

from dataclasses import dataclass

from shot_caller.exclusions import ExcludedTanksConfig
from shot_caller.tank_search import get_tank_type_label
from shot_caller.tankopedia import load_tankopedia
from shot_caller.wg_api import WargamingAPIClient


DETACHMENT_TIERS = (6, 8, 10)
TYPE_ORDER = ["heavyTank", "mediumTank", "lightTank", "AT-SPG", "SPG"]
TIER_LABELS = {
    6: "Tier VI",
    8: "Tier VIII",
    10: "Tier X",
}


@dataclass
class ConfigCatalogTank:
    tank_id: int
    name: str
    tier: int
    tank_type: str
    nation: str
    is_premium: bool
    hidden: bool


ConfigCatalog = dict[int, dict[str, list[ConfigCatalogTank]]]


def build_config_catalog(
    client: WargamingAPIClient | None,
    exclusions: ExcludedTanksConfig,
    tier_filter: int | None = None,
    nation_filter: str | None = None,
) -> ConfigCatalog:
    tankopedia = load_tankopedia(client)
    normalized_nation_filter = nation_filter.lower() if nation_filter else None
    allowed_tiers = (tier_filter,) if tier_filter is not None else DETACHMENT_TIERS
    catalog: ConfigCatalog = {}

    for tank_id, tank in tankopedia.items():
        tier = int(tank.get("tier", 0))
        if tier not in allowed_tiers or tier not in DETACHMENT_TIERS:
            continue

        nation = str(tank.get("nation", "unknown")).lower()
        if normalized_nation_filter and nation != normalized_nation_filter:
            continue

        tank_type = str(tank.get("type", "unknown"))
        tank_entry = ConfigCatalogTank(
            tank_id=tank_id,
            name=str(tank.get("name", f"Tank {tank_id}")),
            tier=tier,
            tank_type=tank_type,
            nation=nation,
            is_premium=bool(tank.get("is_premium", False)),
            hidden=tank_id in exclusions.excluded_tank_ids,
        )

        catalog.setdefault(tier, {})
        catalog[tier].setdefault(tank_type, [])
        catalog[tier][tank_type].append(tank_entry)

    ordered_catalog: ConfigCatalog = {}
    for tier in DETACHMENT_TIERS:
        if tier not in catalog:
            continue

        ordered_catalog[tier] = {}
        for tank_type in TYPE_ORDER:
            tanks = catalog[tier].get(tank_type)
            if not tanks:
                continue
            ordered_catalog[tier][tank_type] = sorted(
                tanks,
                key=lambda tank: (tank.name.lower(), tank.tank_id),
            )

    return ordered_catalog


def format_config_catalog_preview(
    catalog: ConfigCatalog,
    tier_filter: int | None = None,
    nation_filter: str | None = None,
) -> str:
    lines: list[str] = []
    lines.append("")

    title_parts = ["Shotcaller config preview"]
    if tier_filter is not None:
        title_parts.append(TIER_LABELS.get(tier_filter, f"Tier {tier_filter}"))
    if nation_filter:
        title_parts.append(nation_filter.lower())

    lines.append(" - ".join(title_parts))
    lines.append("=" * 40)

    if not catalog:
        lines.append("No matching tanks found for config preview.")
        return "\n".join(lines)

    for tier, tank_types in catalog.items():
        lines.append("")
        lines.append(TIER_LABELS.get(tier, f"Tier {tier}"))
        lines.append("-" * 40)
        for tank_type in TYPE_ORDER:
            tanks = tank_types.get(tank_type)
            if not tanks:
                continue

            lines.append(f"  {get_tank_type_label(tank_type)}")
            for tank in tanks:
                hidden_label = "hidden" if tank.hidden else "shown"
                premium_label = "premium" if tank.is_premium else "standard"
                lines.append(
                    f"    [{'x' if tank.hidden else ' '}] "
                    f"{tank.name} ({tank.nation}, {premium_label}, {hidden_label}, id {tank.tank_id})"
                )

    return "\n".join(lines)
