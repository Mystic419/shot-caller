# Prototype 3O-repair: inherited detachment-exit lifecycle

Prototype 3M loaded safely and created a seven-member normalized Tier 8 cache
for unit `6849134`, including identity, clan, rating, slot, vehicle/intCD,
commander, and legionnaire state. It cleared its cache correctly on unload.

Its `ready=False` output was not yet proven to be a bug: the capture occurred
while the detachment was already in battle, where slots reported
`isFreezed=True`, `playerStatus=3`, and `selectedVehicle.isReadyToFight=True`.

Prototype 3N kept the converter-only architecture and separately stores
`player_ready` from `player.readyState`, `vehicle_ready` from
`selectedVehicle.isReadyToFight`, `player_status`, `is_frozen`, and an explicit
`is_in_battle` field only if supplied by the source. It logs these fields for
validation without converting status into a Boolean ready flag.

Validated state interpretation: `player_status=0` is not ready, `2` is ready,
and `3` is in battle; `frozen=True` is also a reliable in-battle signal.
`vehicle_ready` is independent. The cache therefore adds a derived read-only
`in_battle = bool(is_frozen or player_status == 3)` without changing
`player_ready`.

It also validates unit changes, two-empty-snapshot clearing, narrowly owned
Stronghold watcher start/stop lifecycle confirmation, and a separate in-memory
possible-volunteer cache. It has no raw payload logging, disk writes, APIs, UI,
or player actions.

Prototype 3O correctly identified the lifecycle event but did not install its
hooks: `StrongholdVehiclesWatcher` inherits `start` and `stop` from
`BaseVehiclesWatcher`, so the subclass `__dict__` check skipped both.

Prototype 3O-repair imports the exact base and Stronghold watcher modules,
logs each method origin, and patches only directly owned
`BaseVehiclesWatcher.start` and `.stop`. The wrappers always preserve the
original call, result, and exception. They mutate Shotcaller state only when
the instance is strictly an actual `StrongholdVehiclesWatcher`; ordinary base
watchers—including the normal-hangar replacement—remain completely silent.

A filtered Stronghold stop schedules the existing one-second token/generation
clear. A filtered restart or populated roster cancels it. Thus a normal watcher
replacement cannot clear the cache, while a real detachment exit does.

Build with WoT Python 2.7, then run:

```bat
python build_pyc_wotmod.py
```

Output:

```text
dist\shotcaller_0.0.24_detachment_exit_lifecycle_repair.wotmod
```

Copy to `C:\Games\World_of_Tanks_NA\mods\2.3.0.1\`.

Success criteria:

```text
[shotcaller] watcher lifecycle hooks installed: 2
[shotcaller] watcher filter confirmed: class=StrongholdVehiclesWatcher
[shotcaller] lifecycle validation passed: detachment exit cleared cache
```

Test without restarting WoT: join a detachment, confirm cache population, allow
a transient watcher replacement (which must preserve the cache), leave to the
normal hangar, wait two seconds, and confirm the lifecycle clear. Re-entering
must produce a fresh cache with no stale tier or unit ID.
