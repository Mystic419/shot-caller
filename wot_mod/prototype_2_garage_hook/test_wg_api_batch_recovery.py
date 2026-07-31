"""Python 2.7 coverage for native WG batch error recovery."""
import imp
import time

mod = imp.load_source('shotcaller_wg_batch_recovery_test', 'mod_shotcaller.py')
mod.NATIVE_WG_APP_ID = 'test-public-id'
mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_STRONGHOLD
mod.CACHE.update({'unit_id': 901, 'tier': 8, 'generation': 1,
                  'rows': {1: {'dbid': 1, 'in_battle': False}, 2: {'dbid': 2, 'in_battle': False}, 3: {'dbid': 3, 'in_battle': False}},
                  'order': [1, 2, 3]})
mod.NATIVE_TANKOPEDIA = {88: {'name': 'Tier Eight', 'tier': 8, 'type': 'heavyTank'}}
mod.NATIVE_TANKOPEDIA_REALM = 'NA'
mod.LOOKUP_STATUS.update({'inflight': True, 'pending': False, 'lookup_state': 'queued', 'last_attempt_generation': 1})
players = [{'dbid': 1, 'name': 'cached'}, {'dbid': 2, 'name': 'success'}, {'dbid': 3, 'name': 'failure'}]
lookup_key = mod._native_lookup_key('NA', 8, players)
mod.NATIVE_INFLIGHT_BATCHES.add(lookup_key)

cached_result = {'dbid': 1, 'name': 'cached', 'status': 'ok', 'vehicles': [{'tank_id': 88, 'name': 'Tier Eight', 'tier': 8, 'type': 'heavyTank', 'battles': 2, 'wins': 1}]}
mod._native_read_cache = lambda realm, dbid, tier: {'fetched_at': time.time(), 'result': cached_result} if dbid == 1 else None
writes = []
mod._native_write_player_cache = lambda realm, dbid, tier, result: writes.append((dbid, result['status']))
finishes = []
original_finish = mod._native_finish
mod._native_finish = lambda players, realm, tier, key, started, results, stale_fallback=None, reason=None: finishes.append((results, reason))
logs = []
mod._log = lambda message: logs.append(message)
calls = []

def fake_request(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append((url, endpoint, accounts, realm))
    if accounts > 1:
        errback({'category': 'wg_api', 'http_status': 200, 'endpoint': endpoint, 'accounts': accounts, 'realm': realm,
                 'wg_code': '407', 'wg_message': 'invalid account batch', 'wg_field': 'account_id', 'wg_value': 'two'})
    elif 'account_id=2' in url:
        callback({'status': 'ok', 'data': {'2': [{'tank_id': 88, 'all': {'battles': 6, 'wins': 3}}]}}, {'http_status': 200, 'seconds': 0.1})
    else:
        errback({'category': 'wg_api', 'http_status': 200, 'endpoint': endpoint, 'accounts': accounts, 'realm': realm,
                 'wg_code': '404', 'wg_message': 'unavailable', 'wg_field': '', 'wg_value': ''})
    return {'cancelled': False}

mod.request_json = fake_request
mod._native_lookup(players, 'NA', 8, lookup_key)
assert len(calls) == 4, calls  # legacy cached result also receives its one mastery upgrade request
assert len(finishes) == 1
results = finishes[0][0]
assert results[1]['status'] == 'ok' and results[1]['vehicles'][0]['battles'] == 2
assert results[2]['status'] == 'ok' and results[2]['vehicles'][0]['battles'] == 6
assert results[3]['status'] == 'api_error' and 'Wargaming API' in results[3]['message']
assert writes == [(2, 'ok')]
assert any('native WG API error: endpoint=tanks/stats code=407' in line for line in logs)
assert not any('test-public-id' in line or 'https://' in line for line in logs)

# Navigation can continue to a valid result and presents the failed member as
# an information state rather than a no-vehicle result.
mod.CACHE.update({'rows': {2: {'dbid': 2, 'name': 'success', 'slot_index': 0, 'vehicle_intcd': 88, 'vehicle_level': 8},
                           3: {'dbid': 3, 'name': 'failure', 'slot_index': 1, 'vehicle_intcd': 88, 'vehicle_level': 8}}, 'order': [2, 3]})
mod.LOOKUPS.clear(); mod.LOOKUPS.update(results)
assert mod._panel_state(mod.CACHE['rows'][2])[0] == 'ready'
error_state, error_result = mod._panel_state(mod.CACHE['rows'][3])
assert error_state == 'error'
assert 'Vehicle history unavailable from the Wargaming API.' in mod._panel_message(mod.CACHE['rows'][3], error_state, error_result)

# A status=ok response missing one requested account marks only that account
# unavailable while retaining the valid result for the other account.
finishes[:] = []; calls[:] = []
mod._native_read_cache = lambda realm, dbid, tier: None
mod.CACHE.update({'rows': {2: {'dbid': 2, 'in_battle': False}, 3: {'dbid': 3, 'in_battle': False}}, 'order': [2, 3]})
partial_players = [{'dbid': 2, 'name': 'present'}, {'dbid': 3, 'name': 'missing'}]
partial_key = mod._native_lookup_key('NA', 8, partial_players)
mod.NATIVE_INFLIGHT_BATCHES.add(partial_key)
def partial_request(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append((url, accounts))
    callback({'status': 'ok', 'data': {'2': [{'tank_id': 88, 'all': {'battles': 1, 'wins': 1}}]}}, {'http_status': 200, 'seconds': 0.1})
    return {'cancelled': False}
mod.request_json = partial_request
mod._native_lookup(partial_players, 'NA', 8, partial_key)
assert len(calls) == 1 and len(finishes) == 1
assert finishes[0][0][2]['status'] == 'ok'
assert finishes[0][0][3]['status'] == 'api_error'

# Error output has deliberately safe, scalar diagnostics only.
safe = []
mod._log = lambda message: safe.append(message)
mod._native_log_wg_api_error({'endpoint': 'tanks/stats', 'wg_code': '407', 'wg_message': 'bad request',
                               'wg_field': 'account_id', 'wg_value': 'two', 'accounts': 2, 'realm': 'NA'})
assert 'endpoint=tanks/stats' in safe[0] and 'application_id' not in safe[0] and 'http' not in safe[0]
assert mod._native_safe_wg_error_value('test-public-id', 'application_id') == '***MASKED***'
mod._native_finish = original_finish
print('WG API batch recovery test: ok')
