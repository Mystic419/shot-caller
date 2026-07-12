# Prototype 3G: Stronghold Web/Browser Bridge Probe

This is only a safe Stronghold browser bridge diagnostic for Shot-caller. It
does not implement hover popups, Wargaming API lookup, a local helper,
configuration, or real UI.

## Prototype 3F result

Prototype 3F confirmed that BrowserEntity lifecycle and delayed dumps work, but
`getMembers`, `getPlayers`, `getUnit`, and stats remained empty even after a
teammate joined. The client then showed `StrongholdView` and initialized the
web-backed Stronghold SPA:

```text
ViewKey[alias=StrongholdView, name=StrongholdView]
https://wgsh-wotus-static.wgcdn.co/auth/entry?...
```

The next investigation is the browser/web bridge rather than BrowserEntity
roster getters.

## Prototype 3G behavior

BrowserEntity hooks remain only as lightweight lifecycle logging. The mod
probes BrowserController, lobby browser, web-handler, event bus, and event
modules; logs import status and candidate names; then safely hooks existing
browser create/show/delete methods and a bounded number of obvious web-message
dispatch methods.

Each wrapper calls the original first. It only logs safely stringified context;
it never sends browser messages, changes game state, calls an API, or displays
UI. The first 100 web-bridge calls are logged, then only calls whose text looks
roster-related are retained. Payload text is capped at 1000 characters.

StrongholdView, StrongholdBattleRoomWindow, browser modal/popover aliases, and
matching Stronghold URLs remain detected.

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
dist\shotcaller_0.0.14_stronghold_web_bridge_probe.wotmod
```

## In-game test

Copy the package to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

Open the Stronghold/skirmish flow, create or enter a unit, and have a teammate
join, leave, or select a vehicle if possible. Search `python.log` for
`StrongholdView`, browser URLs, and `web bridge candidate` lines.

## Success criteria

```text
[shotcaller] stronghold view detected: ...
[shotcaller] browser url: ...
[shotcaller] web bridge candidate: ...
```

Payload text containing player, member, slot, vehicle, or roster data is the
key result. This is not a finished mod.
