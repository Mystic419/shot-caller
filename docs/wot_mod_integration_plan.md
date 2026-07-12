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
