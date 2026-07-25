# Prototype 0.0.52 — platoon support and history spacing repair

- Regular random-battle platoons are an intentional supported lobby context, identified through `PREBATTLE_TYPE.SQUAD`; Stronghold retains its dedicated watcher lifecycle.
- The history panel now labels its roster context (`Skirmish roster` or `Platoon roster`). Platoon lookup is gated until every occupied member has selected the same supported Tier VI, VIII, or X vehicle.
- Fixed the `Vehicles shown …Heavy` concatenation: the count remains in the fixed header and the scrolling body begins below a 16 px gap.
- Battle, post-battle, special-mode, training, tournament, and enemy roster contexts remain unsupported.
