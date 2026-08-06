"""Python 2.7 coverage for bounded, sequential tanks/stats recovery."""
import imp
import sys
import types

mod = imp.load_source('shotcaller_chunked_rate_limit_test', 'mod_shotcaller.py')
mod.NATIVE_WG_APP_ID = 'test-public-id'
mod.NATIVE_TANKOPEDIA = {88: {'name': 'Test Tank', 'tier': 8, 'type': 'heavyTank'}}
mod.NATIVE_TANKOPEDIA_REALM = 'NA'
mod._native_read_cache = lambda realm, dbid, tier: None
mod._native_write_player_cache = lambda realm, dbid, tier, result: None

def players(count): return [{'dbid': 1000000000 + number, 'name': 'p%s' % number} for number in range(count)]
def setup(rows):
    mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_STRONGHOLD
    mod.CACHE.update({'unit_id': 79, 'tier': 8, 'generation': 1,
                      'rows': dict((row['dbid'], dict(row, in_battle=False)) for row in rows),
                      'order': [row['dbid'] for row in rows]})
    mod.NATIVE_STATS_REQUEST_ACTIVE = False
    mod.NATIVE_INFLIGHT_BATCHES.clear(); mod.LOOKUP_STATUS.update({'inflight': True, 'pending': False, 'lookup_state': 'queued', 'last_attempt_generation': 1})
    key = mod._native_lookup_key('NA', 8, rows); mod.NATIVE_INFLIGHT_BATCHES.add(key)
    return key
def response(rows):
    return {'status': 'ok', 'data': dict((str(row['dbid']), [{'tank_id': 88, 'all': {'battles': 1, 'wins': 1}}]) for row in rows)}

# Fifteen accounts are strictly split into 8 + 7; the final account is whole,
# and final lookup presentation follows original roster order.
rows = players(15); key = setup(rows); calls = []; pending = []; finishes = []; logs = []
mod._log = lambda message: logs.append(message)
mod._native_finish = lambda original, realm, tier, lookup_key, started, results, stale_fallback=None, reason=None: finishes.append((original, results, reason))
def chunk_success(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append((url, accounts)); pending.append((callback, rows[:8] if accounts == 8 else rows[8:])); return {'cancelled': False}
mod.request_json = chunk_success
mod._native_lookup(rows, 'NA', 8, key)
assert [item[1] for item in calls] == [8] and len(pending) == 1
callback, requested = pending.pop(0); callback(response(requested), {'http_status': 200, 'seconds': 0.01})
assert [item[1] for item in calls] == [8, 7] and len(pending) == 1
callback, requested = pending.pop(0); callback(response(requested), {'http_status': 200, 'seconds': 0.01})
assert [item[1] for item in calls] == [8, 7]
assert str(rows[-1]['dbid']) in calls[-1][0] and str(rows[-1]['dbid']) not in calls[0][0]
assert [row['dbid'] for row in finishes[0][0]] == [row['dbid'] for row in rows]
assert [finishes[0][1][row['dbid']]['dbid'] for row in rows] == [row['dbid'] for row in rows]
assert not any('test-public-id' in line or 'https://' in line or '?' in line for line in logs)

# A failed seven-account chunk recovers only that chunk, sequentially. The
# successful eight accounts are never requested again.
key = setup(rows); calls = []; finishes[:] = []
def recover_one_chunk(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append(accounts)
    if accounts == 7:
        errback({'category': 'wg_api', 'http_status': 200, 'endpoint': endpoint, 'accounts': accounts, 'realm': realm,
                 'wg_code': 'INVALID_ACCOUNT_ID', 'wg_message': 'bad account', 'wg_field': 'account_id', 'wg_value': ''})
    else:
        requested = rows[:8] if accounts == 8 else [row for row in rows[8:] if str(row['dbid']) in url]
        callback(response(requested), {'http_status': 200, 'seconds': 0.01})
    return {'cancelled': False}
mod.request_json = recover_one_chunk
mod._native_lookup(rows, 'NA', 8, key)
assert calls == [8, 7] + [1] * 7
assert len(finishes) == 1 and all(finishes[0][1][row['dbid']]['status'] == 'ok' for row in rows)

# BigWorld callback records delayed retries. A rate-limited request retries in
# place and succeeds without a duplicate request for any other account.
scheduled = []; BigWorld = types.ModuleType('BigWorld'); BigWorld.callback = lambda delay, fn: scheduled.append((delay, fn)); sys.modules['BigWorld'] = BigWorld
one = players(1); key = setup(one); calls = []; finishes[:] = []; attempt = [0]
def rate_then_success(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append(accounts); attempt[0] += 1
    if attempt[0] < 3:
        errback({'category': 'wg_api', 'http_status': 200, 'endpoint': endpoint, 'accounts': accounts, 'realm': realm,
                 'wg_code': 'REQUEST_LIMIT_EXCEEDED', 'wg_message': 'limit', 'wg_field': '', 'wg_value': ''})
    else: callback(response(one), {'http_status': 200, 'seconds': 0.01})
    return {'cancelled': False}
mod.request_json = rate_then_success
mod._native_lookup(one, 'NA', 8, key)
assert [delay for delay, fn in scheduled] == [0.75]
scheduled.pop(0)[1](); assert [delay for delay, fn in scheduled] == [1.5]
scheduled.pop(0)[1](); assert len(calls) == 3 and len(finishes) == 1 and finishes[0][1][one[0]['dbid']]['status'] == 'ok'

# Retry exhaustion produces exactly one final error, and an identity change
# cancels a pending retry before it can issue another tanks/stats request.
two = players(1); key = setup(two); calls = []; finishes[:] = []; scheduled[:] = []
def always_limited(url, callback, errback=None, timeout=10.0, endpoint=None, accounts=0, realm=None):
    calls.append(accounts); errback({'category': 'wg_api', 'http_status': 200, 'endpoint': endpoint, 'accounts': accounts, 'realm': realm,
                                     'wg_code': 'REQUEST_LIMIT_EXCEEDED', 'wg_message': 'limit', 'wg_field': '', 'wg_value': ''}); return {'cancelled': False}
mod.request_json = always_limited
mod._native_lookup(two, 'NA', 8, key)
while scheduled: scheduled.pop(0)[1]()
assert calls == [1, 1, 1, 1] and len(finishes) == 1 and finishes[0][1][two[0]['dbid']]['status'] == 'api_error'
three = players(1); key = setup(three); calls = []; finishes[:] = []; scheduled[:] = []
mod._native_lookup(three, 'NA', 8, key)
assert len(scheduled) == 1
mod.CACHE['rows'] = {}; mod.CACHE['order'] = []
scheduled.pop(0)[1]()
assert calls == [1] and len(finishes) == 1

print('chunked rate limit recovery test: ok')
