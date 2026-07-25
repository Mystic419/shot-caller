# Shot-caller WoT Mod Integration Plan

## Scope

This document starts the research phase for integrating the existing `shot-caller` backend into a World of Tanks client mod.

The goal of this phase is not to build the real UI yet. The goal is to:

- document the likely WoT mod packaging and runtime constraints
- identify the safest first hook points
- identify where the current backend is incompatible with the WoT client runtime
- define a minimal prototype order that proves assumptions in-game before larger work

## Current local project facts

Confirmed from the current repo:

- The backend already talks to the public Wargaming API.
- It already supports batch roster preload and Tankopedia caching.
- It already builds the tier -> tank type -> tank config catalog.
- It already persists hidden tank state via `excluded_tanks.json`.

Relevant implementation details in the current codebase:

- `shot_caller/wg_api.py` uses `requests`.
- `shot_caller/lookup.py` uses `concurrent.futures.ThreadPoolExecutor`.
- Multiple modules use modern Python 3 syntax and libraries:
  - `from __future__ import annotations`
  - `pathlib.Path`
  - `dataclasses`
  - PEP 585 built-in generics like `dict[str, ...]`
  - union operator syntax like `Path | None`

Conclusion:

- The current backend is a good source of business logic.
- It is not directly drop-in compatible with WoT's embedded Python runtime.

## 1. Expected World of Tanks mod package structure

### Confirmed

Public WoT modding docs consistently describe two installation forms:

1. `res_mods/<version>/...`
2. `mods/<version>/<something>.wotmod`

Likely structures:

```text
World_of_Tanks/
|- res/
|- res_mods/
|  |- <client_version>/
|  |  |- scripts/
|  |  |  |- client/
|  |  |     |- mods/
|  |  |     |- gui/mods/
|  |  |- gui/
|  |  |  |- flash/
|  |  |  |- unbound/
|  |- configs/
|     |- <mod_name>/
|- mods/
|  |- <client_version>/
|     |- <mod>.wotmod
|- python.log
|- version.xml
```

Typical `.wotmod` contents:

```text
<mod>.wotmod
|- meta.xml
|- res/
   |- scripts/
      |- client/
         |- gui/
            |- mods/
               |- mod_<name>.pyc
```

### Assumption to verify in-game

- For this project, a small Python entrypoint in `scripts/client/gui/mods/` is the most likely starting point.
- If the detachment room is still legacy lobby code, we may also need Flash assets later.
- If the target screen is already migrated, we may need Gameface / `gui/unbound/` later instead.

## 2. Where mod files likely live under the game folder

### Confirmed

- `res_mods/<version>/...` is the unpacked override location.
- `mods/<version>/...` is the packaged `.wotmod` location.
- `res/` is base game data and should not be edited.
- `python.log` lives at the game root and is the first place to verify load success.

### Practical recommendation

Use `res_mods` for the earliest local prototypes and move to `.wotmod` only after the load path and hook points are proven.

## 3. How Python mods are loaded by WoT

### Confirmed

Based on public modding docs:

- WoT looks for mod files in the client script paths under the versioned mod folders.
- The `mod_` filename prefix is important.
- The client calls `init()` on matching mod modules.
- Load order is described as alphabetical for GUI mod files.
- Logging via `print` ends up in `python.log`.

### Likely loading model

Minimal entrypoint shape:

```python
def init():
    print('[shotcaller] loaded')

def fini():
    print('[shotcaller] unloaded')
```

### Important unresolved detail

There is a documentation conflict:

- One public page says `res_mods` development can use plain `.py`.
- Another public page says WoT expects compiled `.pyc`, and shows plain `.py` only together with ScriptLoader tooling.

Because of that conflict, the first real prototype must test this directly:

- first try stock-compatible `mod_shotcaller.pyc`
- do not assume raw `.py` hot-loading works in the target client

## 4. Known constraints around WoT's Python version and standard-library support

### Confirmed

Public modding references describe the WoT Python layer as `Python 2.7`.

Implications:

- No native `async` / `await`
- No `dataclasses`
- No `pathlib`
- No PEP 585 generics like `dict[str, int]`
- No `X | Y` type-union syntax
- No Python 3-only string and typing conveniences

### Likely available standard library

Reasonable Python 2.7-era assumptions:

- `os`
- `json`
- `threading`
- `time`
- `urllib`, `urllib2`, `httplib`
- `Queue`
- possibly `logging`

### Assumption to verify

- Third-party packages should be treated as unavailable unless proven otherwise.
- `requests` should be treated as unavailable in the stock WoT client.

## 5. Whether the current package code may need compatibility changes

### Short answer

Yes. Major changes would be required if we tried to run the existing package directly inside the WoT client.

### Confirmed incompatibilities from the current repo

- `shot_caller/wg_api.py` imports `requests`.
- `shot_caller/lookup.py` uses `ThreadPoolExecutor`.
- `shot_caller/config.py` and others use `pathlib.Path`.
- Several modules use Python 3-only typing syntax.
- Several modules use `dataclasses`.

### Likely compatibility risk list

- `requests` dependency probably unavailable
- `concurrent.futures` may be absent or incomplete in the client runtime
- `dataclasses` unavailable
- `pathlib` unavailable
- typing syntax would need backport or removal
- `from __future__ import annotations` is not enough to make the rest Python 2.7-safe

### Recommended architectural conclusion

Do not port the whole backend into the WoT client first.

Prefer this split:

1. Tiny WoT-side Python 2.7 shim
2. Existing modern Python backend kept outside the game as a local sidecar or helper service
3. Small JSON/HTTP bridge between them

Why this is safer:

- preserves the existing backend mostly as-is
- minimizes risky WoT-runtime rewrites
- keeps WoT-side code focused on UI hooks, roster extraction, and popup display
- avoids forcing Python 2.7 compatibility across the whole project

## 6. How garage UI mods typically add buttons or panels

### Confirmed

Public WoT docs describe the garage / lobby as mostly Gameface / Unbound in modern clients.

Likely workflow:

- patch a lobby view lifecycle method such as `_initialize`
- access or extend the corresponding ViewModel
- or inject/override Gameface assets if the target view is already in modern UI

Examples from public docs use `gui.impl.lobby...` classes and `_initialize`.

### Practical implication for Shot-caller

The future harmless garage proof should probably use a garage-side hook first because:

- it is easier to verify load success visually
- it avoids the stronger uncertainty around the detachment room

### Assumption

- A tiny temporary garage label or button is likely easier than going straight into Stronghold UI.

## 7. How detachment / Stronghold room UI might be discovered or hooked

### Confirmed

There are stronghold-related modules in public decompiled client references, including paths like:

- `gui/prb_control/entities/stronghold/unit/entity.py`
- `gui/clientgw/strongholds/contexts.py`
- `gui/impl/lobby/stronghold/...`

This strongly suggests:

- Stronghold / detachment state is represented in Python
- there are dedicated request/context objects for stronghold actions
- there is a room/unit entity layer that tracks members, ready state, slot state, and roster constraints

### Practical discovery plan

Search the decompiled source for:

- `stronghold`
- `unit`
- `prb_control`
- `slot`
- `member`
- `tooltip`
- any lobby view alias or view class that corresponds to detachment windows

### Likely hook surfaces

- room/unit entity lifecycle
- member-list changed callbacks
- slot update callbacks
- ready-state or room-state listeners
- the visual row renderer or tooltip provider for member rows

### Assumption

- The detachment room may still involve older prebattle / legacy UI paths even in a modern client.
- That means the Stronghold room could be less straightforward than the garage and may not be pure Gameface.

## 8. How to detect selected detachment tier

### What we know

Public Stronghold internals clearly include roster and slot filtering concepts.

From decompiled stronghold references:

- there is a `StrongholdDynamicRosterSettings`
- there are `minTotalLevel` / `maxTotalLevel`-style roster values
- there are slot vehicle filter request/update concepts like `SlotVehicleFiltersUpdateCtx`

### Best current hypothesis

Selected detachment tier is likely discoverable from one of:

1. room roster settings
2. allowed vehicle filters per slot
3. selected division / battle mode settings that imply a fixed allowed tier

### Practical interpretation for Shot-caller

The cleanest first implementation is probably:

- read the room's effective allowed vehicle level from roster or slot filters
- map it to `6`, `8`, or `10`

### Status

- plausible
- not yet proven
- should be treated as a prototype task, not a solved fact

## 9. How to read visible player names in the detachment list

### Likely sources

Detachment player names are likely accessible through the Stronghold unit/member model, not only by scraping visuals.

Why this is likely:

- stronghold unit/entity code exposes member-list change concepts
- prebattle/unit systems in WoT usually keep structured member/player info in Python

### Recommended preference order

1. Read names from the Python unit/member model
2. Only fall back to row-text scraping if the visual layer does not expose usable structured data

### What to look for

- member objects with player DBID and display name
- clan member vs legionary flags
- slot index -> player mapping
- callbacks such as member-list changed or slot-changed handlers

### Status

- likely feasible
- exact class/property names still TODO

## 10. How to attach hover behavior or display a popup

### Likely options

1. Hook the row renderer / tooltip event for detachment member rows
2. Reuse an existing tooltip framework
3. Inject a small custom popup overlay near the hovered row

### Best practical prototype path

For the first hover prototype, do not start with live backend data.

Instead:

- detect row hover
- show a static popup like `Test popup: E 100 / IS-7 / CS-63`

This proves the hardest UI interaction before networking logic is added.

### Risk

- Hover behavior may belong to legacy Scaleform tooltip code rather than a neat Python-only hook.
- If so, a popup may require either a Flash-side modification or reuse of existing tooltip plumbing.

## 11. Safe networking considerations

### `requests` availability

Recommended assumption: `requests` is not available in stock WoT client Python.

Reason:

- WoT embeds Python 2.7
- public docs do not describe third-party package availability
- shipping a mod that assumes `requests` exists is risky

### `urllib` vs `requests`

Recommended default for WoT-side code:

- use Python 2.7 stdlib HTTP only if the WoT mod itself absolutely must make requests
- prefer `urllib2` / `httplib` style client code over `requests`

### Best architecture for this project

Prefer not to do direct Wargaming API networking from the WoT mod at all.

Instead:

- keep the existing modern backend as a local helper process
- have the WoT mod ask that helper for already-shaped results

This reduces:

- Python 2.7 compatibility pain
- duplicated HTTP code
- duplicated cache logic
- in-client blocking risk

### Background work

Do not do blocking network calls on the UI thread.

Safer options:

1. local helper process + quick polling or callback-style integration
2. background `threading.Thread`
3. WoT async patterns such as `adisp` where appropriate

### Practical recommendation

For WoT-side code:

- do fast UI work on the main thread
- do HTTP or disk-heavy work off the immediate UI callback path
- return cached or placeholder popup content first if needed

## 12. File storage location for Tankopedia cache, `excluded_tanks.json`, and local settings

### Recommended layout

Use WoT community config conventions instead of the current repo-root layout.

Recommended paths:

```text
res_mods/configs/shotcaller/settings.json
res_mods/configs/shotcaller/excluded_tanks.json
res_mods/configs/shotcaller/tankopedia_na.json
res_mods/configs/shotcaller/cache/
```

### Why

- matches common WoT mod conventions
- keeps state outside versioned code folders
- survives client version folder changes better than `res_mods/<version>/...`
- keeps user-editable config in one predictable place

### Suggested split

- `settings.json`
  - selected tier button default
  - popup enable/disable
  - helper-service URL/port if needed
- `excluded_tanks.json`
  - hidden tank IDs
- `tankopedia_na.json`
  - cached Tankopedia data
- `cache/players/...`
  - optional per-player lookup cache if later added

### Note about current code

Current local code expects:

- `.cache/tankopedia_na.json`
- root-level `excluded_tanks.json`

Those paths should be abstracted before any WoT embedding attempt.

## 13. Risks and unknowns

### High-confidence risks

- The current backend is not WoT-Python-compatible as written.
- `requests` is likely unavailable in-client.
- Direct UI hooks for Stronghold rows are still uncertain.
- The detachment room may be legacy UI and more awkward than the garage.

### Important unknowns

- Whether stock client wants `.pyc` only in `res_mods`, or whether `.py` is accepted in the target setup
- Exact detachment room class / view name to patch
- Exact field or callback for selected Stronghold tier
- Exact structured source for visible member names
- Whether hover popup can be done Python-only or needs visual-layer work

### Secondary risks

- Mod conflicts if the chosen hook point is popular
- client updates moving or renaming Stronghold classes
- UI freeze if backend calls are synchronous
- local helper-service lifecycle complexity if we choose a sidecar design

## 14. Recommended first in-game prototype

### Prototype order

1. Minimal mod load
2. Tiny garage UI proof
3. Detachment detection
4. Shotcaller config button
5. Hover popup
6. Backend integration

### 1. Minimal mod load

Goal:

- confirm file placement
- confirm `mod_` naming
- confirm `.pyc` requirement
- confirm logging path

Success criteria:

- WoT launches
- `python.log` contains `Shotcaller loaded`
- no UI changes yet

### 2. Prototype 2: garage/lobby hook test

Goal:

- prove we can patch a known lobby/garage lifecycle safely
- package a harmless Python 2.7-compatible hook as an uncompressed
  `ZIP_STORED` `.wotmod`

Success criteria:

- `python.log` contains `[shotcaller] loaded`
- `python.log` contains `[shotcaller] garage hook fired`
- no Stronghold code yet

Implementation boundary:

- hook only a garage/lobby lifecycle method, with installation guarded by
  `try/except`
- do not add a detachment UI, popup, configuration, API lookup, helper, or
  backend integration

### Prototype 2C: legacy Hangar lifecycle proof

Prototype 2B confirmed that the client executes the `.pyc` package and that
`gui.Scaleform.daapi.view.lobby.hangar.Hangar` is available. Prototype 2C
patches only the first available Hangar lifecycle method in this order:

1. `_populate`
2. `_dispose`
3. `_onRegisterFlashComponent`
4. `init`

The patch preserves the original method, is guarded against duplicate
installation, and logs installation plus callback firing. It must not add UI,
Stronghold/detachment behavior, API lookup, helper, or backend integration.

### Prototype 2D: modern WULF/Gameface Hangar discovery

Prototype 2C found no usable lifecycle method on the legacy Scaleform
`Hangar` class. Client logs instead identify `HangarWindow`, `RandomHangar`,
the Gameface `mono/hangar/main` view, and a ready-state message. Prototype 2D
must not patch anything yet; it should import a small set of modern hangar,
window, WULF, and lobby-state modules and log matching class/function names.

Use the resulting import and candidate logs to select one concrete lifecycle
method for the next harmless hook proof. Keep the package as a Python 2.7
`.pyc` in a `ZIP_STORED` `.wotmod` with root `meta.xml`.

### Prototype 2E: lobby state navigation hook

Prototype 2D found `gui.lobby_state_machine.lobby_state_machine`,
`gui.lobby_state_machine.states`, `isHangarState`, and
`GuiImplViewLobbyState`. Prototype 2E logs methods on the relevant state
classes before patching at most two clear points: first
`LobbyStateMachine.goTo`, then `GuiImplViewLobbyState._onEntered` if present.

Each wrapper calls the original method before inspecting a short,
exception-safe representation of `self` and its arguments. It logs only
Hangar contexts, identified by `hangar` text or `isHangarState(self)`. Keep
this to a lifecycle proof: no UI, Stronghold/detachment behavior, lookup,
helper, or backend integration.

### Prototype 3A: Stronghold battle-room detection

Prototype 2E did not fire in the tested Stronghold flow. The client logs
identified `StrongholdVehiclesWatcher`, `StrongholdBattleRoomWindow`, and the
Stronghold browser URL path ending in `battlerooms`. Prototype 3A wraps
`StrongholdVehiclesWatcher.start` and `.stop` when present, then inspects at
most two WULF/window initialization paths for the exact battle-room alias.

Wrappers call original methods first, only log detection evidence, and avoid
duplicate patching. Browser support is probe-only. Do not add battle UI,
roster lookup, API lookup, configuration, helper, or backend behavior.

### Prototype 3B: Stronghold context probe

Prototype 3A confirmed watcher start/stop and the Stronghold battle-room
window alias. Prototype 3B keeps those hooks and adds bounded, read-only
diagnostics on watcher start and the first `_update`: class/self information,
attribute and method inventories, plus short details for candidate names such
as unit, roster, player, member, vehicles, level, division, queue, and state.

Only guarded getter-style no-argument methods may be called; never call
methods that appear to mutate state. Rate-limit later update logs. Run once for
basic window detection and again during active Stronghold hours for richer
roster/tier evidence. No UI, lookup, configuration, helper, or backend work.

### Prototype 3C: Stronghold entity/unit/roster probe

Prototype 3B showed that the watcher is primarily a vehicle suitability/cache
layer, not the roster source. Prototype 3C should map the Stronghold entity,
unit, context, item, requester, and PRB dispatcher modules, then make one
guarded getter-only probe when the watcher starts. Prefer `prb_getters`, the
PRB dispatcher entity, and no-argument entity getters such as unit data,
roster, players, members, and commander DBID.

Log short values and bounded keys/attributes for roster-like data. Never call
methods that could alter session state. Retain battle-room and browser URL
detection. No UI, external lookup, helper, configuration, or backend work.

### Prototype 3D: Stronghold entity lifecycle/data hook

Prototype 3C found the correct Stronghold entity class family but not a live
instance through PRB getters or dependency lookup. Prototype 3D hooks existing
lifecycle/data methods on `StrongholdEntity` and `StrongholdBrowserEntity`,
then inspects the live `self` object after original methods return.

Keep the hook list small and bounded; deeply inspect only the first few fires
per class/method. Use only safe no-argument getters and never invoke methods
that could mutate Stronghold state. Retain watcher, battle-room window, and
browser URL detection. No UI, external lookup, helper, configuration, or
backend work.

### Prototype 3E: focused Stronghold roster/player/tier probe

Prototype 3D confirmed a live `StrongholdBrowserEntity` and identified the
safe getters for unit data, roster, stats, members, players, vehicles, and
PlayerUnitInfo. Prototype 3E should hook only the BrowserEntity lifecycle and
unit callbacks, call originals first, and dump focused state on initialization,
unit loading, shutdown, and only the first five unit events.

Log bounded PlayerUnitInfo fields, roster setting level/slot ranges, stats, and
VehicleInfo values. Run during active Stronghold hours for populated data. No
mutating calls, UI, external lookup, helper, configuration, or backend work.

### Prototype 3F: delayed Stronghold unit/roster capture

Prototype 3E proved BrowserEntity hooks and PlayerUnitInfo vehicle-CD access,
but the captured room was still empty. Prototype 3F schedules delayed dumps
after initialization and unit loading, keeps listening to all unit callbacks,
and snapshots roster IDs/names/slots/vehicle-CD counts in memory.

Suppress unchanged scheduled snapshots while always logging count changes and
unit events. Inspect slot iterators safely and cap both slot records and total
dumps. Run during active Stronghold hours. No state mutation, file writes, UI,
external lookup, helper, configuration, or backend work.

### Prototype 3G: Stronghold web/browser bridge probe

Prototype 3F confirmed that BrowserEntity state remains empty even when the
Stronghold web flow is active. The client then exposes `StrongholdView` and the
WG Stronghold SPA URL, so Prototype 3G moves discovery to BrowserController,
lobby browser modules, web handlers, and event modules.

Patch only existing browser lifecycle and obvious message-dispatch methods;
call originals first and log bounded payload context. Keep Stronghold view,
battle-room window, and URL detection. Do not send messages or otherwise alter
browser/game state; no UI, external lookup, helper, configuration, or backend
work.

### Prototype 3H: Stronghold web response/callback probe

Prototype 3G captured `strongholds_battle` web-to-client commands, including a
live `join_battle` unit ID, but no roster payload. Prototype 3H retains
`BrowserViewWebHandlers.handleCommand` and inspects the response/callback path
on Browser, BrowserController, WebBrowser, and EventBus methods.

Track web IDs to correlate requests with later callbacks, log bounded payloads,
and avoid repeated noise. Keep view/window/URL detection. Never send browser
messages or modify state; no UI, external lookup, helper, configuration, or
backend work.

### Prototype 3I: StrongholdEvent introspection probe

Prototype 3H confirmed the response path and repeated `StrongholdEvent` calls.
Prototype 3I inspects bounded event snapshots and safe getters while tracking
web-id/action correlations. Mask token, session, auth, password, and secret
values before logging. Keep all behavior read-only.

### Prototype 3J: StrongholdClanData and event-type probe

Prototype 3I identified active Sortie tier/state in `strongholdOnTimer` and a
live StrongholdClanData object. Prototype 3J filters repeated timer events,
inspects each clan object once through safe attrs/getters, and prioritizes
vehicle-selection and other non-timer Stronghold events. Mask sensitive web
values and keep all behavior read-only.

### Prototype 3K: external waiting manager and post-join entity probe

Prototype 3J showed clan identity/status but no roster. Probe
`BaseExternalUnitWaitingManager`, register live Stronghold/unit entities, and
run delayed post-join getter-only captures. Keep all behavior read-only.

### Prototype 3K findings

- `StrongholdBrowserEntity` became live before joining and `StrongholdEntity`
  plus `BaseExternalUnitWaitingManager` became live after waiting-room entry.
- The native client still logged `Unit roster is not definded`; its entity
  roster remained undefined.
- The actual Skirmish waiting room visibly displayed seven active detachment
  members and their selected vehicles despite that missing native roster.

The screenshot clarifies that the target is a legacy Scaleform Skirmish
waiting-room view, not the browser battle-room selector, vehicle popover,
hangar, or regular platoon UI. It has separate Volunteers and Detachment
Members lists and already renders selected vehicle data for every active row.

### Prototype 3L: Skirmish UI and roster data-provider probe

Probe the legacy Scaleform lobby/rally/stronghold view and data-provider path.
Import only available candidate modules; hook only existing view lifecycle,
`as_*S`/data methods, relevant provider methods, Scaleform component
registration, and the safe waiting-manager request/response methods. Every
wrapper must call the original unchanged, use bounded masked logging, avoid
timer/reserve noise, and never mutate UI/game state or send browser/API calls.

Success criteria, in increasing strength:

- `skirmish target view identified` or `skirmish view hook fired`
- `skirmish data hook fired` with a masked payload
- `member row captured` containing an actually displayed name and vehicle
- `volunteer row captured` containing a waiting player

Keep listening through battle/return/join/leave/vehicle changes, with lightweight
member and volunteer snapshots that log roster additions, removals, and vehicle
changes without requiring the room to be reopened.

### Prototype 3L failure and 3L-repair

Prototype 3L failed during client startup. Its broad framework monkey-patching
wrapped shared Scaleform settings/framework classes and caused
`AttributeError: 'function' object has no attribute 'DAMAGED'` from the
trade-in popup, followed by `Package gui.Scaleform.daapi.view.lobby does not
have method getViewSettings`.

Prototype 3L-repair is intentionally narrow: it only discovers names from the
rally, rally data-provider/VO converter, strongholds, and fortifications
modules. It may wrap only the explicitly named functions in
`gui.Scaleform.daapi.view.lobby.rally.vo_converters`; it retains only the three
directly owned `BaseExternalUnitWaitingManager` hooks. No framework/global view
settings/classes, constructors, inherited methods, module-level lobby methods,
component registration paths, or `__setattr__` hooks are permitted.

### Prototype 3L-repair findings and Prototype 3M

Prototype 3L-repair reached the hangar normally and its narrow converter hooks
fired in the Skirmish waiting room. `makeSlotsVOs` returned the complete active
Detachment Members roster as `(boolean, list_of_slot_dicts)`. Each occupied slot
contains player DBID/name/clan/rating/readiness/commander state plus its selected
vehicle name, compact descriptor, tier, type, and readiness; it also supplies
slot order and legionnaire state.

Prototype 3M wraps only `makeSlotsVOs` as the primary source and the three
named player/vehicle converters as optional supporting hooks. It converts only
occupied slots into an in-memory, DBID-keyed cache with order, unit ID, tier,
and generation. It produces concise initial/change logs for members, vehicles,
readiness, commander state, slots, and removals—without raw converter payloads
or duplicate unchanged snapshots. Success requires cache population, valid tier
detection, live change logging, and no startup/lobby errors.

### Prototype 3M success and Prototype 3N validation

Prototype 3M succeeded: it reached the hangar normally and populated an
in-memory seven-member Tier 8 cache for unit `6849134`. Captured rows included
DBID, player identity/clan/rating, ordered slot, selected vehicle/intCD,
commander, and legionnaire state. It also cleared the cache on unload without
raw payload spam.

The observed `ready=False` values are not yet classified as incorrect because
the capture was made during battle, when `isFreezed=True`, `playerStatus=3`,
and `selectedVehicle.isReadyToFight=True` were present. Prototype 3N preserves
player readiness, vehicle readiness, player status, frozen status, and explicit
in-battle state independently. It validates these in waiting and battle states,
plus live updates, two-empty-snapshot protection, unit transitions, safe
watcher-stop clearing, and a separate possible-volunteer cache. No APIs, UI,
helper, or persistence are added.

### Prototype 3N ready-state result and detachment-exit validation

Prototype 3N confirmed that readiness extraction is correct. In battle,
`player_ready=False`, `vehicle_ready=True`, `player_status=3`, and
`is_frozen=True`; after returning, status becomes `0` and frozen becomes false.
Ready clicks change `player_ready` to true and status to `2`; battle launch
changes status back to `3` and freezes the slot without overwriting player
readiness. The cache now derives `in_battle` strictly from frozen or status 3.

The remaining validation is detachment exit without closing WoT. Watcher stop
now schedules a one-second token-protected clear. Watcher start and a populated
roster update explicitly cancel it; otherwise both roster and volunteer caches
clear with `reason=Stronghold watcher stopped`.

### Prototype 3O: reliable detachment-exit lifecycle

Prototype 3N completed the full battle-state validation: ready/unready,
battle-start/end, and selected-vehicle changes all update the cache correctly;
unchanged snapshots remain suppressed. Status `0`, `2`, and `3` respectively
mean not ready, ready, and in battle/frozen. `in_battle` is now a derived
read-only field from frozen or status 3 and never changes player readiness.

Prototype 3O focuses solely on reliable exit while WoT stays open. It retains
only the four proven converter hooks and hooks only direct `start`/`stop`
methods on the exact Stronghold watcher class. The lifecycle state machine uses
watcher and populated-roster generations plus a one-second pending exit token.
It must ignore a transient replacement stop but clear active and volunteer
caches after a confirmed normal detachment exit, then support fresh re-entry.

### Prototype 3O failure and 3O-repair

Prototype 3O's watcher lifecycle hooks never installed because `start` and
`stop` are inherited from `BaseVehiclesWatcher`; the strict subclass
`__dict__` safety check therefore skipped both. Native logs nevertheless
confirmed that the base methods are the correct lifecycle source.

Prototype 3O-repair patches only direct `BaseVehiclesWatcher.start`/`.stop`
methods, then strictly filters every wrapper call to actual
`StrongholdVehiclesWatcher` instances using `isinstance` (with exact module and
class-name fallback). Ordinary base watcher calls do not mutate state or cancel
an exit. The probe logs hook origins/installation, supports transient
Stronghold replacement cancellation, and clears only after an un-replaced,
un-updated one-second stop confirmation.

### Prototype 3O-repair validation and Prototype 4A

Prototype 3O-repair is validated: base watcher origins were confirmed, hooks
installed, Stronghold instances filtered, transient stop/start replacement
cancelled, and a real detachment exit cleared the populated roster after one
second while WoT remained open. The roster subsystem is now considered live
and safe for a consumer.

Prototype 4A introduces a localhost-only bridge to the existing modern backend.
`python -m shot_caller.sidecar` binds to `127.0.0.1:37841`, exposes `GET
/health` and validated `POST /lookup/roster`, and reuses WG client/tankopedia
logic with a ten-minute successful per-player/tier cache. It returns all
public-history vehicles at the requested tier, ordered by battles then name.
The embedded mod uses background standard-library HTTP only, sends no client
credentials/chat/battle data, rejects stale generation/unit responses, and
keeps lookup results in memory. Public history is explicitly not proof of
current garage ownership.

### Prototype 4A result and timeout repair

Prototype 4A proved the localhost trust boundary: the WoT mod queued a
seven-player Tier VIII request and `/health` reported the sidecar available.
The initial roster POST exceeded the embedded client's former five-second
timeout, however, because the sidecar performed player histories sequentially.

The 4A repair keeps sidecar health (`unknown`/`available`/`unavailable`) apart
from lookup execution (`idle`/`queued`/`running`/`complete`/`timeout`/`error`).
Health remains available after a POST timeout. The WoT background POST timeout
is 30 seconds; all responses carry and are checked against unit ID, tier, and
generation. The sidecar serves cache hits immediately and requests all cache
miss DBIDs through the supported bounded-concurrency tank-stat path, loading
tankopedia at most once per batch and preserving request order with per-player
statuses. A direct API diagnostic confirmed that WG rejects the attempted
comma-separated `account_id` format, while individual account requests succeed;
the sidecar now logs that batch-level distinction and classified failures rather
than silently returning seven `api_error` rows. A direct seven-player test
completed successfully with all structured `ok` results.

### Prototype 4A-repair validation and Prototype 4B

Prototype 4A-repair was validated under WoT 2.3.1.0: the roster/watchers stayed
stable, sidecar health reported version 0.0.26, vehicle history arrived in WoT
memory (including a 55-vehicle Tier VIII result), and detachment exit cleared
both roster and lookup caches.

Prototype 4B is a read-only legacy Scaleform/DAAPI hover-target probe. It
retains the validated bridge unchanged and dynamically limits inspection to
Stronghold/Skirmish rally room, slot, member, mouse, and tooltip candidate
methods directly owned by Stronghold-specific classes. Candidate methods log
safe argument types once. When a slot/DBID is available, the existing cache
produces deduplicated hover enter/exit logs with lookup state and cached vehicle
count. No custom tooltip is rendered until this event path is confirmed.

### Prototype 4B result and tooltip-request repair

Prototype 4B was safe but ineffective: its direct Stronghold/rally hover scan
installed zero hooks and therefore produced no row enter/exit event. The live
room evidently routes mouse activity through the legacy tooltip request flow
rather than a directly owned roster-renderer hover method.

Prototype 4B-repair enumerates only tooltip-named candidates in the narrow
Stronghold/rally/battle-room and shared legacy tooltip modules, logging direct
ownership without object representations. It selects at most one direct
Stronghold-specific request callback; if none exists, it selects at most one
narrow shared legacy entry point. Safe scalar request values are correlated to
the existing slot/DBID/vehicle cache, and no new lookup or tooltip content is
introduced until the live callback is confirmed.

### Prototype 4B-repair result and Prototype 4C

Prototype 4B-repair found only `WindowLayer.TOOLTIP` in the queried Fortification
module. It is a constant rather than a callable request route, and no roster
tooltip callback fired during extensive live hovering. This supports the
conclusion that the legacy Stronghold renderer owns hover behavior in
ActionScript rather than exposing it through a useful Python callback.

Prototype 4C disables the tooltip request scan and probes only the already
validated `makeSlotsVOs` output. The reference client source shows
`makeSlotsVOs` passes `_getSlotsData` to `as_setMembersS`; nested vehicle VOs
include a native `tooltip` field for invalid/restricted vehicle state, while
slot/player VOs do not document a general custom tooltip field. The live probe
will log deduplicated top-level/nested schemas and safe candidate scalars from
the actual 2.3.1.0 rows. It does not mutate VOs or apply a marker until a
supported field/renderer contract is proven.

### Prototype 4C result and selected-vehicle marker test

Live screenshots established two native Stronghold roster hover zones: the
player-name area displays full name and the selected-vehicle area displays
`Player's vehicles`. Prototype 4C confirmed the nested live field
`selectedVehicle.tooltip` exists and is normally `None`.

Prototype 4D retains one concise schema confirmation and performs one local-row
marker test before the `makeSlotsVOs` result is consumed. It sets
`selectedVehicle.tooltip` only when the row is the authenticated user,
vehicle/intCD/tier are valid, and the existing tooltip is empty. A non-empty
native restriction tooltip is never overwritten. The result distinguishes
whether the field controls normal vehicle hover (marker appears) or is ignored
(the existing `Player's vehicles` tooltip remains), with no custom UI added.

### First-slot marker repair

The first marker test did not apply because the authenticated player was in the
Volunteers panel, not an active Detachment Members slot. The marker logic was
correctly non-invasive but did not test the field. The repair prefers an active
local slot; otherwise it marks only the first eligible active roster row for
the current roster generation, still requiring a valid tier, vehicle compact
descriptor, and empty native tooltip field.

### Prototype 4E result and Prototype 5A

Prototype 4E applied the marker to slot 0, but hovering that exact vehicle
still displayed the native `Player's vehicles` text. This proves the legacy
Stronghold ActionScript renderer ignores `selectedVehicle.tooltip` for the
normal vehicle hover. Tooltip-field scanning and all marker mutations stop
here.

Prototype 5A is the first real read-only panel. A per-row action cannot be
injected safely because the Stronghold renderer exposes neither a usable
Python hover callback nor a documented row-button contract. The selected
fallback uses the existing legacy Scaleform `VIEW_ALIAS.SIMPLE_DIALOG` view
with a fixed Shotcaller view name and `VIEW_SCOPE`; it needs no custom SWF.
`Ctrl+Alt+V` opens the current cached-roster target, while
`Ctrl+Alt+Left/Right` cycles targets.

The panel reads only the in-memory sidecar cache and never requests WG data on
open. It labels results as public Tier VI/VIII/X vehicle history rather than
current ownership, shows lookup pending/error/empty states, and groups names by
class after sorting by class then name. Its native close button and the fixed
view destruction path close it for detachment exit, target removal, battle
start, and mod unload. The initial build expected native dialog scrolling, but
Prototype 5A-repair validation later proved the stock text body does not scroll.
Known limitation: no per-row icon/button is present in this first panel.

### Prototype 5A validation and navigation repair

Prototype 5A rendered correctly, reused the seven-player cache without new
sidecar/WG requests, grouped vehicle classes correctly, and preserved exit
cleanup. Global `Ctrl+Alt+Left/Right` did not fire while the modal
`simpleDialog` held keyboard focus, so keyboard cycling is retired.

The repair switches the fixed-name panel to the native legacy Scaleform
`buttonDialog`. Unlike `simpleDialog`, its Python callback preserves the button
ID, allowing explicit Previous, Next, and Close controls. Previous/Next walk
only populated roster entries and wrap in both directions. Because the native
view destroys itself after every button click, navigation schedules exactly one
controlled rebuild after destruction while retaining the selected DBID; no
lookup is queued.

The heading adds `Player <current> of <total>`. Display-name normalization
removes all existing instances of the same `[CLAN]` token and then appends one,
so the tag appears exactly once. A display fingerprint covers the selected
DBID/slot, tier, roster position, normalized name, lookup state, and sorted
vehicle identity/type/name data. Ready, frozen, battle-status (except entering
battle), and commander-only changes therefore do not rebuild the panel, and a
status-only suppression is logged at most once per panel session.

### Prototype 5A-repair validation, 5B failure, and 0.0.35 recovery

Live validation displayed the authenticated player's 55 cached Tier VIII
vehicles and completed the first uncached lookup in approximately 3.00 seconds.
Reopening reused the cache and lifecycle cleanup passed. The 55-entry screenshot
also proved that the stock `buttonDialog` grows beyond the client viewport and
does not expose a usable scrollbar.

Prototype 5B / 0.0.34 is unsafe. Opening its custom
`shotcallerVehiclePanel.swf` terminated the WoT process directly after the
native `Loading window: alias=shotcallerVehiclePanel` line and Shotcaller's
waiting-tier/opened lines. There was no Python traceback, normal shutdown, or
mod-unload log. Python had returned from `loadView`, so the evidence indicates
a native Scaleform/renderer fatal failure during SWF construction or population,
not an ordinary mod-Python exception.

Prototype 0.0.35 restores the validated native `buttonDialog` view. Its runtime
does not register, instantiate, load, or reference the 0.0.34 custom alias or
SWF, and its archive contains only `meta.xml` and `mod_shotcaller.pyc`.
`Ctrl+Alt+V`, Previous/Next, cache-only navigation, stale-response protection,
and all roster/lifecycle behavior remain on the proven generic path. The known
55-vehicle overflow remains an accepted temporary limitation.

Static analysis ranks the leading custom-SWF risks as: (1) a duplicate
default-package `ButtonDialogUI` export already supplied by the stock
`buttonDialog.swf`; (2) dynamic child/control creation in the derived dialog
constructor before stock timeline population; (3) overridden layout/text hooks
that can recurse through the inherited dialog/window layout contract; and (4)
an unverified dynamically-created `ScrollBar`/`scrollTarget` relationship.
Runtime `GroupedViewSettings`/Python-view/SWF linkage mismatch and reimported
AS3 bytecode compatibility remain medium and low/unknown alternatives. Masks
and vehicle-list length are not leading candidates because no mask was added and
the process died before significant dynamic data was used.

Installed known-working mod assets contrast with the failed design: Aslain uses
the uniquely named `aslainMenu.swf`, Izeberg uses `modsSettingsWindow.swf`, and
XVM uses context-specific `xvm_lobby*.swf` and `xvm_battle*.swf`. The failed
artifact instead copied the stock dialog export/name and modified its lifecycle
inside a newly registered alias. That structural difference is a useful risk
signal, not proof from archive inspection; compilation, reimport,
decompilation, and ZIP checks had all passed before the live crash.

The minimum future custom-SWF experiment is deliberately separate from 0.0.35
and opt-in only: one plain root `MovieClip`, one static timeline text field, a
unique class/package and alias, and no `ButtonDialogUI` inheritance, Python
callbacks, buttons, masks, scrolling, resizing, or dynamic data. Add features
only after that loads and closes safely.

### Prototype 0.0.36 safe vehicle-selection refresh

The 0.0.35 fallback did not crash, but it demonstrated that the converter hook
is observational rather than a complete lifecycle source. The first roster VO
had no selected vehicle (`intCD=None`, level `0`), and no later `makeSlotsVOs`
call occurred after T-832 became visible in the native Stronghold room. Thus
Shotcaller had no valid tier and deliberately did not queue a lookup.

The actual legacy rally path listens to `g_currentVehicle.onChanged` and calls
`_updateMembersData`, which normally invokes `makeSlotsVOs`. The Stronghold
room has the narrower `onUnitVehiclesChanged(dbID, vInfos)` callback; its
native handler receives `vehTypeCD` and `vehLevel` and updates that slot. The
repair hooks only this direct `StrongholdBattleRoom.__dict__` method, after the
original return, and applies the compact descriptor/level only to the matching
cached DBID. It preserves normal converter hooks and does not patch a shared
lobby base class.

The generic `buttonDialog` is still the only UI. Unknown tier displays `Select
a Tier VI, VIII, or X vehicle.` with no lookup and no `Tier None` title. A
valid tier queues the normal lookup and refreshes an open panel; same-tier
selection reuses cache while a tier change invalidates tier-scoped results.
Previous/Next are no-ops for a one-member roster, avoiding the stock dialog's
otherwise unavoidable close/rebuild cycle. Non-draggable stock dialog behavior
is an accepted temporary limitation.

### 3. Detachment detection

Goal:

- prove we can tell when the Stronghold / detachment room is open

Success criteria:

- log line on enter/exit of the room
- no button required yet

### 4. Shotcaller config button

Goal:

- place a small `Shotcaller` button in the detachment UI

Success criteria:

- button appears only in the right room
- click action logs or opens a trivial placeholder panel

### 5. Hover popup

Goal:

- detect member-row hover and show a static popup

Success criteria:

- moving over a player row shows fixed test content
- leaving the row hides it

### 6. Backend integration

Goal:

- replace static hover content with cached player lookup data

Success criteria:

- known tanks display for the selected detachment tier
- hidden tanks are filtered out
- failures degrade gracefully without freezing the UI

## Minimal mod-loading plan

### Recommended architecture

#### Option A: Preferred

- WoT mod = very small Python 2.7 shim
- local helper = current modern Python backend
- communication = localhost HTTP or a small JSON file protocol

Pros:

- reuses existing backend
- smallest WoT-specific rewrite
- easiest to iterate safely

Cons:

- requires an external helper process
- needs helper startup/discovery handling

#### Option B: Not recommended initially

- port backend logic into WoT Python 2.7

Cons:

- large rewrite
- higher client instability risk
- duplicates modern backend work

### Recommended first shipping shape after research

1. `mod_shotcaller.pyc` entrypoint in WoT
2. WoT-side config path abstraction under `res_mods/configs/shotcaller/`
3. local helper adapter that exposes:
   - `GET /health`
   - `POST /lookup-batch`
   - `GET /config-catalog?tier=6|8|10`
   - `GET/POST /excluded-tanks`

## Practical TODOs

### Confirm in-game

- whether stock client requires `.pyc` for our target workflow
- exact `python.log` messages for a successful mod load
- exact garage lifecycle hook to use
- exact detachment-room open/close hook
- exact member row hover hook
- exact source of selected detachment tier

### Confirm in decompiled source

- the view/controller for the Stronghold detachment room
- the member model object carrying visible names
- the roster or filter object that exposes allowed vehicle tier
- whether the room is driven mainly by legacy Scaleform or modern Gameface

### Prepare in this repo later

- extract path handling so cache/settings are not hardcoded to repo root
- isolate backend logic that can live in a sidecar API process
- define a narrow JSON payload for popup results

## Recommended next step after this document

Build only Prototype 1:

- a tiny WoT mod that loads
- writes `Shotcaller loaded` to `python.log`
- does nothing else

That prototype settles the most basic unknowns before any Stronghold UI work starts.

## Prototype 1 created

Prototype 1 now exists in:

- `wot_mod/prototype_1_minimal_load/`

Contents:

- `README.md`
- `mod_shotcaller.py`

Current prototype scope:

- isolated WoT-side entrypoint only
- Python 2.7-compatible
- no backend imports
- no UI
- no networking
- no config window
- no lookup logic

Current in-game verification target:

- confirm whether `mod_shotcaller.py` loads directly from `res_mods/<client_version>/scripts/client/gui/mods/`
- if not, retry with compiled `.pyc`
- confirm `python.log` contains `[shotcaller] loaded`

### Prototype 1 update after first in-game test

First in-game result:

- loose `mod_shotcaller.py` did not load from `res_mods`
- WoT log behavior was consistent with executed mod scripts being `.pyc` payloads loaded from `.wotmod` packages
- there was no `mod_shotcaller` entry and no `[shotcaller] loaded` line

Updated next step:

- compile `mod_shotcaller.py` with Python 2.7 into `mod_shotcaller.pyc`
- test loose `.pyc` at:
  - `C:\Games\World_of_Tanks_NA\res_mods\2.3.0.1\scripts\client\gui\mods\mod_shotcaller.pyc`
- if loose `.pyc` still does not execute, package next test as:
  - `shotcaller_0.0.1.wotmod`
  - containing `res/scripts/client/gui/mods/mod_shotcaller.pyc`

## Sources

## Prototype 0.0.37 custom-window foundation

The 0.0.34 crash ruled out reuse of the stock ButtonDialog implementation. Its
last Python line was the view load request, with no Python traceback or normal
shutdown; that remains evidence of a native/Scaleform failure rather than an
ordinary mod exception. Prototype 0.0.37 therefore uses a unique root class,
alias, and nested resource path: `shotcaller.ui.ShotcallerVehicleWindow`,
`shotcallerVehicleWindow`, and
`res/gui/flash/shotcaller/shotcallerVehicleWindow.swf` respectively.

The registration pattern was checked against the working Aslain and Izeberg
mods. Both register a `ViewSettings` with a dedicated `View` subclass, a unique
SWF file name, `WindowLayer.OVERLAY`, and `ScopeTemplates.GLOBAL_SCOPE`.
Shotcaller copies only that narrow registration convention. It does not use a
`GroupedViewSettings`, `ButtonDialog`, `ButtonDialogUI`, stock dialog alias,
or stock root export for its custom path.

The Python view performs no data push until `_populate`, treats a missing Flash
method as a population failure, disposes the custom view before one controlled
generic fallback, and confirms that a requested view reaches population within
one second. `USE_CUSTOM_VEHICLE_WINDOW` is the sole switch: false preserves the
validated 0.0.36 built-in buttonDialog fallback. The initial SWF is deliberately
plain and bounded: static root hierarchy, draggable title bar, close/navigation
controls outside a masked vehicle viewport, and wheel/scrollbar handling inside
that viewport. No claim of runtime safety is made until the native client test
passes.

External references used for this research:

- Wargaming Modding Hub index: https://wgmods.dev/docs
- Wargaming Modding Hub, Environment Setup: https://wgmods.dev/docs/wot/getting-started/setup
- Wargaming Modding Hub, Game File Structure: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/game-file-structure.mdx
- Wargaming Modding Hub, Client Architecture: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/client-architecture.mdx
- Wargaming Modding Hub, Python, Flash, and Gameface: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/python-flash-gameface.mdx
- Wargaming Modding Hub, Hooking into the Game: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/hooking-into-the-game.mdx
- Wargaming Modding Hub, Configuration Files: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/configuration-files.mdx
- Wargaming Modding Hub, Packaging your Mod: https://github.com/wgmods-dev/wgmods.dev/blob/main/content/docs/wot/getting-started/packaging.mdx
- WoTStat docs, Python Environment: https://docs.wotstat.info/en/guide/first-steps/environment/python/
- WoTStat docs, Asynchronous Programming with adisp: https://github.com/wotstat/mods-development-docs/blob/main/docs/en/articles/adisp/index.md
- World of Tanks Stronghold guide, detachment references: https://worldoftanks.com/en/content/strongholds_guide/advances/
- World of Tanks Stronghold guide, member-list interaction references: https://worldoftanks.com/en/content/strongholds_guide/reserves/
- Decompiled client reference examples surfaced during research:
  - https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/tree/1.42/source/res/scripts/client/gui/impl/lobby/stronghold
  - https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/blob/1.42/source/res/scripts/client/gui/prb_control/entities/stronghold/unit/entity.py
  - https://github.com/StranikS-Scan/WorldOfTanks-Decompiled/blob/1.42/source/res/scripts/client/gui/clientgw/strongholds/contexts.py

Local project references:

- `shot_caller/wg_api.py`
- `shot_caller/lookup.py`
- `shot_caller/config.py`
- `shot_caller/exclusions.py`
- `shot_caller/tankopedia.py`

## Prototype 0.0.38 IView contract repair

The live 0.0.37 rejection, `[Scaleform] net.wg.infrastructure.interfaces.IView
does not implemented`, occurred after the custom resource was loaded and before
the Python fallback. This identifies the missing ActionScript DAAPI contract,
not registration, alias, resource path, or Python population behavior.

The exact 2.3.1.0 client definition in `lobby.swf` is `AbstractView extends
AbstractViewMeta implements IView`. Extracted Aslain and Izeberg overlay roots
follow the same pattern by extending `net.wg.infrastructure.base.AbstractView`
and overriding `onPopulate` / `onDispose`. Prototype 0.0.38 changes only the
Shotcaller root to that base and lifecycle; it retains its unique alias, root,
and standalone layout, and does not inherit any stock dialog class.

The Flex SDK does not ship Wargaming framework SWCs. A compile-only external
contract records the superclass name and verified lifecycle signatures so the
generated SWF links to the client class at runtime. It does not define `IView`,
is not packaged, and cannot replace the real client framework. Static inspection
must therefore show the root superclass as
`net.wg.infrastructure.base.AbstractView`; the shipped archive remains only
metadata, Python bytecode, and the custom SWF.

## Prototype 0.0.39 persistent vehicle filters

The first custom overlay is now runtime-validated: it is non-modal, draggable,
scrollable, reloads safely, and closes safely on detachment exit. Prototype
0.0.39 applies global presentation-only filters after the full cached sidecar
result, preserving complete lookup data and avoiding any request when filters
change. Stable numeric vehicle IDs are persisted by tier in the external,
versioned `mods/configs/shotcaller/vehicle_filters.json` file.

The settings surface is a separate unique Scaleform `AbstractView` overlay.
Configuration failure is isolated from the history-view fallback. Missing or
malformed configuration uses the empty built-in defaults, and JSON writes use a
temporary file with replacement where practical. Both runtime SWFs are compiled
against the audited AbstractView contract and are the only non-Python resources
in the package.

## Prototype 0.0.42 complete filter catalog and controls

The 0.0.41 callback bridge is validated for Close, Settings, Cancel, and view
lifecycle. 0.0.42 repairs the independent catalog contract: the settings
payload is sourced from the local client vehicle-definition list rather than a
player history, garage, roster, or API result. All VI/VIII/X catalogs are sent
once, allowing Flash to switch tiers, search names, toggle classes, scroll, and
change checkbox working state without callback traffic. Save returns the three
complete hidden-ID sets to Python; configuration remains presentation-only and
does not request sidecar data.

## Prototype 0.0.43 vehicle catalog iteration repair

Live 0.0.42 confirmed the Flash payload path but exposed the client API error:
`g_list.getList()` requires a nation argument. The 2.3.1.0 customization
service provides the verified iteration contract:
`nations.INDICES.itervalues()` then
`vehicles.g_list.getList(nationID).itervalues()`. The catalog builder now uses
this contract, descriptor compact descriptors, localized descriptor names, and
supported descriptor vehicle types. It reports guarded call diagnostics and
does not label a failed extraction as a complete catalog.

## Prototype 0.0.44 vehicle catalog cache scope repair

The repaired nation loop reached client `VehicleItem` values, then failed only
because the builder assigned `VEHICLE_CATALOG` without declaring it global.
The cache is now atomic: `None` until a fully validated local catalog exists,
then one module-level assignment. A failed build retains `None` and a later
Settings action retries, while a successful second open reuses the completed
catalog. No Scaleform or roster/sidecar behavior changes in this repair.

## Prototype 0.0.45 vehicle class resolution repair

The 2.3.1 live wrapper data showed that `VehicleItem.type` and `typeName` are
both `None`. Class resolution therefore moves to the proven full-definition
path: `vehicles.getVehicleType(item.compactDescr)` followed by
`vehicles.getVehicleClassFromVehicleType(...)`. Only the five normal vehicle
class tags are emitted; all other entries and individual resolution failures
are counted and safely skipped.

## Prototype 0.0.46 filter payload contract repair

The complete live client catalog exposed a separate schema mismatch at the
Scaleform boundary. The wire format is now versioned, compact JSON with
camel-case schema keys and a record `class` field. The ActionScript receiver
logs bounded raw type, length, parse, schema, tier-array, and accepted/skipped
record diagnostics through its dedicated DAAPI callback, so any remaining
bridge truncation or coercion issue is observable without logging full payloads.

## Prototype 0.0.47 Scaleform JSON decoder repair

Live diagnostics proved the JSON bridge preserves the full payload but the
Scaleform runtime lacks the global `JSON` implementation. The settings data
path now uses native DAAPI arrays: begin metadata, three tier catalogs, three
hidden-ID arrays, and finish. The view validates and normalizes those primitive
arrays, retaining all catalog and filter behavior while removing the unavailable
JSON parser dependency.

## Prototype 0.0.48 filter state and duplicate grouping repair

Display rows are now grouped by tier/localized name/class, not by compact
descriptor alone. Each group retains all its stable IDs and the SWF stores
hidden state in per-tier ID maps independent of search, scrolling, class
browsing, and current tab. Save uses three explicit sorted numeric arrays;
Python persists them and refreshes only the existing cached history panel.
# Prototype 0.0.52 — intentional regular-platoon support

The shared legacy rally converter is no longer treated as sufficient context evidence. The mod checks the current prebattle type and accepts only `PREBATTLE_TYPE.SQUAD` for a regular random platoon; Stronghold remains identified by `StrongholdVehiclesWatcher`. Platoon lifecycle is narrowly observed on `gui.prb_control.entities.random.squad.entity.RandomSquadEntity` (`init`, `fini`, and unit vehicle callbacks), without broadening the Stronghold watcher patch or touching `BaseVehiclesWatcher` for platoon handling.

For platoons, a lookup tier is resolved only when all occupied selected vehicles report one matching supported tier (6, 8, or 10). Mixed/unknown/unsupported selections do not request the sidecar. The history HTML separator after `Vehicles shown` is retained as the fixed-header/body split, while the SWF viewport now starts at y=154 after a y=138 header, a 16 px gap; the first body line is `Heavy` with no blank leading line.
# Prototype 0.0.53 — authoritative platoon roster source

The regular platoon’s audited source is the random squad entity’s unit snapshot: `getUnit(safe=True)` plus `getSlotsIterator(unitMgrID, unit)`. Slot entries provide the player wrapper and selected vehicle entry used for normalized DBID rows. Rebuilds are scheduled after `init`, roster, player, ready, and vehicle events; retries are bounded to 0, 250, 750, and 1500 ms and are invalidated on `fini`. The existing `makeSlotsVOs` result remains accepted only while the explicit random-platoon context is active, preserving the successful 0.0.51 fallback path.
# Prototype 0.0.54 — field-aware platoon merging

The entity slot snapshot is intentionally treated as sparse: `None`, zero, and empty values from that source are “missing”, not a deselection. Only an explicit converter slot update may clear a selected vehicle. For a matching DBID, entity membership/slot/commander fields are merged with existing converter vehicle, tier, ready, status, name, clan, and rating fields. This prevents a delayed entity rebuild from changing Tier VIII to unknown and incorrectly invalidating an in-flight lookup.
# Prototype 0.0.55 — text/rendering and invalid-tier UX

The first heading clipping was a TextField/scrollRect glyph-edge issue: headings were formatted HTML in the same scrolling TextField as vehicle names. The history body now renders heading fields separately, with `text` (not `htmlText`), `TextFieldAutoSize.NONE`, no wrapping, `_sans`, `embedFonts=false`, an x=24 local inset, and a clipped viewport starting at x=0. `as_setMessageState(contextLabel, titleLine, detailLine)` provides the unsupported/mixed-tier state without another SWF or sidecar request.
# Prototype 0.0.56 — no heading sentinels

The 0.0.55 leak was caused by the former multiline heading delimiter flowing into the vehicle list when its ActionScript recognition path did not match. The history bridge now sends native DAAPI calls for typed heading and vehicle rows; no heading inference or marker parsing remains. A separate `resolved_tier` preserves a real Tier V selection while `tier` remains the supported lookup tier (`None`), allowing a correct unsupported-tier message without a request.
# Prototype 0.0.57 — state classifier

`_classify_history_state(roster)` distinguishes a real selected but unsupported tier from incomplete and mixed selection. `_apply` computes both `resolved_tier` and the supported lookup tier from merged rows, after source-precedence reconciliation, preventing sparse entity data from collapsing Tier V to unknown. Informational state uses the existing SWF and clears row/scroll state; no sidecar request is permitted without a supported lookup tier.
