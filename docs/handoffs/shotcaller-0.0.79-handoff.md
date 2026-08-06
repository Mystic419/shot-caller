# ShotCaller 0.0.79 stable-release handoff

## Scope and status

This is a handoff for the committed stable release **0.0.79**. It records the
repository state rather than a roadmap implementation. Do not treat historical
prototype labels in older READMEs as the current release version.

- Stable commit: `e0edd37` — `STABLE RELEASE 0.0.79`.
- Release package: `wot_mod/prototype_2_garage_hook/dist/shotcaller_0.0.79_chunked_rate_limit_fix.wotmod`.
- This handoff was created from the committed source and documentation at that
  commit. The commit contains the 0.0.78 application-ID repair and the 0.0.79
  large-roster recovery repair.
- The runtime is a standalone `.wotmod`; there is no required companion
  sidecar process in the 0.0.79 native lookup path.

## Confirmed current behavior

### Purpose and player workflow

ShotCaller is a World of Tanks lobby/room mod that captures a friendly
Stronghold/Skirmish/Advances or regular-platoon roster, resolves a supported
team tier, retrieves each member's public vehicle history for that tier, and
shows it in a Tank History window. Its supported tiers are **VI, VIII, and X**.

In normal use, the player enters a supported room, waits until the member
roster and selected vehicles yield a supported tier, then presses
**Ctrl+Alt+V**. That shortcut opens or closes the Tank History window for the
current cached target. The window supports Previous/Next roster navigation and
Settings. `Ctrl+Alt+Left` and `Ctrl+Alt+Right` are also handled as target
navigation shortcuts. Opening or navigating the window reads already-held
results; it does not itself initiate a new WG request.

The window can display pending, ready, no-history, API-error, incomplete,
mixed-tier, unsupported-tier, and empty-roster states. For a platoon, lookup is
held until occupied members select matching supported-tier vehicles. For a
Stronghold context, vehicle updates are captured through the room callback.
The roster is cleared on the applicable lifecycle exit/unload paths, and the
panel is closed when appropriate.

### Runtime architecture

`wot_mod/prototype_2_garage_hook/mod_shotcaller.py` is the WoT Python 2.7
runtime module. It declares public `init()` and `fini()` functions. It does not
call `init()` at module scope: WoT imports the module and calls `init()` under
the native mod lifecycle. A process-global guard prevents duplicate hook
installation.

At initialization the module:

1. Loads persisted vehicle filters.
2. Installs converter hooks around the rally VO conversion path to normalize
   roster rows.
3. Installs Stronghold watcher and direct vehicle-selection listeners.
4. Installs regular-platoon entity lifecycle listeners.
5. Installs an account-readiness hook for the local clan watermark.
6. Registers the two uniquely named Scaleform overlay views and global keyboard
   handlers.

The central in-memory structures are `CACHE` (rows, order, unit ID, tier and
generation), `LOOKUPS` (per-DBID normalized history result), `LOOKUP_STATUS`,
and `PANEL` (open target and position). Roster identity is based on room
context, unit ID, realm, tier, and sorted DBIDs. A broad presentation generation
change can be accepted when this material identity is unchanged; a material
change discards a stale response and queues one replacement lookup.

The history and filters windows are separate Scaleform `AbstractView`-based
overlays registered with unique aliases:

- `shotcallerVehicleWindow` → `res/gui/flash/shotcaller/shotcallerVehicleWindow.swf`
- `shotcallerVehicleFilters` → `res/gui/flash/shotcaller/shotcallerVehicleFilters.swf`

The custom history view has a guarded fallback path to a generic native dialog
if registration, loading, population, or first data push fails. This fallback
is intentional crash isolation, not a separate application.

### Tank History presentation and settings

The active target is selected from cached roster order. The custom view receives
structured headings and vehicle rows. Ready rows are grouped in the fixed type
order Heavy, Medium, Light, Tank Destroyer, and SPG. Within each current group,
the runtime sorts vehicle names alphabetically (case-insensitive). Each vehicle
row carries battle count, optional wins used to derive WR, and Ace/Mastery data.

Settings opens the filters overlay. Filters are presentation-only: they hide
specific stable vehicle IDs from the history view and do not delete cached WG
history or change API results. The filter screen uses a local client vehicle
catalog for tiers VI/VIII/X, supports browsing/search/type filtering and
Hide All/Show All for its currently visible settings rows, and passes three
per-tier hidden-ID lists back to Python on Save. Cancel/Close discard unsaved
working changes. A successful save refreshes an already open history view.

The current persistent filter format is schema version 1 at:

```text
mods/configs/shotcaller/vehicle_filters.json
```

Missing or malformed filter data falls back to showing all vehicles. Saves use
a temporary file then replacement where supported. The local client catalog is
built lazily from nation-scoped `items.vehicles.g_list.getList(nationID)` data,
resolved through client vehicle-type helpers, and cached in memory only after a
complete validated build. Catalog failure remains retryable and is surfaced as
a guarded settings diagnostic.

### WG API and Tankopedia flow

The runtime uses WoT's asynchronous `BigWorld.fetchURL` through `request_json`
for official HTTPS API requests. The audited six-argument call form is:

```text
BigWorld.fetchURL(url, callback, headers, timeout, method, postData)
```

The realm is selected from WoT's `CURRENT_REALM` when available, otherwise NA.
Configured endpoints are the corresponding NA/EU/ASIA World of Tanks API hosts.
The application ID is injected only into temporary staged build source from the
developer's local `WG_APP_ID`; the repository runtime source intentionally
contains `NATIVE_WG_APP_ID = None`.

Lookup is cache-first. A player cache hit younger than six hours supplies its
result immediately, except records without complete mastery data are refreshed.
For misses, the runtime first uses in-memory Tankopedia for the current realm,
then a valid six-hour Tankopedia disk cache, then
`encyclopedia/vehicles`. If that endpoint fails, it attempts a local client
catalog fallback; if neither is available, it completes with available cache
results and error/stale fallback handling.

`tanks/stats` requests ask for `tank_id`, battles, wins, and mastery. Results
are normalized to the active tier and per-player cache records are written only
for non-API-error results. A successful API response that omits a requested
account makes that account unavailable; it does not invalidate other accounts.
The local-account clan flow separately uses `clans/accountinfo` and
`clans/info` to derive a clan tag/emblem watermark, with its own guarded cache
and retry behavior.

### 0.0.79 batching, protection, and recovery

The prior 0.0.78 code formed one tanks/stats URL from all roster misses and
launched every individual recovery request at once after a batch failure.
0.0.79 changes the confirmed runtime behavior as follows:

- A maximum roster of 15 eligible accounts remains in scope for one lookup.
- `tanks/stats` chunks are capped at **8 accounts**. Fifteen accounts become an
  8-account request followed by a 7-account request.
- The final encoded URL is constructed before dispatch. The URL limit is 1800
  characters; a chunk is reduced until it fits. A single account that cannot
  form a valid bounded URL is failed safely rather than partially sent.
- The runtime verifies the joined account-ID sequence before URL construction,
  so it does not deliberately dispatch a partial/truncated final ID.
- Tanks/stats work is sequential: `NATIVE_STATS_REQUEST_ACTIVE` permits at
  most one active tanks/stats request. The Tankopedia request remains a
  separate request path.
- Chunk responses merge into the shared DBID result map; final presentation
  iterates original roster order, preserving roster order regardless of chunk
  boundaries.
- A failed chunk caused by WG API failure (including `INVALID_ACCOUNT_ID`),
  malformed response, invalid JSON, callback/transport/HTTP failure, timeout,
  or unknown transport failure is recovered only for that chunk. Multi-account
  recovery is queued as sequential single-account requests; successful prior
  chunk accounts are not re-requested.
- `REQUEST_LIMIT_EXCEEDED` is detected from the WG error code/message and is
  retried through `BigWorld.callback`, not immediately. There are up to three
  retries after the original attempt, delayed **0.75 s**, **1.5 s**, and
  **3.0 s**. The lookup remains pending while scheduled.
- Each delayed callback rechecks lookup identity. A stale roster/generation
  stops the pending retry, and normal stale-response replacement behavior
  applies. A stale disk cache result is retained when available; otherwise a
  permanently failed account becomes `api_error`.

### Cache, logging, and privacy safeguards

Public player history and Tankopedia cache files are under:

```text
mods/configs/shotcaller/cache/
```

Player cache records are realm/DBID/tier-scoped and schema-versioned. The
runtime uses atomic temporary-file writes where possible, ignores corrupt data,
keeps cache data for a six-hour TTL, and bounds retained player cache files.
Clan emblems live below the cache directory with a 24-hour TTL and bounded
download size.

Logging uses the `[shotcaller]` tag. It records hook/lifecycle state, safe room
and tier information, cache behavior, request endpoint/count/status/elapsed
time, URL length, retry scheduling, and bounded diagnostics. It does **not**
log a full WG URL or query string for tanks/stats. Sensitive error fields
(`application`, token, session, auth, password, secret) are masked, and the
application ID is replaced by `***MASKED***` in guarded text handling. The
build's safe application-ID report states only configured status, length, and
`source: injected build value`; it never prints the ID.

## Repository map

| Path | Purpose |
| --- | --- |
| `wot_mod/prototype_2_garage_hook/mod_shotcaller.py` | Main Python 2.7 WoT runtime: hooks, views, history presentation, filters, native API client, cache, clan watermark, lifecycle cleanup. |
| `wot_mod/prototype_2_garage_hook/custom_ui/src/shotcaller/ui/` | ActionScript source for the history and filter Scaleform views. |
| `wot_mod/prototype_2_garage_hook/custom_ui/dist/` | Built SWF inputs consumed by the release builder. |
| `wot_mod/prototype_2_garage_hook/build_native_lookup_migration.py` | Shared current release builder: validates/injects `WG_APP_ID`, runs the Python 2.7 regression list, stages source, runs compileall, packages/audits archive. |
| `wot_mod/prototype_2_garage_hook/build_chunked_rate_limit_fix.py` | 0.0.79 wrapper selecting the exact package name, version, readable-source path, and metadata. |
| `wot_mod/prototype_2_garage_hook/build_application_id_fix.py` | 0.0.78 historical correction wrapper. |
| `wot_mod/prototype_2_garage_hook/build_wgmods_review.py`, `build_wgmods_compileall.py`, `build_standalone*.py` | Current shared-builder wrappers for WGMods/review/standalone packaging; inspect their selected names/version before using them for a future release. |
| `wot_mod/prototype_2_garage_hook/test_*.py` | Python 2.7 regression tests; the builder owns the complete current test list. |
| `wot_mod/prototype_2_garage_hook/dist/` | Built historical and release `.wotmod` artifacts. |
| `docs/native_transport_investigation.md` | Evidence and decisions for native WoT HTTPS transport, cache, application-ID, and version-specific transport assumptions. Some batching discussion predates 0.0.79. |
| `docs/wot_mod_integration_plan.md` | Long-running integration research and prototype history; it includes historical assumptions and is not a current release specification. |
| `wot_mod/prototype_2_garage_hook/README.md` | Detailed prototype/release history and UI notes; its headings are historical and must be cross-checked against the runtime. |
| `shot_caller/`, `shotcaller_lookup.py` | Earlier sidecar-oriented project material. It is not required by the 0.0.79 standalone native lookup path. |

## Build and packaging

Use the 0.0.79 wrapper from `wot_mod/prototype_2_garage_hook`:

```bat
C:\Python27\python.exe build_chunked_rate_limit_fix.py
```

The shared builder requires `C:\Python27\python.exe`, reads `WG_APP_ID` from
the project-local `.env`, rejects missing/empty/whitespace/placeholder/malformed
values, and injects the validated value into a temporary staged source file.
The repository source remains unconfigured by design.

Its exact compileall command is:

```text
C:\Python27\python.exe -m compileall res\scripts\client\gui\mods\mod_shotcaller.py
```

The same staged bytes are copied to `source/mod_shotcaller.py` before compileall
and are verified equal. The generated Python 2.7 `.pyc` is loaded for a safe
configured-ID verification without printing the value. Raw staged runtime
source is removed before packaging.

The 0.0.79 archive is written with `ZIP_STORED` only and must contain exactly:

```text
meta.xml
source/mod_shotcaller.py
res/scripts/client/gui/mods/mod_shotcaller.pyc
res/gui/flash/shotcaller/shotcallerVehicleWindow.swf
res/gui/flash/shotcaller/shotcallerVehicleFilters.swf
```

The builder audits entry names, compression method, readable-source equality,
forbidden sidecar/config/log/credential-like archive entries, and Python 2.7
magic. Do not add a sidecar, runtime environment variable, user configuration,
or metadata-based application-ID mechanism to this release path.

## Installation

Confirmed packaging research identifies the conventional install destination as
the game's versioned `mods` directory:

```text
<World of Tanks install>\mods\<game-version>\shotcaller_0.0.79_chunked_rate_limit_fix.wotmod
```

Do not unpack the archive into `res_mods` for the normal packaged workflow.
At runtime, ShotCaller creates/uses settings and cache data below:

```text
<World of Tanks install>\mods\configs\shotcaller\
    vehicle_filters.json
    cache\
```

The exact installed game-version directory name must match the active WoT
client. Verify that name in the user's installed client before deployment.

## Verification completed for 0.0.79

The stable build wrapper ran the complete current Python 2.7 regression suite:

- history-state classification;
- platoon source precedence/merge;
- vehicle battle normalization;
- vehicle catalog cache and class resolution;
- native lookup/cache/staleness behavior;
- in-place history navigation refresh;
- existing WG API batch recovery;
- 0.0.79 chunk/rate-limit recovery;
- WR and clan watermark behavior;
- WGMods lifecycle (including no module-scope `init()` call);
- build-time application-ID injection and verification.

The dedicated 0.0.79 coverage confirms: 15 accounts split 8+7; the final
account ID remains complete; results preserve roster order; only a failed chunk
is recovered; recovery is sequential; rate-limit callbacks use the required
delays and can succeed on a later retry; exhaustion creates one final error;
stale identity cancels a pending retry; and logs do not expose the application
ID or full URL/query string.

The package was audited after build for the exact five entries, `ZIP_STORED`,
injected readable source matching compileall source, compiled configured-ID
verification, and presence of the chunk/retry runtime constants.

## Known limitations, risks, and unresolved facts

### Confirmed limitations and fragile points

- The supported tier set is only VI/VIII/X. Other/mixed/incomplete selections
  show informational/pending states rather than public-history lookup.
- The roster cap remains 15 eligible players per lookup. This matches the
  current implementation, not a general arbitrary-size roster contract.
- The tanks/stats global sequential gate protects against bursts but can make a
  large cold-cache roster take longer to finish, especially during rate limits.
- A permanent WG/API failure can leave an account in an API-error state when no
  stale cache is available. A successful response can also omit an account.
- The custom Scaleform views, WoT imports, class/method names, and view
  registration contract are client-integration points that can break after a
  game update. The generic history fallback mitigates only certain custom-view
  failures.
- `BigWorld.fetchURL` is logical-cancellation only: the runtime ignores late
  callbacks, but the client primitive has no audited physical cancellation API.
- The existing local-clan resolution has observed fragile API/URL behavior in
  prior runtime logs. The committed implementation includes guarded fallback
  and diagnostics, but this handoff cannot confirm a live 0.0.79 clan lookup
  against all regions.
- Older docs and the prototype README contain historical sidecar wording,
  package layouts, version labels, and experimental notes. Treat current source
  and the stable commit as authoritative.

### Inferred behavior requiring verification

- The native transport decision is documented from WoT **2.3.1.0** source/live
  investigation. Compatibility with later game client builds must be verified
  in game, particularly `BigWorld.fetchURL`, Scaleform aliases, and hook names.
- Conventional `.wotmod` install location is documented, but no live install
  on every current WoT release is recorded in this handoff.
- The 1800-character URL limit is a conservative runtime safeguard. It is not
  documented here as an official WG or WoT limit.
- The 0.0.79 test suite verifies mocked asynchronous behavior. It does not
  replace live Advances testing in each realm under actual WG rate pressure.
- The exact UI text/layout and current SWF behavior should be confirmed from
  the compiled SWFs/live client if a future change depends on them; this
  handoff relies on source/tests and repository documentation.

## Proposed next-version work only

Do not implement these items as part of maintaining 0.0.79. Their feasibility,
UI contract, persistence schema, and in-game behavior require a fresh scoped
change and verification.

- Add a clan-logo transparency slider to the settings menu.
- Add sorting within the existing tank-type groups by Name, Win rate, and
  Battle count. Preserve alphabetical Name sorting as the available/default
  option unless a new source review establishes otherwise.
- Add a numeric minimum-battles filter with manual numeric entry, up/down
  one-step controls, minimum zero, and zero disabling the filter. Tanks below
  the selected battle count would be hidden to reduce rental/sold/barely played
  vehicles.
- Make each tank-type section independently collapsible without permanently
  hiding a type; consider a tank count on collapsed headings.
- Investigate a ShotCaller launcher icon/button in platoon and
  skirmish/Stronghold windows. Retain `Ctrl+Alt+V` as the permanent fallback,
  especially when a game update breaks injected UI elements.

## Safe next-version start checklist

1. Start from a clean tree at or after `e0edd37`; record the intended new
   version and package name before editing.
2. Read this handoff, the current runtime source, relevant ActionScript source,
   and the exact tests covering the proposed change. Do not rely on old
   prototype README headings alone.
3. Preserve the WoT lifecycle contract: public `init()` only, no module-scope
   initialization call, and Python 2.7 compatibility.
4. Preserve native standalone operation, staged `WG_APP_ID` injection, masked
   diagnostics, readable-source inclusion, and the exact ZIP_STORED archive
   audit unless the new work explicitly and safely changes packaging.
5. Extend tests first or alongside behavior changes; include regressions for
   roster order, stale identity, cache fallback, view failure paths, and privacy
   when the affected area touches them.
6. Re-run the shared builder's complete Python 2.7 suite and archive audit.
7. Perform focused in-game validation on the active WoT build for any changed
   hook, Scaleform, input, or network behavior; record client version and logs
   without exposing the application ID.
8. Keep `Ctrl+Alt+V` usable as the reliable launch/recovery path even if a
   future injected launcher control is added.
