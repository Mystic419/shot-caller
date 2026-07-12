"""Prototype 3N: read-only Skirmish roster lifecycle validation."""
import re
import time

TAG = '[shotcaller]'
MARK = '_shotcaller_3n_'
CONVERTER_MODULE = 'gui.Scaleform.daapi.view.lobby.rally.vo_converters'
PRIMARY = 'makeSlotsVOs'
SUPPORTING = ('makePlayerVO', 'makeVehicleVO', 'makeVehicleBasicVO')
SENSITIVE = re.compile(r"(?i)(access_token|token2?|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
CACHE = {'rows': {}, 'order': [], 'unit_id': None, 'tier': None, 'last_update': None, 'generation': 0}
VOLUNTEERS = {}
EMPTY_SNAPSHOTS = 0
EXIT_TOKEN = 0
PENDING_EXIT = None

def _log(text): print(TAG + ' ' + text)
def _text(value, limit=500):
    try: return SENSITIVE.sub(r'\1\2***MASKED***', str(value)[:limit])
    except Exception: return '<unavailable>'
def _copy(value): return dict(value) if isinstance(value, dict) else None

def get_roster_snapshot(): return [_copy(CACHE['rows'][key]) for key in CACHE['order'] if key in CACHE['rows']]
def get_roster_member(dbid): return _copy(CACHE['rows'].get(dbid))
def get_current_tier(): return CACHE['tier']
def get_current_unit_id(): return CACHE['unit_id']
def get_roster_generation(): return CACHE['generation']
def get_volunteer_snapshot(): return [_copy(row) for row in VOLUNTEERS.values()]

def _get(data, key, default=None):
    try: return data[key] if key in data else default
    except Exception: return default
def _int(value):
    try: return int(value)
    except Exception: return None
def _vehicle(row): return row.get('vehicle_name') or row.get('vehicle_short_name') or row.get('vehicle_internal_name') or 'None'

def _normalize(slot, index):
    player = _get(slot, 'player', {})
    if not isinstance(player, dict) or not player or _get(player, 'dbID') is None: return None
    vehicle = _get(slot, 'selectedVehicle', {})
    if not isinstance(vehicle, dict): vehicle = {}
    return {
        'slot_index': index, 'unit_id': _get(slot, 'rallyIdx'), 'dbid': _get(player, 'dbID'),
        'account_id': _get(player, 'accID'), 'name': _get(player, 'userName'),
        'full_name': _get(player, 'fullName'), 'clan': _get(player, 'clanAbbrev'),
        'rating': _get(player, 'rating'), 'player_ready': _get(player, 'readyState'),
        'vehicle_ready': _get(vehicle, 'isReadyToFight'), 'player_status': _get(slot, 'playerStatus'),
        'is_frozen': _get(slot, 'isFreezed'),
        'is_in_battle': _get(slot, 'isInBattle', _get(player, 'isInBattle')),
        'commander': _get(player, 'isCommander'), 'offline': _get(player, 'isOffline'),
        'role': _get(slot, 'role'), 'is_legionnaire': _get(slot, 'isLegionaries'),
        'is_current_user': _get(slot, 'isCurrentUserInSlot'),
        'vehicle_intcd': _get(vehicle, 'intCD'), 'vehicle_name': _get(vehicle, 'userName'),
        'vehicle_short_name': _get(vehicle, 'shortUserName'), 'vehicle_internal_name': _get(vehicle, 'name'),
        'vehicle_level': _int(_get(vehicle, 'level', _get(slot, 'selectedVehicleLevel'))),
        'vehicle_type': _get(vehicle, 'type'), 'vehicle_nation_id': _get(vehicle, 'nationID'),
        'in_battle': bool(_get(slot, 'isFreezed') or _get(slot, 'playerStatus') == 3)}

def _state(row):
    _log('state validation: name=%s player_ready=%s vehicle_ready=%s player_status=%s frozen=%s' %
         (row['name'], row['player_ready'], row['vehicle_ready'], row['player_status'], row['is_frozen']))
def _row(row):
    _log('roster member: slot=%s dbID=%s name=%s clan=%s rating=%s vehicle=%s intCD=%s tier=%s player_ready=%s commander=%s legionnaire=%s' %
         (row['slot_index'], row['dbid'], row['name'], row['clan'], row['rating'], _vehicle(row), row['vehicle_intcd'], row['vehicle_level'], row['player_ready'], row['commander'], row['is_legionnaire']))

def _clear(reason):
    global EMPTY_SNAPSHOTS, PENDING_EXIT
    if CACHE['rows'] or VOLUNTEERS:
        CACHE['rows'] = {}; CACHE['order'] = []; CACHE['unit_id'] = None; CACHE['tier'] = None; CACHE['last_update'] = None
        VOLUNTEERS.clear(); CACHE['generation'] += 1; _log('roster cache cleared: reason=' + reason)
    EMPTY_SNAPSHOTS = 0; PENDING_EXIT = None

def _cancel_exit(reason):
    global EXIT_TOKEN, PENDING_EXIT
    if PENDING_EXIT is not None:
        EXIT_TOKEN += 1; PENDING_EXIT = None
        _log('Stronghold exit clear cancelled: reason=' + reason)

def _remove_volunteer(dbid):
    row = VOLUNTEERS.pop(dbid, None)
    if row: _log('volunteer removed: dbID=%s name=%s' % (dbid, row['name']))

def _apply(rows):
    global EMPTY_SNAPSHOTS
    if not rows:
        if CACHE['rows']:
            EMPTY_SNAPSHOTS += 1
            _log('roster empty confirmation pending: %s/2' % EMPTY_SNAPSHOTS)
            if EMPTY_SNAPSHOTS >= 2: _clear('two consecutive empty snapshots')
        return
    EMPTY_SNAPSHOTS = 0; _cancel_exit('roster update')
    new = {}; order = []
    for row in rows: new[row['dbid']] = row; order.append(row['dbid'])
    unit_id = next((row['unit_id'] for row in rows if row['unit_id'] is not None), None)
    tier = next((row['vehicle_level'] for row in rows if row['vehicle_level'] in (6, 8, 10)), None)
    if CACHE['unit_id'] is not None and unit_id is not None and CACHE['unit_id'] != unit_id:
        old_id = CACHE['unit_id']; _clear('unit changed old=%s new=%s' % (old_id, unit_id))
    old = CACHE['rows']
    changed = old != new or CACHE['order'] != order or CACHE['tier'] != tier or CACHE['unit_id'] != unit_id
    if not changed: return
    first = not old
    for dbid, row in new.items():
        _remove_volunteer(dbid)
        previous = old.get(dbid)
        if previous is None: _log('roster member added: dbID=%s name=%s vehicle=%s' % (dbid, row['name'], _vehicle(row)))
        else:
            if any(previous[key] != row[key] for key in ('vehicle_intcd', 'vehicle_name', 'vehicle_level')):
                _log('roster vehicle changed: name=%s old=%s new=%s' % (row['name'], _vehicle(previous), _vehicle(row)))
            if previous['player_ready'] != row['player_ready']:
                _log('roster player ready changed: name=%s old=%s new=%s' % (row['name'], previous['player_ready'], row['player_ready']))
            if previous['vehicle_ready'] != row['vehicle_ready']:
                _log('roster vehicle ready changed: name=%s old=%s new=%s' % (row['name'], previous['vehicle_ready'], row['vehicle_ready']))
            if previous['slot_index'] != row['slot_index']:
                _log('roster slot changed: name=%s old=%s new=%s' % (row['name'], previous['slot_index'], row['slot_index']))
            if previous['commander'] != row['commander']:
                _log('roster commander changed: name=%s old=%s new=%s' % (row['name'], previous['commander'], row['commander']))
            if previous['player_status'] != row['player_status']:
                _log('roster player status changed: name=%s old=%s new=%s' % (row['name'], previous['player_status'], row['player_status']))
            if previous['is_frozen'] != row['is_frozen']:
                _log('roster frozen changed: name=%s old=%s new=%s' % (row['name'], previous['is_frozen'], row['is_frozen']))
    for dbid, row in old.items():
        if dbid not in new: _log('roster member removed: dbID=%s name=%s' % (dbid, row['name']))
    CACHE['rows'] = new; CACHE['order'] = order; CACHE['unit_id'] = unit_id; CACHE['tier'] = tier; CACHE['last_update'] = time.time(); CACHE['generation'] += 1
    if tier is not None: _log('skirmish tier detected: ' + str(tier))
    if first: _log('roster cache populated: members=%s tier=%s unit_id=%s' % (len(rows), tier, unit_id))
    else: _log('roster cache changed: members=%s tier=%s generation=%s' % (len(rows), tier, CACHE['generation']))
    for row in rows: _state(row); _row(row)

def _extract(result):
    if not isinstance(result, (tuple, list)) or len(result) < 2 or not isinstance(result[1], (tuple, list)):
        raise ValueError('makeSlotsVOs result is not (boolean, slot list)')
    rows = []
    for index, slot in enumerate(result[1]):
        if isinstance(slot, dict):
            row = _normalize(slot, index)
            if row is not None: rows.append(row)
    _apply(rows)

def _primary_hook(original):
    def hook(*args, **kwargs):
        result = original(*args, **kwargs)
        try: _extract(result)
        except Exception as error: _log('roster extraction error: ' + _text(error, 300))
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _info_value(info, names):
    for name in names:
        try:
            value = getattr(info, name)
            return value() if callable(value) and name.startswith('get') else value
        except Exception: pass
    return None

def _support_hook(name, original):
    def hook(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            if name == 'makePlayerVO':
                info = next((value for value in args if hasattr(value, 'isInSlot')), None)
                if info is not None and info.isInSlot() is False:
                    dbid = _info_value(info, ('dbID', 'getDbID'))
                    if dbid is not None and dbid not in CACHE['rows'] and dbid not in VOLUNTEERS:
                        candidate = result if isinstance(result, dict) else {}
                        row = {'dbid': dbid, 'name': _get(candidate, 'userName', _info_value(info, ('name', 'getName'))),
                               'clan': _get(candidate, 'clanAbbrev', _info_value(info, ('clanAbbrev', 'getClanAbbrev')))}
                        VOLUNTEERS[dbid] = row; _log('volunteer added: dbID=%s name=%s clan=%s' % (dbid, row['name'], row['clan']))
        except Exception: pass
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _watcher_hook(name, original):
    def hook(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        global EXIT_TOKEN, PENDING_EXIT
        if name == 'start':
            _cancel_exit('restart')
            return result
        if name == 'stop':
            EXIT_TOKEN += 1; token = EXIT_TOKEN; PENDING_EXIT = token
            _log('Stronghold exit clear scheduled')
            def confirm():
                global PENDING_EXIT
                if PENDING_EXIT == token and CACHE['rows']:
                    _clear('Stronghold watcher stopped')
            try:
                import BigWorld; BigWorld.callback(1.0, confirm)
            except Exception: pass
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _install_watcher():
    try:
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as module
        cls = getattr(module, 'StrongholdVehiclesWatcher', None)
        if cls is None: return
        for name in ('start', 'stop'):
            if name in cls.__dict__ and callable(cls.__dict__[name]) and not getattr(cls.__dict__[name], MARK + 'wrapped', False):
                setattr(cls, name, _watcher_hook(name, cls.__dict__[name]))
    except Exception: pass

def _install():
    count = 0
    try: module = __import__(CONVERTER_MODULE, fromlist=['*'])
    except Exception as error: _log('converter import failed: ' + _text(error)); return
    for name in (PRIMARY,) + SUPPORTING:
        try:
            original = getattr(module, name, None)
            if callable(original) and not getattr(original, MARK + 'wrapped', False):
                setattr(module, name, _primary_hook(original) if name == PRIMARY else _support_hook(name, original)); count += 1
        except Exception as error: _log('converter hook skipped: %s (%s)' % (name, _text(error)))
    _install_watcher(); _log('roster converter hooks installed: ' + str(count))

def init(): _log('loaded'); _install()
def fini(): _clear('mod unloaded'); _log('unloaded')
