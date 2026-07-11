# Prototype 1: Minimal Load Test

This prototype is only a minimal load test for Shot-caller World of Tanks integration.

It does not implement UI, networking, lookup, hover popups, config windows, or backend integration.

## Purpose

The only purpose of this prototype is to prove that the WoT client loads the Shot-caller mod entrypoint.

## Files

- `mod_shotcaller.py`
- `build_raw_py_wotmod.bat`
- `build_raw_py_wotmod.py`
- `build_mod_shotcaller_py27.bat`

## Raw Python `.wotmod` package test (no Python 2.7 required)

Before installing Python 2.7, test whether this client will load the raw,
Python-2.7-compatible `mod_shotcaller.py` source from a `.wotmod` package.

Run this from the prototype directory:

```bat
build_raw_py_wotmod.bat
```

The first raw package built with PowerShell `Compress-Archive` was rejected by
WoT with `load error: compression not supported`. A `.wotmod` must therefore
be a ZIP archive in `ZIP_STORED` (no-compression) mode.

The batch script uses Python 3's standard-library `zipfile` module for
packaging only; it does not require Python 2.7 or third-party tools. It creates
a temporary package folder and produces:

```text
dist\shotcaller_0.0.1_raw_py.wotmod
```

Copy `shotcaller_0.0.1_raw_py.wotmod` to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

The package contains this internal path:

```text
res/scripts/client/gui/mods/mod_shotcaller.py
```

### Expected success

The test succeeds if `python.log` contains:

```text
[shotcaller] loaded
```

### If this test fails

If no `[shotcaller] loaded` line appears, we likely need a Python
2.7-compiled `mod_shotcaller.pyc` inside the `.wotmod` package.

## Current test result

The loose `mod_shotcaller.py` test did not load from `res_mods`.

Observed outcome from the in-game test:

- WoT detected `res_mods` and `mods`
- the log showed actual script execution coming from `.pyc` files inside `.wotmod` packages
- there was no `mod_shotcaller` entry
- there was no `[shotcaller] loaded` line

Current conclusion:

- loose `.py` is not sufficient for this client test
- the next test should use a Python 2.7-compiled `mod_shotcaller.pyc`

## Expected target path

The next target test path is:

```text
C:\Games\World_of_Tanks_NA\res_mods\2.3.0.1\scripts\client\gui\mods\mod_shotcaller.pyc
```

If loose `.pyc` still does not load, the next test after that is packaging it as a `.wotmod`.

## Compile with Python 2.7

Do not compile this file with Python 3.

Expected output:

```text
mod_shotcaller.pyc
```

### Option 1: use the batch file

Run:

```bat
build_mod_shotcaller_py27.bat C:\Python27\python.exe
```

### Option 2: run Python 2.7 directly

Run:

```bat
C:\Python27\python.exe -m py_compile mod_shotcaller.py
```

After a successful build, the prototype should produce:

```text
mod_shotcaller.pyc
```

## Success condition

The test succeeds if `python.log` contains:

```text
[shotcaller] loaded
```

## Failure condition

The test fails if:

- no log line appears in `python.log`
- the client reports import errors
- the client reports script load errors
- the loose `.pyc` file is ignored

## Important note

`.py` versus `.pyc` behavior is no longer an open starting assumption for this client test.

Current evidence says loose `.py` did not load in the tested client.

Loose `.pyc` still must be tested in-game.

## Next test if loose `.pyc` still fails

Package the compiled file as:

```text
shotcaller_0.0.1.wotmod
```

Packaging TODO:

```text
shotcaller_0.0.1.wotmod
|- res/
   |- scripts/
      |- client/
         |- gui/
            |- mods/
               |- mod_shotcaller.pyc
```

That packaging step is only a TODO for the next test. It is not implemented in this prototype yet.
