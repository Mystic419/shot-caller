# Native WoT transport investigation (development prototype)

Status: native HTTPS was proven live in WoT 2.3.1.0: `BigWorld.fetchURL`
returned HTTP 200 from the official WG endpoint in 3.79 seconds, with a string
body containing 283 vehicle records and `all.battles` on every record.

## Decision

**Decision: A — native client HTTPS is viable for ShotCaller.**

The 2.3.1.0 client has an audited, asynchronous networking primitive that WoT
itself uses:
`BigWorld.fetchURL(url, callback, headers, timeout, method, postData)`.
The 0.0.60 migration uses this transport directly; the sidecar remains in the
repository solely as historical rollback/reference code and is not in the
native package.

## 0.0.60 native lookup migration

The functional migration build uses `LOOKUP_TRANSPORT = 'native'` and makes no
startup probe. A request begins only after a supported Stronghold or platoon
roster has valid account IDs and a supported tier. It resolves the WoT runtime
`constants.CURRENT_REALM` to NA, EU, or ASIA, with NA as the safe fallback:

- NA: `api.worldoftanks.com`
- EU: `api.worldoftanks.eu`
- ASIA: `api.worldoftanks.asia`

The coordinator deduplicates positive DBIDs, sends up to 15 in one
comma-separated `tanks/stats` request, and retains roster names locally. A
shared Tankopedia request is made only when neither the in-memory nor cache
metadata is fresh. Results preserve the existing `dbid`, `name`, `status`, and
vehicle (`tank_id`, `name`, `tier`, `type`, `battles`, `wins`) shape consumed by
the already validated UI. Navigation and filter changes never issue WG calls.

Native cache files live under `mods/configs/shotcaller/cache/`: predictable
per-realm/account/tier player records and one realm Tankopedia record. They use
schema version 1, fetch time, realm, normalized public data only, and a
six-hour freshness policy. Temporary-file write, flush, and Windows
`MoveFileExW` replacement are used where available. Corrupt files are ignored;
stale player data is used as a fallback after a network failure. Player cache
retention is bounded to the 120 most recently written records. No raw API body,
request URL, ID, or token is stored.

The `.wotmod` builder reads `WG_APP_ID` from the developer's local `.env` only
to inject it into temporary Python 2.7 source. The repository source, logs,
and package manifest do not expose it. This is a public WG API identifier, not
a player credential. 0.0.60 is a migration test build, not yet the public
release.

## 0.0.61 lookup-identity repair

0.0.60 used the broad roster generation in its native response-stale check.
Ready/status presentation updates increment that generation, so a successful
request could be discarded after cache writes but before applying results,
leaving the history window Pending. 0.0.61 replaces it with a material lookup
key: room context, current unit/session identity, realm, supported tier, and
the normalized set of positive roster DBIDs. A response is accepted when that
key still matches, even if ready/status, commander, or same-tier vehicle UI
state changed. The existing open history view is refreshed immediately.

If the material key differs—room exit, battle, unit change, tier/realm change,
or roster removal—the response is rejected and one cache-aware replacement
evaluation is queued for the active roster. Native diagnostics now report only
safe key summaries (context/unit/realm/tier/account count). The stats summary
counts `withBattles` only among normalized, displayed vehicles rather than the
unfiltered WG record list. Tankopedia completion is logged; a failed refresh
falls back to the existing local VI/VIII/X client catalog before failing the
lookup.

## 0.0.62 active-view navigation repair

Previous/Next had already selected the correct cached roster DBID, but then
called `loadView` with the same global alias while the custom history view was
open. WoT coalesced that duplicate load request, leaving the old visible data.
The navigation path now retains the populated custom-view reference and pushes
the selected row through the existing structured DAAPI bridge in place.
`as_setHistoryHeader` replaces name/clan/counter/state, while
`as_beginHistoryRows` clears all heading, vehicle, battle-count, and
informational children and resets the scroll body to the top before new rows
are sent. The overlay is neither closed nor moved. If roster membership
changes, the selected DBID is retained when possible; otherwise the nearest
available row is selected and refreshed in place.

## Client networking audit

The read-only 2.3.1.0 client source was inspected from the extracted reference
tree; no file under `reference/` was changed.

| Facility | Evidence | Assessment |
| --- | --- | --- |
| `BigWorld.fetchURL` | `gui/clientgw/factory.py` passes `(url, callback, headers, timeout, method, postData)` directly to it. | Selected for the prototype. It is WoT's own callback-based path. |
| Fetch response contract | `uilogging/core/handler.py` reads `response.responseCode` and `response.body`, then decodes JSON. | Audited response shape used by the adapter. |
| Client gateway requester | `gui.clientgw/factory.py` creates `client_request_lib.requester.Requester` on top of `BigWorld.fetchURL`. | Strong evidence that the API is normal client infrastructure, not a mod-only trick. |
| `WebDownloader` | `web/cache/web_downloader.py` queues `_HttpOpenUrlJob` on a `helpers.threads.ThreadPool`, and returns callbacks via `nextTick`. | Useful precedent for asynchronous download/callback design, but not selected: its underlying helper is HTTP-oriented and does not establish the HTTPS/TLS behavior needed here. |
| `urllib2` / `httplib` | Client helpers use them for ordinary synchronous/cache work. | Present, but not selected for game-facing WG traffic because a mod would have to supply its own thread, TLS handling, and callback marshalling. |
| `connection_mgr` | Used for the game-server connection lifecycle. | Not a general external HTTP client. |
| `fetchURLEx`, `requests`, `OpenWG` helper | No usable Python 2.7 client-side implementation was found in the audited source. | Not a candidate. |

The installed/reference-mod archives are not a better network dependency than
the client's own gateway facility. The prototype therefore avoids copying a
network helper from another mod.

## XVM/OpenWG audit (0.0.59 probe preparation)

The installed XVM package was inspected read-only at
`reference/wot-2.3.1.0/installed-mods/com.modxvm.xvm_13.1.0.0033.wotmod`.
The relevant compiled files are:

- `res/mods/openwg_packages/xvm_main/loadurl.pyc` — entry point
  `xvm_main.loadurl.loadUrl`;
- `res/mods/openwg_packages/xvm_main/xvmapi.pyc` — API wrapper whose `_exec`
  invokes `loadUrl` and parses JSON;
- `reference/.../net.openwg/net.openwg.common_2.1.2.wotmod`,
  `res/mods/openwg_packages/openwg_network/__init__.pyc` — `request`,
  `request_callback`, and `request_async` wrappers;
- the same package's
  `res/mods/openwg_packages/openwg_network/native_wg/openwg_network.pyd` —
  the native implementation used by those wrappers.

XVM's `loadUrl` constructs headers, calls
`openwg_network.request(url, method=..., headers=..., body=..., timeout=...)`,
and receives `(status, headers, body)`. It logs only request/response timing
and accepts selected HTTP statuses before JSON decoding. The OpenWG Python
wrapper can run `request` in a `threading.Thread` (`request_callback`) and also
exposes a `game_async` wrapper. XVM itself therefore depends on the OpenWG
native extension, rather than on `BigWorld.fetchURL` or plain `urllib2`.

This explains the observed `[XVM/Main/LoadUrl]` logging and proves that a
reliable in-client HTTPS stack exists on the user's installation. It is not a
safe standalone ShotCaller dependency: importing it would require XVM/OpenWG
to be installed and version-compatible, and bundling its `.pyd` would turn a
small mod into an unmanaged native-binary distribution. ShotCaller copies only
the *pattern*—bounded timeout, concise timing/status logs, JSON after a
successful response, and no UI work on a worker—not OpenWG code or imports.

For the first standalone probe, `BigWorld.fetchURL` remains the selected
transport. It is directly provided by WoT, is already used by WoT's client
gateway, has an audited callback object contract, and imposes no XVM/OpenWG
dependency. The probe instruments callback arity/types rather than assuming
the contract beyond the client evidence.

## Prototype implementation

`wot_mod/prototype_2_garage_hook/mod_shotcaller.py` now contains the isolated
development-only API:

```python
def request_json(url, callback, errback=None, timeout=10.0):
    pass
```

Its real implementation:

- calls `BigWorld.fetchURL` with the audited six-argument signature;
- receives WoT's response object and accepts only HTTP 2xx;
- decodes JSON with the embedded Python 2.7 `json` module;
- requires the WG response field `status == 'ok'`;
- normalizes failures to `dns`, `network`, `timeout`, `tls`, `http`,
  `invalid_json`, `wg_api`, `callback`, or `unknown` without logging URLs or
  credentials; only a masked 200-character body prefix is emitted for a
  failure that needs diagnosis;
- schedules completion using `BigWorld.callback(0.0, ...)` when available;
- returns a small handle. `cancel_native_request` is logical cancellation:
  the network request may finish, but a cancelled/stale callback is ignored;
- cancels outstanding native probe handles as part of the existing roster clear
  path.

`LOOKUP_TRANSPORT = 'sidecar'` remains the default. The normal source has
`NATIVE_PROBE_ENABLED = False`. The dedicated 0.0.59 development builder alone
injects `True` and the locally available public application ID into a temporary
source file before Python 2.7 compilation; it never writes either value back to
the repository source. That one-session probe does not manufacture incomplete
history rows or alter the Scaleform UI. It leaves full migration for a later
build.

## Minimal in-game test hook

The test hook is `run_native_wg_probe(account_id=None)`. The 0.0.59 package
schedules it once after a lobby app is available, with account ID `1001921023`
(`mystic419`). It calls the same endpoint and fields as the sidecar:

```
https://api.worldoftanks.com/wot/tanks/stats/
fields=tank_id,all.battles,all.wins
```

The development builder reads the existing local `.env` only to stage the test
package; no ID is committed or printed. Expected bounded diagnostics:

```
[shotcaller] native WG request started: endpoint=tanks/stats
[shotcaller] native WG transport callback: responseCode=200
[shotcaller] native WG callback diagnostics: args=1 types=... bodyType=... bodyBytes=...
[shotcaller] native WG request complete: seconds=...
[shotcaller] native WG response parsed: status=ok vehicles=... withBattles=... zeroBattles=...
```

The test records only account ID, number of records, and number whose
`all.battles` field exists, in `NATIVE_PROBE_RESULT`, retrievable by
`get_native_probe_snapshot()`. It does not print a response body, application
ID, token, or vehicle list. A test should confirm the game remains responsive
while the request is pending, then change/leave the room before completion to
confirm the logical cancellation and generation-safe discard behavior.

## HTTPS and TLS status

The client source proves that `fetchURL` is asynchronous and timeout-bearing.
It does **not** expose the implementation details of TLS verification in the
decompiled Python tree. The adapter neither disables verification nor supplies
custom certificates. Therefore the controlled in-game test must explicitly
record:

1. HTTP 200 from the HTTPS WG endpoint;
2. a valid JSON/WG status result;
3. a bounded timeout failure by using a deliberately short development timeout;
4. the safe `tls` classification, if a certificate failure can be reproduced
   in a non-production test environment.

Redirect behavior is intentionally not relied upon: the adapter calls the
final HTTPS API URL directly. Query parameters are encoded with Python 2.7
`urllib.urlencode`.

## Application ID

The existing sidecar gets `WG_APP_ID` from the developer environment or `.env`.
That mechanism is unsuitable for a normal one-file mod installation. A future
client-only release needs a ShotCaller-owned **public** application ID embedded
as a non-secret constant, subject to Wargaming's current public API terms,
rate limits, and revocation policy. It must not use player account tokens or
ask users to create an ID. No such ID has been added during this investigation.

This is an operational risk, not a technical blocker: a public ID can be
observed in a client mod and therefore must be treated as revocable and
rate-limited rather than confidential.

## Cache design for a client-only migration

Use `mods/configs/shotcaller/cache/`, never the `.wotmod` archive. Suggested
files are:

- `tankopedia_na.json` — normalized `tank_id`, localized name, tier, class;
- `players/<dbid>_tier<tier>.json` — normalized public history with battle
  counts and expiry metadata.

Each file should contain schema version, `created_at`, `expires_at`, and data.
Use the existing six-hour player refresh target; tankopedia may use its own
longer versioned TTL. Writes must be atomic: write `*.tmp`, flush/close, then
replace the final file. A corrupt, missing, expired, or incompatible file must
be ignored without a client exception. On transient network failure, expose a
non-expired stale record as a clearly marked fallback rather than discarding it.

## Rate, batching, and migration constraints

The sidecar source records the WG behavior observed during prototype work:
`tanks/stats` rejects comma-separated account IDs. A full 15-player detachment
therefore costs up to **15** individual public `tanks/stats` requests on cache
miss, plus one shared tankopedia request when its cache is cold. A native
implementation must use a bounded queue (for example 3–5 active requests),
deduplicate by `(dbid, tier)`, debounce roster updates, and reject responses
whose `(unit_id, tier, generation)` no longer matches the current roster.

The current `BigWorld.fetchURL` adapter is correctly asynchronous but is only
a one-player proof. A production migration must add the bounded scheduler,
tankopedia resolver, six-hour disk cache, stale-cache fallback, and conversion
into the existing normalized `LOOKUPS` record shape. UI, roster, filtering, and
lifecycle code should consume that normalized result without knowing the
transport.

## Next decision gate

Run the development probe in WoT before any release migration. If it receives
an HTTPS 200 response with valid data and no UI hitch, native transport moves
to a production scheduler/caching prototype. If it fails, capture only the
adapter's safe category and HTTP status; diagnose `BigWorld.fetchURL` first,
not raw `urllib2`. A hosted backend is only the transparent fallback if WoT's
client gateway cannot reliably reach the public WG API under current client
TLS/policy constraints.

## 0.0.63 WG API batch recovery

The client sends multiple `account_id` values to `tanks/stats` as the official
comma-delimited query value (URL-encoded as `%2C`). A HTTP 200 response can
still carry the WG JSON `status=error` envelope. The native coordinator now
logs only safe envelope fields—endpoint, WG code/message, optional field/value,
account count, and realm—never the URL or application ID. A failed multi-account
envelope makes one bounded transition to individual unresolved-account requests;
there is no recursive retry. Valid memory/disk cache entries remain intact,
successful individual records are cached, and only accounts that still fail or
are absent from an otherwise successful response receive the explicit
informational API-unavailable state.

## 0.0.64 win rate and local clan watermark

The native `tanks/stats` record now preserves non-negative `all.wins` alongside
battles. The history row renders public `WR / Battles`; missing legacy wins,
zero battles, and impossible win totals render an em dash rather than a false
percentage. The optional watermark is based only on the logged-in account's
public clan, never the currently selected roster member. Metadata and validated
PNG/JPEG art use a 24-hour cache beneath ShotCaller's existing cache directory;
no-clan or image failures leave both windows unchanged.
