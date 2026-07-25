"""Python 2.7 coverage for resolved/supported tier state separation."""
import imp
mod = imp.load_source('shotcaller_history_state_test', 'mod_shotcaller.py')
def row(tier=None): return {'vehicle_intcd': 1 if tier is not None else None, 'vehicle_level': tier}
assert mod._classify_history_state([row(5)]) == mod.HISTORY_STATE_UNSUPPORTED_TIER
assert mod._classify_history_state([row(None)]) == mod.HISTORY_STATE_INCOMPLETE
assert mod._classify_history_state([row(7), row(8)]) == mod.HISTORY_STATE_MIXED_TIER
mod.LOOKUP_STATUS['inflight'] = False; mod.LOOKUP_STATUS['pending'] = False; mod.LOOKUP_STATUS['lookup_state'] = 'idle'
assert mod._classify_history_state([row(8), row(8)]) == mod.HISTORY_STATE_READY
assert mod._classify_history_state([]) == mod.HISTORY_STATE_EMPTY_ROSTER
print('history state classifier test: ok')
