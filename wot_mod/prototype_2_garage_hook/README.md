# Prototype 2: Garage/Lobby Hook Test

This is only a harmless garage/lobby lifecycle hook test for Shot-caller. It
does not implement detachment UI, hover popups, configuration, Wargaming API
lookups, a local helper, or backend integration.

## Confirmed package structure

The working Aslain reference package
`platoon_window.2.3.0.1.1.2.wotmod` confirmed this structure:

```text
meta.xml
res/scripts/client/gui/mods/mod_platoon_window.pyc
```

Prototype 1 confirmed that a `ZIP_STORED` (no-compression) `.wotmod` is
detected by WoT. The raw `.py` package loads but does not execute. The next
working candidate must therefore contain a WoT-compatible `.pyc` plus
`meta.xml` at the archive root.

## Files

- `mod_shotcaller.py` - Python 2.7-compatible garage hook source
- `build_pyc_wotmod.py` - creates the `.pyc` + `meta.xml` test package
- `build_raw_py_wotmod.bat` and `build_raw_py_wotmod.py` - earlier raw-source
  package test only

## Build the `.pyc` candidate

First compile `mod_shotcaller.py` with the WoT-compatible Python version and
place the resulting file beside the source as:

```text
mod_shotcaller.pyc
```

Then run:

```bat
python build_pyc_wotmod.py
```

The script produces:

```text
dist\shotcaller_0.0.3_pyc.wotmod
```

Its uncompressed ZIP contents are exactly:

```text
meta.xml
res/scripts/client/gui/mods/mod_shotcaller.pyc
```

## In-game test

Remove earlier Shot-caller test packages before testing this one. Copy
`shotcaller_0.0.3_pyc.wotmod` to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Start WoT and enter the garage/lobby.

## Success criteria

`python.log` contains:

```text
[shotcaller] loaded
[shotcaller] garage hook fired
```

## Failure criteria

The test failed if the package loads but no garage-hook log line appears, or if
`python.log` contains import or hook errors. In particular, a
`[shotcaller] hook install failed: ...` line means the client lifecycle target
needs to be confirmed from matching client references before the next attempt.

This is not a finished mod. It is deliberately limited to proving a safe
garage/lobby hook.
