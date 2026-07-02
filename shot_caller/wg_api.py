from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from shot_caller.config import BASE_URL, REQUEST_TIMEOUT_SECONDS


class ShotCallerError(RuntimeError):
    """Base error for the project."""


class MissingApplicationIDError(ShotCallerError):
    """Raised when WG_APP_ID is not configured."""


@dataclass
class WargamingAPIError(ShotCallerError):
    """Raised for non-timeout Wargaming API failures."""

    message: str
    field: str = ""
    code: str = ""

    def __str__(self) -> str:
        details: list[str] = []
        if self.field:
            details.append(self.field)
        if self.code:
            details.append(f"code {self.code}")

        if details:
            return f"Wargaming API error: {self.message} ({', '.join(details)})"
        return f"Wargaming API error: {self.message}"


@dataclass
class InvalidApplicationIDError(WargamingAPIError):
    """Raised when Wargaming rejects the application ID."""


class PlayerNotFoundError(ShotCallerError):
    """Raised when a nickname does not resolve to a player account."""


class APITimeoutError(ShotCallerError):
    """Raised when the Wargaming API times out."""


class NoTanksFoundError(ShotCallerError):
    """Raised when no public tank history exists for the selected tier."""


@dataclass
class WargamingAPIClient:
    app_id: str
    base_url: str = BASE_URL
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS

    def api_get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{path}/"
        request_params = dict(params)
        request_params["application_id"] = self.app_id

        try:
            response = requests.get(url, params=request_params, timeout=self.timeout_seconds)
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise APITimeoutError("Wargaming API request timed out.") from exc
        except requests.exceptions.RequestException as exc:
            response = getattr(exc, "response", None)
            status_code = getattr(response, "status_code", None)
            message = "Wargaming API request failed."
            if status_code is not None:
                message = f"Wargaming API request failed with HTTP {status_code}."
            raise WargamingAPIError(message=message) from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise WargamingAPIError("Wargaming API returned invalid JSON.") from exc

        if payload.get("status") != "ok":
            error = payload.get("error", {})
            message = str(error.get("message", "Unknown API error"))
            field = str(error.get("field", ""))
            code = str(error.get("code", ""))

            message_upper = message.upper()
            field_lower = field.lower()
            is_invalid_app_id = (
                field_lower == "application_id"
                or "INVALID_APPLICATION_ID" in message_upper
                or "INVALID APPLICATION ID" in message_upper
            )
            if is_invalid_app_id:
                raise InvalidApplicationIDError(
                    message=message,
                    field=field,
                    code=code,
                )

            raise WargamingAPIError(
                message=message,
                field=field,
                code=code,
            )

        return payload["data"]

    def find_account_id(self, nickname: str) -> int:
        data = self.api_get(
            "account/list",
            {
                "search": nickname,
                "type": "exact",
                "limit": 1,
            },
        )

        if not data:
            raise PlayerNotFoundError(f'No account found for nickname: "{nickname}"')

        return int(data[0]["account_id"])

    def find_account_ids(self, nicknames: list[str]) -> dict[str, int]:
        """Resolve nicknames one by one for now, structured for future batching."""
        resolved: dict[str, int] = {}
        for nickname in nicknames:
            resolved[nickname] = self.find_account_id(nickname)
        return resolved

    def get_player_tank_stats(self, account_id: int) -> list[dict[str, Any]]:
        data = self.api_get(
            "tanks/stats",
            {
                "account_id": account_id,
                "fields": "tank_id,all.battles",
            },
        )
        return data.get(str(account_id), []) or []

    def get_player_tank_stats_batch(self, account_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
        if not account_ids:
            return {}

        joined_account_ids = ",".join(str(account_id) for account_id in account_ids)
        data = self.api_get(
            "tanks/stats",
            {
                "account_id": joined_account_ids,
                "fields": "tank_id,all.battles",
            },
        )
        return {
            int(account_id): records or []
            for account_id, records in data.items()
        }

    def get_tankopedia(self) -> dict[int, dict[str, Any]]:
        data = self.api_get(
            "encyclopedia/vehicles",
            {
                "fields": "tank_id,name,tier,type,nation,is_premium",
            },
        )
        return {int(tank_id): tank for tank_id, tank in data.items()}
