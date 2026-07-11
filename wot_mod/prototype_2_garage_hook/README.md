# Prototype 2B: Garage/Lobby Import Discovery

This is only a garage/lobby import and hook discovery run for Shot-caller. It
does not implement detachment UI, hover popups, configuration, Wargaming API
lookups, a local helper, or backend integration.

## Confirmed results

Prototype 2A loaded and executed successfully as a WoT-compatible `.pyc`
inside a `.wotmod` package:

```text
[ASL] executed script in mods folder: mod_shotcaller.pyc
[shotcaller] loaded
```

The earlier guessed `hangar` import failed, so it is no longer a dependency or
a hook target. Prototype 2B only probes likely lobby/garage modules and logs
what this client exposes; it does not patch any lifecycle method.

The confirmed package structure remains:

```text
meta.xml
res/scripts/client/gui/mods/mod_shotcaller.pyc
```

The package is a `ZIP_STORED` (no-compression) archive.

## Files

- `mod_shotcaller.py` - Python 2.7-compatible import discovery mod
- `build_pyc_wotmod.py` - creates the `.pyc` + `meta.xml` test package
- `build_raw_py_wotmod.bat` and `build_raw_py_wotmod.py` - earlier raw-source
  package test only

## Build

First compile `mod_shotcaller.py` with the WoT-compatible Python version and
place the resulting file beside the source as:

```text
mod_shotcaller.pyc
```

Then run:

```bat
python build_pyc_wotmod.py
```

This produces:

```text
dist\shotcaller_0.0.4_garage_probe.wotmod
```

## In-game test

Remove earlier Shot-caller test packages before testing this one. Copy
`shotcaller_0.0.4_garage_probe.wotmod` to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Start WoT and enter the garage/lobby.

## Success criteria

`python.log` shows the environment and per-module import results, including
lines such as:

```text
[shotcaller] loaded
[shotcaller] python version: ...
[shotcaller] BigWorld import: ok
[shotcaller] import ok: gui.Scaleform.daapi.view.lobby
[shotcaller] import missing: gui.impl.lobby.hangar
```

If a likely class or lifecycle symbol is present, the probe logs it as a
`class candidate` or `hook candidate`; it does not patch it.

## Failure criteria

The test failed if the package does not load, no import results appear in
`python.log`, or import/probe errors appear. This is not a finished mod.
