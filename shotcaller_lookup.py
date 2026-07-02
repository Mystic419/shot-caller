import argparse
import sys
from pathlib import Path

from shot_caller.config import get_app_id, get_app_id_status
from shot_caller.config_catalog import build_config_catalog, format_config_catalog_preview
from shot_caller.exclusions import (
    load_excluded_tanks_config,
    set_tank_hidden,
    toggle_tank_hidden,
)
from shot_caller.formatter import (
    format_batch_lookup_result,
    format_lookup_result,
    format_tank_search_results,
)
from shot_caller.lookup import lookup_batch_player_tanks, lookup_player_tanks
from shot_caller.tank_search import find_tanks
from shot_caller.tankopedia import load_tankopedia
from shot_caller.wg_api import (
    APITimeoutError,
    InvalidApplicationIDError,
    MissingApplicationIDError,
    NoTanksFoundError,
    PlayerNotFoundError,
    WargamingAPIClient,
    WargamingAPIError,
)


def print_debug_app_id_status() -> None:
    status = get_app_id_status()
    found = "yes" if status.found else "no"
    print("DEBUG WG_APP_ID")
    print(f"  found: {found}")
    print(f"  source: {status.source}")
    print(f"  length: {status.length}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python shotcaller_lookup.py",
        usage=(
            "python shotcaller_lookup.py <nickname> <tier> [--debug]\n"
            "       python shotcaller_lookup.py --batch <roster.txt> <tier> [--debug]"
        ),
    )
    parser.add_argument("arg1", nargs="?")
    parser.add_argument("arg2", nargs="?")
    parser.add_argument("--batch", dest="batch_file")
    parser.add_argument("--config-preview", action="store_true")
    parser.add_argument("--config-tier", type=int)
    parser.add_argument("--nation")
    parser.add_argument("--find-tank")
    parser.add_argument("--find-tier", type=int)
    parser.add_argument("--hide-tank", type=int)
    parser.add_argument("--show-tank", type=int)
    parser.add_argument("--toggle-tank", type=int)
    parser.add_argument("--show-excluded", action="store_true")
    parser.add_argument("--workers", type=int)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def read_roster_file(path: str) -> list[str]:
    roster_path = Path(path)
    return [
        line.strip()
        for line in roster_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def make_optional_client() -> WargamingAPIClient | None:
    app_id = get_app_id()
    if not app_id:
        return None
    return WargamingAPIClient(app_id=app_id)


def resolve_tank_name(tank_id: int) -> str:
    try:
        tankopedia = load_tankopedia(make_optional_client())
    except Exception:
        return f"Tank {tank_id}"

    tank = tankopedia.get(int(tank_id))
    if not tank:
        return f"Tank {tank_id}"

    return str(tank.get("name", f"Tank {tank_id}"))


def handle_hidden_tank_command(args: argparse.Namespace) -> int | None:
    commands = [
        tank_id is not None
        for tank_id in (args.hide_tank, args.show_tank, args.toggle_tank)
    ]
    if not any(commands):
        return None

    if sum(commands) > 1:
        print("Use only one of --hide-tank, --show-tank, or --toggle-tank.")
        return 1

    if args.arg1 is not None or args.arg2 is not None or args.batch_file or args.config_preview or args.find_tank:
        print("Tank visibility edit commands cannot be combined with lookup, batch, preview, or search arguments.")
        return 1

    if args.hide_tank is not None:
        set_tank_hidden(args.hide_tank, True)
        print(f"Hidden: {resolve_tank_name(args.hide_tank)}")
        return 0

    if args.show_tank is not None:
        set_tank_hidden(args.show_tank, False)
        print(f"Shown: {resolve_tank_name(args.show_tank)}")
        return 0

    new_hidden_state = toggle_tank_hidden(args.toggle_tank)
    label = "Hidden" if new_hidden_state else "Shown"
    print(f"{label}: {resolve_tank_name(args.toggle_tank)}")
    return 0


def main() -> int:
    args = parse_args()

    hidden_tank_command_result = handle_hidden_tank_command(args)
    if hidden_tank_command_result is not None:
        return hidden_tank_command_result

    if args.config_preview:
        if args.arg1 is not None or args.arg2 is not None or args.batch_file or args.find_tank:
            print("Config preview mode cannot be combined with nickname, batch, or tank search arguments.")
            return 1
        if args.config_tier is not None and args.config_tier not in (6, 8, 10):
            print("Config tier must be 6, 8, or 10.")
            return 1

        client = make_optional_client()
        exclusions = load_excluded_tanks_config()
        catalog = build_config_catalog(
            client,
            exclusions,
            tier_filter=args.config_tier,
            nation_filter=args.nation,
        )
        print(
            format_config_catalog_preview(
                catalog,
                tier_filter=args.config_tier,
                nation_filter=args.nation,
            )
        )
        return 0

    if args.find_tank:
        if args.arg1 is not None or args.arg2 is not None or args.batch_file:
            print("Tank search mode cannot be combined with nickname or batch lookup arguments.")
            return 1
        if args.find_tier is not None and args.find_tier not in (6, 8, 10):
            print("Find tier must be 6, 8, or 10.")
            return 1

        client = make_optional_client()
        results = find_tanks(client, args.find_tank, tier=args.find_tier)
        print(format_tank_search_results(args.find_tank, results, tier=args.find_tier))
        return 0

    try:
        if args.batch_file:
            if args.arg2 is not None:
                print("Batch mode accepts only a roster file and a tier.")
                return 1
            if args.arg1 is None:
                print("Batch mode requires a roster file and a tier.")
                return 1
            nickname = None
            tier = int(args.arg1)
        else:
            if args.arg1 is None or args.arg2 is None:
                print("Usage:")
                print("  python shotcaller_lookup.py <nickname> <tier>")
                print("  python shotcaller_lookup.py --batch roster.txt <tier>")
                return 1
            nickname = args.arg1
            tier = int(args.arg2)
    except ValueError:
        print("Tier must be 6, 8, or 10.")
        return 1

    if tier not in (6, 8, 10):
        print("Tier must be 6, 8, or 10.")
        return 1

    workers = 4 if args.workers is None else max(1, min(args.workers, 8))

    app_id = get_app_id()
    if not app_id:
        raise MissingApplicationIDError(
            "WG_APP_ID is not set. Add it to your environment or a local .env file."
        )

    client = WargamingAPIClient(app_id=app_id)
    exclusions = load_excluded_tanks_config()

    if args.debug:
        print_debug_app_id_status()

    if args.batch_file:
        nicknames = read_roster_file(args.batch_file)
        if not nicknames:
            print("Roster file is empty.")
            return 1
        batch_result = lookup_batch_player_tanks(
            client,
            nicknames,
            tier,
            exclusions,
            max_workers=workers,
        )
        print(
            format_batch_lookup_result(
                batch_result,
                debug=args.debug,
                show_excluded=args.show_excluded,
            )
        )
        return 0

    result = lookup_player_tanks(client, nickname, tier, exclusions)
    print(
        format_lookup_result(
            result,
            debug=args.debug,
            show_excluded=args.show_excluded,
        )
    )
    return 0


if __name__ == "__main__":
    debug_enabled = "--debug" in sys.argv
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"File error: {exc}")
        sys.exit(1)
    except MissingApplicationIDError as exc:
        if debug_enabled:
            print_debug_app_id_status()
        print(exc)
        sys.exit(1)
    except InvalidApplicationIDError as exc:
        if not debug_enabled:
            print("Invalid WG_APP_ID. Please check your Wargaming application ID.")
        else:
            print(exc)
        sys.exit(1)
    except PlayerNotFoundError as exc:
        print(exc)
        sys.exit(1)
    except APITimeoutError:
        print("Wargaming API timeout. Please try again.")
        sys.exit(1)
    except NoTanksFoundError:
        print("No public tank history found for the selected tier.")
        sys.exit(1)
    except WargamingAPIError as exc:
        print(exc)
        sys.exit(1)
    except RuntimeError as exc:
        print(exc)
        sys.exit(1)
