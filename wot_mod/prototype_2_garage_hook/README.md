# Prototype 3A: Stronghold Battle Room Detection

This is only a safe Stronghold/battle-room entry and exit detector for
Shot-caller. It does not implement hover popups, roster lookup, Wargaming API
lookup, configuration, a local helper, or backend integration.

## Prototype 2E result

Prototype 2E loaded and installed a lobby-state hook, but it did not fire for
the tested flow. The Stronghold/skirmish test revealed more direct targets:

```text
gui.prb_control.entities.stronghold.unit.vehicles_watcher.StrongholdVehiclesWatcher
StrongholdBattleRoomWindow
https://wgsh-wotus-static.wgcdn.co/.../battlerooms
```

## Prototype 3A behavior

The mod probes `StrongholdVehiclesWatcher`, logs its methods, and safely wraps
`start` and `stop` when present. It also probes WULF/window implementation
classes and wraps at most two `__init__` methods. Those wrappers call the
original method first and only inspect text for `StrongholdBattleRoomWindow`.

Browser support is import-probed only; no browser controller is patched.
Nothing in this prototype changes game state or interacts with battle UI.

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
dist\shotcaller_0.0.8_stronghold_detect.wotmod
```

## In-game test

1. Launch WoT.
2. Enter the garage.
3. Open a Stronghold/skirmish battle room.
4. Exit the game.
5. Search `python.log` for `shotcaller` and `StrongholdBattleRoomWindow`.

Copy the package to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

## Success criteria

`python.log` contains one or both of:

```text
[shotcaller] stronghold watcher started
[shotcaller] stronghold battle room window detected
```

The corresponding stop line after leaving Stronghold is also useful:

```text
[shotcaller] stronghold watcher stopped
```

This is not a finished mod.
