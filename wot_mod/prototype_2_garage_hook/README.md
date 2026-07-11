# Prototype 3B: Stronghold Context Probe

This is only a safe Stronghold context diagnostic for Shot-caller. It does not
implement hover popups, roster lookup, Wargaming API lookup, configuration, a
local helper, or backend integration.

## Prototype 3A result

Prototype 3A successfully loaded and detected the Stronghold flow:

```text
[shotcaller] stronghold watcher class: StrongholdVehiclesWatcher
[shotcaller] stronghold watcher started
[shotcaller] stronghold battle room window detected
[shotcaller] stronghold watcher stopped
```

## Prototype 3B behavior

The mod preserves that watcher and window detection, then adds read-only,
bounded diagnostics for `StrongholdVehiclesWatcher` on `start` and its first
`_update`. It logs class/self information, up to 50 non-callable attribute
names, up to 50 method names, and short type/repr details for Stronghold-like
candidates. It only makes guarded no-argument calls to getter-style methods
that do not appear to change state.

Subsequent `_update` messages are rate-limited to avoid log spam. The full
stringified window object is logged, capped at 300 characters, when the
`StrongholdBattleRoomWindow` alias is detected.

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
dist\shotcaller_0.0.9_stronghold_context_probe.wotmod
```

## In-game test

Copy the package to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Run the test now for basic window detection, then run it again during active
Stronghold hours for richer roster and tier data. Launch WoT, enter the
garage, open a Stronghold/skirmish battle room, exit the game, and search
`python.log` for `shotcaller` and `StrongholdBattleRoomWindow`.

## Success criteria

`python.log` contains:

```text
[shotcaller] stronghold watcher started
[shotcaller] stronghold context attribute: ...
[shotcaller] stronghold watcher update
```

The existing `stronghold battle room window detected` and watcher-stop lines
remain useful confirmation. This is not a finished mod.
