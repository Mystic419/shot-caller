"""Python 2.7 coverage for the standalone native lookup coordinator."""
import imp
import os
import shutil
import time

mod = imp.load_source('shotcaller_native_lookup_test', 'mod_shotcaller.py')

assert mod.NATIVE_REALMS['NA'] == 'https://api.worldoftanks.com'
assert mod.NATIVE_REALMS['EU'] == 'https://api.worldoftanks.eu'
assert mod.NATIVE_REALMS['ASIA'] == 'https://api.worldoftanks.asia'
mod.NATIVE_WG_APP_ID = 'test-public-id'
url = mod._native_url('NA', 'tanks/stats', {'account_id': '1,2', 'fields': 'tank_id,all.battles'})
assert url.startswith('https://api.worldoftanks.com/wot/tanks/stats/?')
assert 'account_id=1%2C2' in url and 'application_id=test-public-id' in url

records = [{'tank_id': 7, 'all': {'battles': 9, 'wins': 4}}, {'tank_id': 8, 'all': {'battles': -1}}]
tanks = {7: {'name': 'Tank Seven', 'tier': 8, 'type': 'heavyTank'}, 8: {'name': 'Tank Eight', 'tier': 8, 'type': 'mediumTank'}}
result = mod._native_result({'dbid': 1, 'name': 'tester'}, records, tanks, 8)
assert result['status'] == 'ok' and result['vehicles'][0]['battles'] == 9 and result['vehicles'][1]['battles'] == 0
assert mod._native_result({'dbid': 2, 'name': 'missing'}, None, tanks, 8)['status'] == 'no_account'
assert mod._native_result({'dbid': 3, 'name': 'empty'}, [], tanks, 8)['status'] == 'no_vehicle_history'

test_cache = 'native_lookup_test_cache'
if os.path.isdir(test_cache): shutil.rmtree(test_cache)
mod.NATIVE_CACHE_DIR = test_cache
mod._native_write_player_cache('NA', 1, 8, result)
cached = mod._native_read_cache('NA', 1, 8)
assert cached and cached['result']['vehicles'][0]['battles'] == 9
cached['fetched_at'] = time.time() - mod.NATIVE_CACHE_TTL - 1
open(mod._native_cache_path('NA', 1, 8), 'wb').write(mod.json.dumps(cached))
assert time.time() - mod._native_read_cache('NA', 1, 8)['fetched_at'] > mod.NATIVE_CACHE_TTL
open(mod._native_cache_path('NA', 2, 8), 'wb').write('not json')
assert mod._native_read_cache('NA', 2, 8) is None
shutil.rmtree(test_cache)

captured = []
mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_STRONGHOLD
mod.CACHE.update({'unit_id': 77, 'tier': 8, 'generation': 4, 'rows': {}, 'order': []})
mod.LOOKUP_STATUS.update({'inflight': False, 'pending': False, 'lookup_state': 'idle'})
mod._native_lookup = lambda players, realm, tier, key: captured.append((players, realm, tier, key))
rows = [{'dbid': 4, 'name': 'a'}, {'dbid': 4, 'name': 'duplicate'}, {'dbid': 0, 'name': 'invalid'}, {'dbid': None, 'name': 'missing'}, {'dbid': 5, 'name': 'b'}]
mod._queue_lookup(rows, force=True)
assert len(captured) == 1 and [player['dbid'] for player in captured[0][0]] == [4, 5]
mod._queue_lookup(rows, force=True)
assert len(captured) == 1
key = mod._native_lookup_key('NA')
assert mod._native_is_stale(key) is False
# Ready/status and same-tier vehicle presentation changes advance broad roster
# generation, but are not part of the public-history identity.
mod.CACHE['generation'] = 5
assert mod._native_is_stale(key) is False
mod.CACHE['rows'] = {4: {'dbid': 4, 'in_battle': False}, 5: {'dbid': 5, 'in_battle': False}}
mod.CACHE['order'] = [4, 5]
key = mod._native_lookup_key('NA')
mod.CACHE['generation'] = 6
assert mod._native_is_stale(key) is False
mod.CACHE['tier'] = 6
assert mod._native_is_stale(key) is True
mod.CACHE['tier'] = 8
mod.CACHE['rows'].pop(5)
assert mod._native_is_stale(key) is True
mod.CACHE['rows'][5] = {'dbid': 5, 'in_battle': True}
assert mod._native_is_stale(key) is True
mod.CACHE['rows'][5]['in_battle'] = False
mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_NONE
assert mod._native_is_stale(key) is True
mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_STRONGHOLD

# A broad generation-only change accepts the response, stores it for the
# current member, and refreshes an already-open pending history panel.
mod.CACHE.update({'unit_id': 77, 'tier': 8, 'generation': 20,
                  'rows': {4: {'dbid': 4, 'in_battle': False}, 5: {'dbid': 5, 'in_battle': False}},
                  'order': [4, 5]})
lookup_key = mod._native_lookup_key('NA')
mod.CACHE['generation'] = 21
mod.NATIVE_INFLIGHT_BATCHES.add(lookup_key)
mod.LOOKUP_STATUS.update({'inflight': True, 'pending': False, 'lookup_state': 'queued', 'last_attempt_generation': 20})
refreshed = []
mod._schedule_panel_refresh = lambda: refreshed.append(True)
mod.LOOKUPS.clear()
mod._native_finish([{'dbid': 4, 'name': 'a'}, {'dbid': 5, 'name': 'b'}], 'NA', 8, lookup_key, time.time(),
                   {4: {'dbid': 4, 'name': 'a', 'status': 'ok', 'vehicles': [{'tank_id': 7, 'battles': 9}]},
                    5: {'dbid': 5, 'name': 'b', 'status': 'no_vehicle_history', 'vehicles': []}})
assert mod.LOOKUPS[4]['vehicles'][0]['battles'] == 9 and refreshed and mod.LOOKUP_STATUS['lookup_state'] == 'complete'

# A material roster identity change triggers exactly one replacement attempt.
replacement = []
mod._queue_lookup = lambda rows, force=False: replacement.append(list(rows))
mod.CACHE['rows'].pop(5); mod.CACHE['order'] = [4]
mod.NATIVE_INFLIGHT_BATCHES.add(lookup_key); mod.LOOKUP_STATUS.update({'inflight': True, 'pending': False, 'lookup_state': 'queued'})
mod._native_finish([{'dbid': 4, 'name': 'a'}, {'dbid': 5, 'name': 'b'}], 'NA', 8, lookup_key, time.time(), {})
assert len(replacement) == 1 and len(replacement[0]) == 1

source = open('mod_shotcaller.py', 'rb').read().lower()
assert '127.0.0.1' not in source and 'localhost' not in source and 'sidecar unavailable' not in source
print('native lookup test: ok')
