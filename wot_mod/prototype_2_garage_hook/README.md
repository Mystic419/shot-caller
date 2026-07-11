# Prototype 2D: Modern Hangar Module Discovery

This is only a read-only Modern WULF/Gameface hangar discovery run for
Shot-caller. It does not implement detachment UI, hover popups, configuration,
Wargaming API lookups, a local helper, or backend integration.

## Prototype 2C result

Prototype 2C loaded and executed, but the legacy
`gui.Scaleform.daapi.view.lobby.hangar.Hangar` class did not expose any of the
tested lifecycle methods. The client logs instead show the modern hangar path:

```text
Loading window: HangarWindow(... content=RandomHangar(...))
Gameface Load view mono/hangar/main
HANGAR LOADING STATE: HANGAR UI READY
```

## Prototype 2D goal

Probe likely Modern WULF/Gameface hangar, window, and lobby state-machine
modules. For each module, `python.log` records its import result and up to 30
candidate names containing hangar, random, window, state, load, initialize,
enter, or create. Prototype 2D does not monkey-patch any class or method.

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
dist\shotcaller_0.0.6_modern_hangar_probe.wotmod
```

## In-game test

Remove earlier Shot-caller test packages before testing this one. Copy
`shotcaller_0.0.6_modern_hangar_probe.wotmod` to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Start WoT and enter the garage/lobby.

## Success criteria

`python.log` contains:

```text
[shotcaller] loaded
[shotcaller] import ok: <modern module>
[shotcaller] candidate: <modern module>.<class or function>
```

Import failures are also useful evidence and are logged as:

```text
[shotcaller] import missing: <module>: <error>
```

This is not a finished mod.
