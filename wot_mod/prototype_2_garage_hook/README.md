# Prototype 3L-repair: safe Skirmish converter probe

Prototype 3L failed before reaching the hangar because it broadly monkey-patched
shared Scaleform framework classes during startup. The client then raised
`AttributeError: 'function' object has no attribute 'DAMAGED'` while importing
the trade-in popup, followed by a missing lobby `getViewSettings` error.

This repair deliberately does not patch any view, setting, component, loader,
constructor, base/framework class, global registration path, or module function
other than these exact functions in `rally.vo_converters`:

- `getUnitRosterData`, `getUnitRosterModel`, `makeSortiePlayerVO`, `makePlayerVO`
- `makeUnitRosterVO`, `makeSlotsVOs`, `makeVehicleVO`, `makeVehicleBasicVO`
- `makeFortClanBattleRoomVO`

It only discovers candidate names in five narrow modules. Converter and waiting
manager wrappers preserve arguments, return values, and original exceptions;
they log only after a successful original call. Waiting-manager methods are
patched only when directly present on that class. Sensitive values stay masked.

Build with WoT Python 2.7, then run:

```bat
python build_pyc_wotmod.py
```

Output:

```text
dist\shotcaller_0.0.20_skirmish_ui_safe_probe.wotmod
```

Copy to `C:\Games\World_of_Tanks_NA\mods\2.3.0.1\`.

Success criteria:

```text
[shotcaller] lobby getViewSettings intact: True
[shotcaller] safe converter hooks installed: <count>
[shotcaller] converter hook fired: makePlayerVO
```

First confirm the client reaches the hangar. Converter calls before entering
Skirmish are optional; the target result is a converter payload containing real
member, vehicle, and slot data after entering the waiting room.
