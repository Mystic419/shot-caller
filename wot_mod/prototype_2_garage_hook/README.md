# Prototype 0.0.35: safe Scaleform crash isolation

## Safe baseline

Prototype 0.0.34 is unsafe and must not be used. Pressing `Ctrl+Alt+V` caused
an immediate World of Tanks process termination immediately after the custom
Scaleform view began loading. Prototype 0.0.35 restores the validated 0.0.33
native `buttonDialog` panel. It contains no custom SWF, custom view setting, or
custom Scaleform alias.

At startup it logs:

```text
[shotcaller] safe generic panel active
[shotcaller] custom SWF disabled: reason=0.0.34 hard client crash
```

`Ctrl+Alt+V` opens or closes the generic cached-history panel. Previous and
Next remain native dialog buttons; navigation uses cached WoT-memory lookup
results and never causes a new WG/sidecar request. The stable roster capture,
Tier VI/VIII/X detection, stale-generation rejection, player/clan normalization,
status-only refresh suppression, watcher lifecycle cleanup, and close-on-battle
behavior are unchanged.

The stock dialog still has its known limitation: a very long list can extend
beyond the usable client area because it has no usable body scrollbar. That is
accepted for this recovery build; no scrolling or loading-UX experiment is
present in its runtime path.

## Archive boundary

The package is deliberately limited to:

```text
meta.xml
res/scripts/client/gui/mods/mod_shotcaller.pyc
```

`flash_work/shotcallerVehiclePanel.swf` and its ActionScript remain disabled
development artifacts for forensic work only. The build script neither checks
for nor writes that SWF, and the Python runtime has no reference to it.

## Crash isolation report

The last useful client log lines were the native load request for
`alias=shotcallerVehiclePanel`, followed by Shotcaller logging the waiting-tier
panel state and the panel-opened message. There was no Python traceback, normal
shutdown sequence, or Shotcaller unload message. Python had returned from the
view-load request before the process died. That pattern points to a native
Scaleform/renderer fatal failure during SWF construction or population, rather
than an exception in mod Python.

Static compilation, reimport, decompilation, and ZIP inspection are therefore
not evidence that the SWF is runtime-safe; all had passed in 0.0.34.

Likely causes, ranked:

1. **High:** the custom SWF exports the default-package `ButtonDialogUI` class
   already exported by WoT's built-in `buttonDialog.swf`. Loading a second view
   with that linkage/name can conflict with the stock class/symbol resolution.
2. **High:** its constructor creates and configures dynamic text and scrolling
   children before the inherited dialog has completed timeline construction and
   population. Native Scaleform bindings may not tolerate those inherited
   timeline-child interactions at that point.
3. **High:** it overrides stock dialog layout/text hooks and combines
   `invalidateLayout`, `super.applyLayout`, changing child geometry, and a
   viewport-height calculation. This changes the established dialog/window
   layout contract and can cause a native recursive layout/resize failure.
4. **Medium:** dynamic lookup and construction of `ScrollBar`, then duck-typed
   assignment of its `scrollTarget`, is not a verified contract for a separately
   loaded WoT SWF. Changing that target during text updates adds another unsafe
   native-component interaction.
5. **Medium:** the runtime `GroupedViewSettings` registration paired the custom
   root with the Python `ButtonDialog` view and a new alias. Python accepted the
   request, but that does not establish that the root symbol, DAAPI linkage, and
   lifecycle contract match the client expectation.
6. **Low/unknown:** JPEXS reimport may have produced a bytecode or linkage detail
   that WoT's embedded Scaleform runtime rejects despite ordinary tools accepting
   it. No masks were added, and the crash occurred before meaningful list data,
   so malformed masks and vehicle-list size are not current leading causes.

For comparison, installed working mods use uniquely named SWF assets, for
example Aslain `aslainMenu.swf`, Izeberg `modsSettingsWindow.swf`, and XVM's
context-specific `xvm_lobby*.swf` / `xvm_battle*.swf`. The 0.0.34 SWF instead
reused the game's `ButtonDialogUI` export and attempted to behave as a modified
copy of the shared stock dialog. Its inheritance, duplicate export name,
runtime alias registration, and dynamic control construction are the material
structural differences. This comparison is informative, not a claim that an
archive-level inspection can prove safe runtime behavior.

## Minimum next custom-SWF experiment

Do not repair the full panel next. Make a separate, opt-in diagnostic build
only after 0.0.35 is live-stable. It must contain exactly one plain root
`MovieClip` and one static timeline text field. It must have no `ButtonDialogUI`
inheritance, Python callbacks, buttons, masks, scrolling, resize handling, or
dynamic vehicle data. Give it a unique package/class and a unique alias. Only
after that view loads and closes safely should the integration contract be
expanded one feature at a time.

## Existing validated functionality

Prototype 3M created a seven-member normalized Tier 8 roster cache. Prototype
3N proved ready-state handling is correct: `player_ready` remains distinct from
`vehicle_ready`; `player_status=0/2/3` means not-ready/ready/in-battle; and
`in_battle = bool(is_frozen or player_status == 3)`. Prototype 3O-repair
validated watcher-based exit clearing. Prototype 4A-repair validated localhost
health, public vehicle-history lookup, cache reuse, and exit clearing. Prototype
5A-repair validated the native generic vehicle-history panel, its navigation,
single clan-tag display, and no new lookup on opening or navigation.

## Prototype 0.0.36 vehicle-selection refresh

The safe 0.0.35 live test proved that the crash rollback was safe, but exposed
a separate cache-refresh gap. The initial `makeSlotsVOs` conversion occurred
before the local T-832 selection and contained an empty selected vehicle. The
native Stronghold room then visibly updated to T-832 without another converter
call, so Shotcaller correctly retained the only VO it had seen: no vehicle,
tier `None`, and no lookup.

The client rally source shows the normal path: `BaseRallyRoomView` listens to
`CurrentVehicle.g_currentVehicle.onChanged` and refreshes its members. More
specifically for Stronghold, `StrongholdBattleRoom.onUnitVehiclesChanged(dbID,
vInfos)` is the callback that receives the selected compact descriptor and
level and updates the native slot. Prototype 0.0.36 wraps only that direct
Stronghold method, calls the original first, preserves its return value and
exceptions, and updates only the matching cached DBID afterward. It logs the
old/new compact descriptor and tier, then uses the existing tier-gated sidecar
queue and panel refresh.

Unknown tier is now a normal waiting state: the generic panel says `Select a
Tier VI, VIII, or X vehicle.` and never queues a lookup. It never renders
`Public vehicle history for Tier None`. Once a valid tier arrives, the open
panel transitions through the existing pending/loading and ready/error states
without being manually reopened. A same-tier vehicle change reuses cached
results; a VI/VIII/X tier change clears the tier-scoped result cache and queues
the normal lookup.

For a one-member roster, Previous and Next remain visible because stock
`buttonDialog` has no safe per-button disabled contract in this use, but are
true no-ops: they do not destroy or rebuild the dialog. The stock fallback is
also intentionally non-draggable; no change is made to `buttonDialog.swf`.

## Build and validation

Compile `mod_shotcaller.py` with WoT-compatible Python 2.7, then run:

```bat
python build_pyc_wotmod.py
```

Output:

```text
dist\shotcaller_0.0.38_iview_contract_repair.wotmod
```

Before live testing, confirm the archive has `meta.xml`, the compiled Python
entry, and only `res/gui/flash/shotcaller/shotcallerVehicleWindow.swf`; the old
`shotcallerVehiclePanel.swf` must be absent.

## Prototype 0.0.37 safe custom window foundation

Prototype 0.0.37 retains all validated 0.0.36 roster, selection-refresh,
sidecar, tier-cache, stale-response, navigation, and cleanup behavior. It
adds an opt-in Scaleform foundation under `USE_CUSTOM_VEHICLE_WINDOW = True`.
The unique alias is `shotcallerVehicleWindow`; the dedicated Python `View`
subclass is registered as `shotcaller/shotcallerVehicleWindow.swf` on
`WindowLayer.OVERLAY` with `ScopeTemplates.GLOBAL_SCOPE`.

The arrangement follows the conceptual registration shape found in the working
Aslain and Izeberg settings mods: each uses a unique alias, a direct `View`
subclass, a unique SWF name, `WindowLayer.OVERLAY`, and global scope. It does
not copy either view implementation. The custom root is
`shotcaller.ui.ShotcallerVehicleWindow`; it has no
`ButtonDialog` or `ButtonDialogUI` inheritance or symbol reuse.

The generic 0.0.36 `buttonDialog` is a fail-closed fallback. If registration,
the synchronous load request, population, or first data push fails, Shotcaller
destroys the custom view before scheduling one generic fallback. A one-second
population confirmation also detects a load that never reaches `_populate`.
Only one named Shotcaller panel is allowed at a time. Set
`USE_CUSTOM_VEHICLE_WINDOW = False` before compiling to force the known generic
fallback without loading or registering the custom view.

This is still a first-runtime experiment. Its SWF has a fixed plain layout,
title-bar drag, close/previous/next visual controls, and a clipped fixed-size
vehicle body with mouse-wheel and scrollbar mechanics. It intentionally has no
animation, hover behavior, skinning, or automatic reopen. The Python view logs
construction, population, first data push, close, disposal, and fallback
activation. Runtime validation is required before calling the custom view safe.

## Prototype 0.0.38 IView contract repair

Prototype 0.0.37 reached the custom loader but the client rejected its plain
`MovieClip` root with `[Scaleform] net.wg.infrastructure.interfaces.IView does
not implemented`. The generic fallback then behaved as designed. The 2.3.1.0
`lobby.swf` and both working settings overlays were inspected: the Aslain and
Izeberg window roots extend `net.wg.infrastructure.base.AbstractView`, and the
client definition declares `AbstractView extends AbstractViewMeta implements
IView`.

The unique Shotcaller root now extends `AbstractView`, calls its native
`onPopulate` and `onDispose` lifecycle methods, and retains its independent
layout after that framework contract is established. A small external-only
compile contract supplies the verified superclass name and the two protected
lifecycle signatures to Flex; it is not included in the SWF or the `.wotmod`.
At runtime, the root resolves the real client `AbstractView` and therefore the
real `IView` implementation. Prototype 0.0.39 adds the separate filters SWF;
its package contains four ZIP_STORED runtime entries.

## Prototype 0.0.39 persistent vehicle filters

Prototype 0.0.39 keeps the validated custom history overlay and adds a second,
unique non-modal `AbstractView` overlay for global vehicle filters. Filtering is
presentation-only: cached sidecar results remain complete and the history view
reports `Vehicles shown: X of Y`. Checked stable vehicle IDs are hidden; display
names are never used as filter keys.

The persistent file is `mods/configs/shotcaller/vehicle_filters.json`, outside
the `.wotmod`. Its schema version is 1, its initial built-in defaults show all
Tier VI/VIII/X vehicles, and malformed or missing files safely restore those
defaults. Save uses a temporary file followed by replacement where supported.
The configuration window is closed with the history view during detachment exit
and never invokes the generic-dialog fallback.

## Prototype 0.0.40 settings callback repair

The initial settings button was visually present but used an unbound Flash
function property, so its click never reached Python. Prototype 0.0.40 gives
the button its own post-initialization click listener and routes Settings,
Close, Previous, and Next through the same `AbstractView` DAAPI
`App.utils.callInNoArgs` convention. The Python target uses the corresponding
`onSettingsS` method and logs callback receipt, the filter load request, view
construction, population, and the initial data push. The count/list body also
uses an additional internal left inset so `Vehicles shown: X of Y` is not cut
off by the viewport.

## Prototype 0.0.42 complete filter catalog and controls

Prototype 0.0.42 replaces the empty player-derived filter probe with one cached
local Tankopedia catalog built from `items.vehicles.g_list.getList()`. It reads
all normal client definitions at tiers VI, VIII, and X, retaining compact
descriptor, localized display name, tier, and class. It does not use a garage,
roster, sidecar response, or account-history data to form the catalog.

The Python-to-Flash payload is a JSON string sent to `as_setData` with
`selected_tier`, `catalogs` keyed by `"6"`, `"8"`, and `"10"`, and the three
working hidden-ID arrays. Flash owns local tier browsing, search, class
browsing filters, scrolling, row checkbox state, and Hide All/Show All for
only the rows currently visible under those browsing filters. Save alone sends
all three hidden-ID arrays to Python for validation and persistence; Cancel
and Close discard working changes. The filters title bar now uses the same
bounded title-only drag pattern as history.

The fixed history header now keeps `Vehicles shown: X of Y` outside the clipped
vehicle viewport, with a 16px left inset. The development diagnostic reads
`Loaded N Tier VIII vehicles; showing M.` so a malformed or empty catalog is
visible rather than silently rendering a blank list.

## Prototype 0.0.43 vehicle catalog iteration repair

The first 0.0.42 runtime test proved the catalog SWF and data receiver were
working, but also proved that calling `items.vehicles.g_list.getList()` with no
argument is invalid in the 2.3.1.0 client. The client’s own customization
service uses `nations.INDICES.itervalues()` followed by
`vehicles.g_list.getList(nationID).itervalues()`. Prototype 0.0.43 uses that
same nation-scoped descriptor iteration and the descriptor `compactDescr`.

The guarded audit logs the callable shape, attempted argument, returned
container type, a bounded first-item sample, failure type/message, and a
bounded traceback. Successful builds log tier and class counts plus skip
reasons. A failed catalog is explicitly marked unavailable and Settings shows a
clear diagnostic state; it is never reported as a successful empty catalog.

## Prototype 0.0.44 vehicle catalog cache scope repair

0.0.43 validated the nation-scoped `VehicleItem` iteration but exposed a
Python local/global shadowing error while the completed cache was being
assigned. Prototype 0.0.44 initializes `VEHICLE_CATALOG` to `None`, declares
it global in the builder, constructs a local complete catalog first, and only
then atomically assigns it to the module cache. Failure keeps the cache `None`,
so a later Settings open retries cleanly; success logs `vehicle catalog cache
reused` on subsequent opens.

`test_vehicle_catalog_cache_scope.py` is a Python 2.7 mock test covering first
build, cache reuse, failed-build non-caching, and retry. The package builder
also rejects source that assigns the catalog inside the builder without the
required global declaration.

## Prototype 0.0.45 vehicle class resolution repair

Live `VehicleItem` wrappers correctly supply compact descriptor, level, and
localized `userString`, but deliberately expose neither `type` nor `typeName`.
0.0.45 resolves every wrapper through the client API
`items.vehicles.getVehicleType(compactDescr)`, then calls
`getVehicleClassFromVehicleType(vehicleType)`. This is the same descriptor and
class helper sequence used by the client vehicle web API.

The builder logs only one bounded descriptor/tag sample for each supported
class. Per-entry descriptor failures, unknown classes, invalid IDs, and
duplicates are counted and skipped without aborting the nation loop. The
Python 2.7 mock test now covers all five classes and every skip path.

## Prototype 0.0.46 filter payload contract repair

The live catalog is now complete (116 Tier VI, 333 Tier VIII, and 191 Tier X
entries), leaving only the Python-to-Scaleform contract. 0.0.46 sends a compact
ASCII-safe JSON string with `schemaVersion`, `selectedTier`, `catalogs`, and
`hiddenVehicleIds`; every record uses `id`, `name`, `tier`, and `class`.

The filters view accepts either a bridged string or object, reports bounded
raw-type/length/schema diagnostics to Python, validates each tier separately,
and skips individual invalid records instead of rejecting the complete
catalog. The UI reports the precise parsing stage if validation fails.

## Prototype 0.0.47 Scaleform JSON decoder repair

WoT 2.3.1.0 delivered the complete 40,632-character JSON string intact but
does not provide the global AS3 `JSON` object. Rather than add an unverified
decoder, 0.0.47 uses a native DAAPI primitive-array contract: one begin call,
one vehicle-array call and one hidden-ID call per tier, then one finish call.
The filters SWF creates normalized row objects locally after validating IDs,
names, and supported class strings. This eliminates JSON decoding entirely
without issuing per-vehicle bridge calls.

## Prototype 0.0.48 filter state and duplicate grouping repair

The native bridge now transfers all records, so 0.0.48 makes the filters SWF
own the authoritative hidden-ID maps for all three tiers. Rows are grouped by
tier, case-normalized localized name, and class, while retaining every matching
compact descriptor. Checking a grouped row adds every represented ID; Save
sends three sorted numeric ID arrays directly to Python. Python validates,
persists, and reapplies the saved filters to the open cached history result
without a sidecar call.

## Prototype 0.0.49 filter row metadata repair

Scaleform seals `flash.display.Sprite`, so grouped-row metadata can no longer
be attached dynamically. 0.0.49 introduces the dedicated
`shotcaller.ui.VehicleFilterRow` class with declared tier, name, class, IDs,
and grouped-data fields. Rebuilds remove listeners before children are dropped;
clicks recover metadata from the typed row class and update the existing hidden
ID maps.

## Prototype 0.0.50 live history refresh and heading layout repair

Filter Save now pushes rebuilt history data directly into the already populated
custom history view through the same `as_setData` helper used for first
population. It does not reopen the view or invoke the sidecar. The history body
also starts 12px from the viewport’s left edge and 8px below its top edge; its
scroll clamp preserves the prior position when refreshed and keeps the first
bold vehicle-class heading inside the clipping rectangle.
# Prototype 0.0.53 — platoon roster population repair

- Fixes the 0.0.52 platoon regression: the converter could run before the prebattle-type getter became available, leaving the valid roster rejected.
- Random platoons now rebuild from `RandomSquadEntity.getUnit(safe=True)` and `getSlotsIterator(unitMgrID, unit)` after initialization and roster/vehicle events, with bounded 0/250/750/1500 ms retries.
- Converter-derived platoon rows remain a logged fallback. A delayed Stronghold clear cannot erase a newer Platoon context.
# Prototype 0.0.54 — platoon source precedence and merge repair

- Converter data is authoritative for selected vehicle, tier, ready/status, and display fields. Entity snapshots remain authoritative for occupied membership, commander identity, and slot order.
- Missing entity fields no longer erase rich converter values. Complete converter rosters stop pending initial entity retries; identical merged snapshots do not advance roster generation.
# Prototype 0.0.55 — heading glyph and unsupported-tier feedback

- Vehicle section headings now use dedicated plain-text `_sans` TextFields and 24 px backplates, rather than HTML inside the clipped list field. Their 24 px local inset is logged at runtime.
- Ctrl+Alt+V opens an informational history state for unsupported or mixed tiers; no sidecar request is made until Tier VI, VIII, or X is resolved.
# Prototype 0.0.56 — structured history rows

- Removed the leaked string heading protocol completely. Python now transfers each section with `as_beginHistoryRows`, `as_addHistoryHeading`, `as_addHistoryVehicle`, and `as_finishHistoryRows`.
- Informational state distinguishes resolved unsupported tiers from mixed/incomplete selections and keeps the permanent title out of the body.
# Prototype 0.0.57 — resolved unsupported tier and informational layout

- History state is now classified from merged normalized roster rows: empty, incomplete, mixed, resolved unsupported, loading, or ready.
- Informational mode hides Previous/Next and scrollbar/track, leaving Settings and Close at x=48 and x=220; normal history restores the four-control layout.

# Prototype 0.0.60 — native in-client lookup migration

- The sidecar is no longer required by this migration test package. Native
  asynchronous `BigWorld.fetchURL` performs official WG HTTPS requests only
  when a supported platoon or Stronghold roster needs history data.
- The normal UI, roster lifecycle, filters, battle counts, scrolling, dragging,
  and unsupported-tier presentation are unchanged.
- Player/tier records and shared Tankopedia metadata use six-hour,
  schema-versioned public-data cache files at `mods/configs/shotcaller/cache/`.
  Corrupt cache files are ignored and stale records are used after a temporary
  native transport failure.
- NA, EU, and ASIA endpoints are selected from the client realm. The test
  builder injects a public WG API application ID from the developer `.env` into
  temporary compiled source; users install only the resulting `.wotmod`.
- 0.0.60 is a native migration validation build, not yet the final release.

# Prototype 0.0.61 — native lookup identity repair

- Public vehicle-history requests no longer use the broad roster UI generation
  as their stale token. Ready/status and same-tier vehicle-state refreshes now
  accept a matching native result and refresh an open Pending panel.
- Room/unit changes, tier changes, realm changes, battle entry, and removed
  roster members remain material invalidations. They trigger one deduplicated,
  cache-aware replacement evaluation rather than leaving the panel Pending.

# Prototype 0.0.63 — WG API batch recovery

- A WG JSON `status=error` from a multi-account `tanks/stats` request now logs
  safe endpoint/code/message/field/account/realm diagnostics and performs one
  individual retry per unresolved player.
- Existing cached results and successful individual responses are preserved.
  Missing or still-failed accounts show “Vehicle history unavailable from the
  Wargaming API.” rather than a zero-vehicle history.

# Prototype 0.0.64 — WR / Battles and local clan watermark

- Rows now show public `WR / Battles`; a one-decimal win rate appears only for
  valid nonzero battle totals. Battles-only legacy cache records safely display
  an em dash until refreshed.
- The optional faint emblem watermark always belongs to the logged-in player's
  public clan, not the roster target. Its validated image and metadata are
  cached for 24 hours; no clan or refresh/image failure leaves normal windows.

# Prototype 0.0.62 — in-place player navigation

- Previous/Next no longer submits a duplicate `loadView` request for the
  already-open global history alias. It pushes the selected roster member
  directly into the active custom view.
- The structured history bridge replaces heading/state and invokes
  `as_beginHistoryRows`, which clears old rows and battle fields and resets the
  list scroll position without moving or recreating the draggable overlay.
