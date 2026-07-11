# Prototype 3D: Stronghold Entity Lifecycle/Data Hook

This is only a safe Stronghold entity lifecycle and data discovery hook for
Shot-caller. It does not implement hover popups, Wargaming API lookup, a local
helper, configuration, or real UI.

## Prototype 3C result

Prototype 3C confirmed the correct Stronghold class/module family, including:

```text
StrongholdEntity
StrongholdBrowserEntity
StrongholdDynamicRosterSettings
StrongholdUnitStats
StrongholdSettings
UnitFullData
PlayerUnitInfo
SlotInfo
VehicleInfo
```

The runtime PRB getter and dependency lookup did not expose a live entity, so
Prototype 3D hooks the two confirmed entity classes directly when WoT calls
them.

## Prototype 3D behavior

The mod inventories lifecycle/data-related entity methods and hooks up to six
existing methods per class from the approved candidate list. Every wrapper
calls the original method first, logs the hook fire, and deeply inspects the
live `self` object only for the first three fires of each class/method pair.

Inspection is bounded and read-only: selected unit/roster/member/player/slot/
vehicle/settings/state/commander/stats attributes are logged, and only safe
no-argument `get*`, `is*`, `has*`, or `can*` methods are called. State-changing
method names are never called by the probe.

Stronghold watcher, battle-room window, and Stronghold browser URL detection
remain enabled.

## Confirmed package structure

```text
meta.xml
res/scripts/client/gui/mods/mod_shotcaller.pyc
```

The package is a `ZIP_STORED` (no-compression) archive.

## Build

Compile `mod_shotcaller.py` with the WoT-compatible Python version and place
the output beside the source as:

```text
mod_shotcaller.pyc
```

Then run:

```bat
python build_pyc_wotmod.py
```

This produces:

```text
dist\shotcaller_0.0.11_stronghold_entity_hook.wotmod
```

## In-game test

Copy the package to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Launch WoT, enter the garage, and open a Stronghold/skirmish battle room.
Search `python.log` for `shotcaller`, `StrongholdBattleRoomWindow`, and
Stronghold entity output. Run again during active Stronghold hours for the
best chance of finding live unit, roster, player, tier, and division data.

## Success criteria

`python.log` contains:

```text
[shotcaller] stronghold entity hook fired: ...
[shotcaller] stronghold entity value: ...
```

`UnitFullData`, roster, `PlayerUnitInfo`, `SlotInfo`, or vehicle information
would be especially useful evidence. This is not a finished mod.
