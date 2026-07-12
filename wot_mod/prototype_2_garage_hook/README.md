# Prototype 3J: StrongholdClanData Probe

Prototype 3I confirmed active Stronghold mode through `strongholdOnTimer`:
tier 8, Sortie, and the `squadInBattle` waiting state were captured. Its
context also exposed a live `StrongholdClanData` object. Timer events are not
roster data and are now logged only when their tracked status changes.

This probe inspects each StrongholdClanData object once, including safe attrs
and getters for clan, members, players, roster, slots, vehicles, commander,
division, tier, and unit data. It keeps masked web responses, join-battle
summaries, watcher logs, and only Stronghold-specific window detection.

## Build

Compile `mod_shotcaller.py` with WoT Python 2.7, then run:

```bat
python build_pyc_wotmod.py
```

Output:

```text
dist\shotcaller_0.0.17_stronghold_clan_data_probe.wotmod
```

Copy to:

```text
C:\Games\World_of_Tanks_NA\mods\2.3.0.1\
```

## Success criteria

```text
[shotcaller] stronghold status: ...
[shotcaller] clan data attr: ...
[shotcaller] stronghold event changed: ...
```

`strongholdVehicleSelected` with vehicle/player context is especially useful.
This is not a finished mod.
