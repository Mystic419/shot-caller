# Prototype 3N: roster-cache correctness and lifecycle validation

Prototype 3M loaded safely and created a seven-member normalized Tier 8 cache
for unit `6849134`, including identity, clan, rating, slot, vehicle/intCD,
commander, and legionnaire state. It cleared its cache correctly on unload.

Its `ready=False` output was not yet proven to be a bug: the capture occurred
while the detachment was already in battle, where slots reported
`isFreezed=True`, `playerStatus=3`, and `selectedVehicle.isReadyToFight=True`.

Prototype 3N keeps the same converter-only architecture and separately stores
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

On watcher stop it schedules a one-second token-protected exit clear. A watcher
restart or any populated `makeSlotsVOs` result cancels that pending clear; if
neither arrives, active and volunteer caches clear while WoT remains open.

Build with WoT Python 2.7, then run:

```bat
python build_pyc_wotmod.py
```

Output:

```text
dist\shotcaller_0.0.22_skirmish_roster_cache_validation.wotmod
```

Copy to `C:\Games\World_of_Tanks_NA\mods\2.3.0.1\`.

Success criteria:

```text
[shotcaller] state validation: name=<name> player_ready=<value> vehicle_ready=<value> player_status=<value> frozen=<value>
[shotcaller] roster cache changed: members=<n> tier=<tier> generation=<n>
[shotcaller] roster empty confirmation pending: 1/2
```

Success means correct pre-battle versus in-battle state evidence, one or more
live changes, cache clearing after room exit, fresh repopulation on re-entry,
no duplicate snapshots, and normal client startup/lobby behavior.
