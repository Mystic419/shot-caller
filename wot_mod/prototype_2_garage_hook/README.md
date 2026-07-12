# Prototype 3I: StrongholdEvent Introspection Probe

This is a safe Stronghold event and web-response diagnostic only.
It does not implement UI, API lookup, a helper, configuration, or backend integration.

## Prototype 3H result

Prototype 3H found the `WebBrowser.sendMessage` response path.
It kept web-id/action correlation and captured the `join_battle` unit ID.
It also exposed repeated `StrongholdEvent` calls in the waiting room.

An access token was accidentally logged in 3H.
Prototype 3I masks access_token, token, session, auth, password, and secret values.

## Prototype 3I behavior

The mod retains command/response correlation and hooks EventBus events.
It logs the first ten StrongholdEvent snapshots, then only changed or roster-relevant ones.
It inspects safe attributes, `__dict__`, and `get*`/`is*`/`has*` methods.
Reserve response dictionaries are summarized rather than dumped.

## Build

Compile `mod_shotcaller.py` with WoT Python 2.7 and place `mod_shotcaller.pyc` beside it.

```bat
python build_pyc_wotmod.py
```

This produces:

```text
dist\shotcaller_0.0.16_stronghold_event_probe.wotmod
```

Copy it to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

## Success criteria

```text
[shotcaller] stronghold event fired: ...
[shotcaller] stronghold event attr: ...
```

Unit, roster, member, player, slot, or vehicle state inside an event is the key result.
This is not a finished mod.
