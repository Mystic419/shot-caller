"""Loopback-only HTTP bridge for the modern Shotcaller lookup backend."""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from shot_caller.config import get_app_id
from shot_caller.tankopedia import load_tankopedia
from shot_caller.wg_api import APITimeoutError, MissingApplicationIDError, WargamingAPIClient, WargamingAPIError

HOST = "127.0.0.1"
PORT = 37841
VERSION = "0.0.26"
CACHE_TTL_SECONDS = 10 * 60
_result_cache: dict[tuple[str, int, int], tuple[float, dict[str, Any]]] = {}


def _validate_request(payload: Any) -> tuple[str, int, Any, int, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    region = payload.get("region")
    tier = payload.get("tier")
    unit_id = payload.get("unit_id")
    generation = payload.get("generation")
    players = payload.get("players")
    if region != "na":
        raise ValueError("unsupported region")
    if tier not in (6, 8, 10):
        raise ValueError("tier must be 6, 8, or 10")
    if not isinstance(players, list) or len(players) > 15:
        raise ValueError("players must be a list of at most 15 entries")
    if not isinstance(generation, int):
        raise ValueError("generation must be an integer")
    unique: list[dict[str, Any]] = []
    seen: set[int] = set()
    for player in players:
        if not isinstance(player, dict) or not isinstance(player.get("dbid"), int) or player["dbid"] <= 0:
            raise ValueError("each player requires a positive integer dbid")
        if player["dbid"] not in seen:
            seen.add(player["dbid"])
            unique.append({"dbid": player["dbid"], "name": str(player.get("name") or "")})
    return region, tier, unit_id, generation, unique


def _result_from_records(player: dict[str, Any], records: list[dict[str, Any]] | None, tankopedia: dict[int, dict[str, Any]], tier: int) -> dict[str, Any]:
    result: dict[str, Any] = {"dbid": player["dbid"], "name": player["name"], "status": "api_error", "vehicles": []}
    if records is None:
        result["status"] = "no_account"; return result
    vehicles = []
    for record in records:
        tank = tankopedia.get(int(record.get("tank_id", 0)))
        if not tank or int(tank.get("tier", 0)) != tier: continue
        all_stats = record.get("all") or {}
        try: battles = max(0, int(all_stats.get("battles", 0)))
        except (TypeError, ValueError): battles = 0
        vehicles.append({"tank_id": int(record["tank_id"]), "name": str(tank.get("name", "Unknown")),
                          "tier": tier, "type": str(tank.get("type", "unknown")),
                          "battles": battles, "wins": int(all_stats.get("wins", 0))})
    vehicles.sort(key=lambda item: (-item["battles"], item["name"]))
    result["vehicles"] = vehicles; result["status"] = "ok" if vehicles else "no_vehicle_history"
    return result


def _failure_category(error: Exception) -> str:
    if isinstance(error, MissingApplicationIDError): return "configuration"
    if isinstance(error, APITimeoutError): return "http"
    if isinstance(error, WargamingAPIError): return "api"
    if isinstance(error, (ValueError, TypeError, json.JSONDecodeError)): return "parse"
    return "unknown"


def lookup_roster(payload: Any) -> dict[str, Any]:
    region, tier, unit_id, generation, players = _validate_request(payload)
    app_id = get_app_id()
    if not app_id:
        raise MissingApplicationIDError("WG application ID is not configured")
    client = WargamingAPIClient(app_id=app_id)
    started = time.monotonic(); print(f"[shotcaller-sidecar] roster request started: players={len(players)} tier={tier}")
    hits: dict[int, dict[str, Any]] = {}; misses: list[dict[str, Any]] = []
    for player in players:
        cached = _result_cache.get((region, player["dbid"], tier))
        if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS: hits[player["dbid"]] = dict(cached[1])
        else: misses.append(player)
    print(f"[shotcaller-sidecar] roster cache: hits={len(hits)} misses={len(misses)}")
    results = dict(hits)
    if misses:
        tankopedia_started = time.monotonic()
        try: tankopedia = load_tankopedia(client)
        except Exception as exc:
            print(f"[shotcaller-sidecar] roster request failed: stage=tankopedia reason={type(exc).__name__}")
            tankopedia = None
        print(f"[shotcaller-sidecar] tankopedia ready: seconds={time.monotonic() - tankopedia_started:.3f}")
        stats_started = time.monotonic(); histories: dict[int, list[dict[str, Any]] | None] = {}; failed: set[int] = set()
        print(f"[shotcaller-sidecar] batch lookup started: players={len(misses)}")
        if tankopedia is not None:
            # WG tanks/stats rejects comma-separated account IDs (account_id/407),
            # so this is the fastest supported form: bounded concurrent requests.
            with ThreadPoolExecutor(max_workers=min(7, len(misses))) as executor:
                futures = {executor.submit(client.get_player_tank_stats, player["dbid"]): player for player in misses}
                for future in as_completed(futures):
                    player = futures[future]
                    try:
                        histories[player["dbid"]] = future.result()
                        print("[shotcaller-sidecar] response status=ok api_status=ok top_level_player_records=1")
                    except Exception as exc:
                        failed.add(player["dbid"])
                        print(f"[shotcaller-sidecar] batch lookup failed: category={_failure_category(exc)} reason={type(exc).__name__}")
        print(f"[shotcaller-sidecar] batch lookup complete: players={len(misses)} seconds={time.monotonic() - stats_started:.3f}")
        print(f"[shotcaller-sidecar] player history fetched: players={len(misses)} seconds={time.monotonic() - stats_started:.3f}")
        for player in misses:
            if tankopedia is None or player["dbid"] in failed: result = {"dbid": player["dbid"], "name": player["name"], "status": "api_error", "vehicles": []}
            else: result = _result_from_records(player, histories.get(player["dbid"]), tankopedia, tier)
            results[player["dbid"]] = result
            if result["status"] in ("ok", "no_vehicle_history"): _result_cache[(region, player["dbid"], tier)] = (time.monotonic(), dict(result))
    ordered = []
    for player in players:
        result = dict(results[player["dbid"]]); result["name"] = player["name"] or result.get("name", ""); ordered.append(result)
    print(f"[shotcaller-sidecar] roster request complete: players={len(ordered)} seconds={time.monotonic() - started:.3f}")
    return {"ok": True, "unit_id": unit_id, "tier": tier, "generation": generation, "players": ordered,
            "notice": "Public vehicle history does not prove current garage ownership."}


class SidecarHandler(BaseHTTPRequestHandler):
    server_version = "ShotcallerSidecar/0.0.26"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health": self._json(HTTPStatus.OK, {"ok": True, "service": "shotcaller", "version": VERSION})
        else: self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/lookup/roster":
            self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 32 * 1024: raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            self._json(HTTPStatus.OK, lookup_roster(payload))
        except MissingApplicationIDError:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "configuration"})
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid lookup request"})
        except Exception:
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {"ok": False, "error": "lookup unavailable"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    parser.add_argument("--allow-non-loopback", action="store_true")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "::1", "localhost") and not args.allow_non_loopback:
        parser.error("refusing non-loopback bind without --allow-non-loopback")
    print("[shotcaller-sidecar] WG application ID configured: " + ("yes" if get_app_id() else "no"))
    server = ThreadingHTTPServer((args.host, args.port), SidecarHandler)
    print(f"Shotcaller sidecar listening on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
