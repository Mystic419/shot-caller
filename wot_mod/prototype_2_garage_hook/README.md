# Prototype 3C: Stronghold Entity/Unit/Roster Probe

This is only a safe Stronghold entity, unit, roster, and member discovery
probe for Shot-caller. It does not implement hover popups, Wargaming API
lookup, a local helper, configuration, or real UI.

## Prototype 3B result

Prototype 3B confirmed that the package loads, the Stronghold watcher starts,
and the battle-room window is detected. The watcher itself mainly exposed
vehicle suitability/cache state, including `_BaseVehiclesWatcher__itemsCache`,
`_getUnsuitableVehicles`, `_getVehiclesCustomStates`, and `_update`.

## Prototype 3C behavior

The mod logs import status and bounded candidate names for Stronghold unit,
entity, context, item, and requester modules. On watcher `start`, it performs
one guarded PRB getter/dispatcher/entity probe. It only calls no-argument
getter-style accessors and never calls methods that appear to join, leave, set,
assign, kick, invite, ready, select, change, update, start, stop, create, or
destroy state.

Successful values include a short type/repr log and safe keys/attribute names
when they resemble unit, roster, slot, member, player, tier, division, or
state data. Existing battle-room detection remains, and a window context that
contains `wgsh-wotus-static` or `battlerooms` logs a short browser URL line.

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
dist\shotcaller_0.0.10_stronghold_entity_probe.wotmod
```

## In-game test

Copy the package to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Launch WoT, enter the garage, and open a Stronghold/skirmish battle room.
Search `python.log` for `shotcaller`, `StrongholdBattleRoomWindow`, and the
probe output. Run again during active Stronghold hours for the best chance of
finding live roster, tier, division, commander, and player data.

## Success criteria

`python.log` contains:

```text
[shotcaller] stronghold watcher started
[shotcaller] import ok: gui.prb_control.entities.stronghold.unit.entity
[shotcaller] stronghold probe value: ...
```

Roster, unit, member, player, tier, or division data would be especially useful
evidence. This is not a finished mod.
