"""Prototype 3O: read-only Skirmish detachment-exit lifecycle validation."""
import re
import time

TAG = '[shotcaller]'; MARK = '_shotcaller_3o_'
CONVERTER_MODULE = 'gui.Scaleform.daapi.view.lobby.rally.vo_converters'
PRIMARY = 'makeSlotsVOs'; SUPPORTING = ('makePlayerVO', 'makeVehicleVO', 'makeVehicleBasicVO')
SENSITIVE = re.compile(r"(?i)(access_token|token2?|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
CACHE = {'rows': {}, 'order': [], 'unit_id': None, 'tier': None, 'last_update': None, 'generation': 0}
VOLUNTEERS = {}; EMPTY_SNAPSHOTS = 0
_stronghold_watcher_active = False
_stronghold_watcher_generation = 0
_pending_exit_token = None
_populated_generation = 0
WATCHER_ORIGINALS = {}
WATCHER_FILTER_LOGGED = False

def _log(text): print(TAG + ' ' + text)
def _text(value, limit=500):
    try: return SENSITIVE.sub(r'\1\2***MASKED***', str(value)[:limit])
    except Exception: return '<unavailable>'
def _copy(value): return dict(value) if isinstance(value, dict) else None
def _get(data, key, default=None):
    try: return data[key] if key in data else default
    except Exception: return default
def _int(value):
    try: return int(value)
    except Exception: return None
def _vehicle(row): return row.get('vehicle_name') or row.get('vehicle_short_name') or row.get('vehicle_internal_name') or 'None'

def get_roster_snapshot(): return [_copy(CACHE['rows'][key]) for key in CACHE['order'] if key in CACHE['rows']]
def get_roster_member(dbid): return _copy(CACHE['rows'].get(dbid))
def get_current_tier(): return CACHE['tier']
def get_current_unit_id(): return CACHE['unit_id']
def get_roster_generation(): return CACHE['generation']
def get_volunteer_snapshot(): return [_copy(row) for row in VOLUNTEERS.values()]
def is_stronghold_context_active(): return bool(_stronghold_watcher_active or (CACHE['rows'] and _pending_exit_token is None))
def get_lifecycle_snapshot():
    return {'watcher_active': bool(_stronghold_watcher_active), 'watcher_generation': _stronghold_watcher_generation,
            'pending_exit': _pending_exit_token is not None, 'roster_populated': bool(CACHE['rows']),
            'tier': CACHE['tier'], 'unit_id': CACHE['unit_id'], 'roster_generation': CACHE['generation']}

def _normalize(slot, index):
    player = _get(slot, 'player', {})
    if not isinstance(player, dict) or not player or _get(player, 'dbID') is None: return None
    vehicle = _get(slot, 'selectedVehicle', {})
    if not isinstance(vehicle, dict): vehicle = {}
    frozen = _get(slot, 'isFreezed'); status = _get(slot, 'playerStatus')
    return {'slot_index': index, 'unit_id': _get(slot, 'rallyIdx'), 'dbid': _get(player, 'dbID'),
            'account_id': _get(player, 'accID'), 'name': _get(player, 'userName'), 'full_name': _get(player, 'fullName'),
            'clan': _get(player, 'clanAbbrev'), 'rating': _get(player, 'rating'), 'player_ready': _get(player, 'readyState'),
            'vehicle_ready': _get(vehicle, 'isReadyToFight'), 'player_status': status, 'is_frozen': frozen,
            'is_in_battle': _get(slot, 'isInBattle', _get(player, 'isInBattle')),
            'in_battle': bool(frozen or status == 3), 'commander': _get(player, 'isCommander'),
            'offline': _get(player, 'isOffline'), 'role': _get(slot, 'role'), 'is_legionnaire': _get(slot, 'isLegionaries'),
            'is_current_user': _get(slot, 'isCurrentUserInSlot'), 'vehicle_intcd': _get(vehicle, 'intCD'),
            'vehicle_name': _get(vehicle, 'userName'), 'vehicle_short_name': _get(vehicle, 'shortUserName'),
            'vehicle_internal_name': _get(vehicle, 'name'), 'vehicle_level': _int(_get(vehicle, 'level', _get(slot, 'selectedVehicleLevel'))),
            'vehicle_type': _get(vehicle, 'type'), 'vehicle_nation_id': _get(vehicle, 'nationID')}

def _print_initial(row):
    _log('state validation: name=%s player_ready=%s vehicle_ready=%s player_status=%s frozen=%s' %
         (row['name'], row['player_ready'], row['vehicle_ready'], row['player_status'], row['is_frozen']))
    _log('roster member: slot=%s dbID=%s name=%s clan=%s rating=%s vehicle=%s intCD=%s tier=%s player_ready=%s commander=%s legionnaire=%s in_battle=%s' %
         (row['slot_index'], row['dbid'], row['name'], row['clan'], row['rating'], _vehicle(row), row['vehicle_intcd'], row['vehicle_level'], row['player_ready'], row['commander'], row['is_legionnaire'], row['in_battle']))

def clear_roster_cache(reason):
    """Central idempotent clear for exit, empty fallback, unit transition, unload."""
    global EMPTY_SNAPSHOTS, _pending_exit_token
    if not CACHE['rows'] and not VOLUNTEERS:
        EMPTY_SNAPSHOTS = 0; _pending_exit_token = None; return False
    CACHE['rows'] = {}; CACHE['order'] = []; CACHE['unit_id'] = None; CACHE['tier'] = None; CACHE['last_update'] = None
    VOLUNTEERS.clear(); EMPTY_SNAPSHOTS = 0; _pending_exit_token = None; CACHE['generation'] += 1
    _log('roster cache cleared: reason=' + reason)
    if reason == 'Stronghold watcher stopped': _log('lifecycle validation passed: detachment exit cleared cache')
    return True

def _cancel_pending_exit(reason):
    global _pending_exit_token
    if _pending_exit_token is not None:
        _pending_exit_token = None
        _log('Stronghold exit clear cancelled: reason=' + reason)
        if reason == 'watcher restarted': _log('lifecycle validation passed: transient watcher stop ignored')

def _remove_volunteer(dbid):
    row = VOLUNTEERS.pop(dbid, None)
    if row: _log('volunteer removed: dbID=%s name=%s' % (dbid, row['name']))

def _apply(rows):
    global EMPTY_SNAPSHOTS, _populated_generation
    if not rows:
        if CACHE['rows']:
            EMPTY_SNAPSHOTS += 1; _log('roster empty confirmation pending: %s/2' % EMPTY_SNAPSHOTS)
            if EMPTY_SNAPSHOTS >= 2: clear_roster_cache('two consecutive empty snapshots')
        return
    EMPTY_SNAPSHOTS = 0; _populated_generation += 1
    if _pending_exit_token is not None:
        _cancel_pending_exit('roster update')
        _log('lifecycle validation passed: transient watcher stop ignored')
    new = {}; order = []
    for row in rows: new[row['dbid']] = row; order.append(row['dbid'])
    unit_id = next((row['unit_id'] for row in rows if row['unit_id'] is not None), None)
    tier = next((row['vehicle_level'] for row in rows if row['vehicle_level'] in (6, 8, 10)), None)
    if CACHE['unit_id'] is not None and unit_id is not None and CACHE['unit_id'] != unit_id:
        clear_roster_cache('unit changed old=%s new=%s' % (CACHE['unit_id'], unit_id))
    old = CACHE['rows']
    changed = old != new or CACHE['order'] != order or CACHE['tier'] != tier or CACHE['unit_id'] != unit_id
    if not changed: return
    first = not old
    for dbid, row in new.items():
        _remove_volunteer(dbid); previous = old.get(dbid)
        if previous is None: _log('roster member added: dbID=%s name=%s vehicle=%s' % (dbid, row['name'], _vehicle(row)))
        else:
            if any(previous[key] != row[key] for key in ('vehicle_intcd','vehicle_name','vehicle_level')): _log('roster vehicle changed: name=%s old=%s new=%s' % (row['name'], _vehicle(previous), _vehicle(row)))
            if previous['player_ready'] != row['player_ready']: _log('roster player ready changed: name=%s old=%s new=%s' % (row['name'], previous['player_ready'], row['player_ready']))
            if previous['vehicle_ready'] != row['vehicle_ready']: _log('roster vehicle ready changed: name=%s old=%s new=%s' % (row['name'], previous['vehicle_ready'], row['vehicle_ready']))
            if previous['slot_index'] != row['slot_index']: _log('roster slot changed: name=%s old=%s new=%s' % (row['name'], previous['slot_index'], row['slot_index']))
            if previous['commander'] != row['commander']: _log('roster commander changed: name=%s old=%s new=%s' % (row['name'], previous['commander'], row['commander']))
            if previous['player_status'] != row['player_status']: _log('roster player status changed: name=%s old=%s new=%s' % (row['name'], previous['player_status'], row['player_status']))
            if previous['is_frozen'] != row['is_frozen']: _log('roster frozen changed: name=%s old=%s new=%s' % (row['name'], previous['is_frozen'], row['is_frozen']))
            if previous['in_battle'] != row['in_battle']: _log('roster battle state changed: name=%s old=%s new=%s' % (row['name'], previous['in_battle'], row['in_battle']))
    for dbid, row in old.items():
        if dbid not in new: _log('roster member removed: dbID=%s name=%s' % (dbid, row['name']))
    CACHE['rows'] = new; CACHE['order'] = order; CACHE['unit_id'] = unit_id; CACHE['tier'] = tier; CACHE['last_update'] = time.time(); CACHE['generation'] += 1
    if tier is not None: _log('skirmish tier detected: ' + str(tier))
    if first:
        _log('roster cache populated: members=%s tier=%s unit_id=%s' % (len(rows), tier, unit_id))
        for row in rows: _print_initial(row)
    else: _log('roster cache changed: members=%s tier=%s generation=%s' % (len(rows), tier, CACHE['generation']))

def _extract(result):
    if not isinstance(result, (tuple, list)) or len(result) < 2 or not isinstance(result[1], (tuple, list)): raise ValueError('makeSlotsVOs result is not (boolean, slot list)')
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
            value = getattr(info, name); return value() if callable(value) and name.startswith('get') else value
        except Exception: pass
    return None
def _support_hook(name, original):
    def hook(*args, **kwargs):
        result = original(*args, **kwargs)
        try:
            if name == 'makePlayerVO':
                info = next((value for value in args if hasattr(value, 'isInSlot')), None)
                if info is not None and info.isInSlot() is False:
                    dbid = _info_value(info, ('dbID','getDbID'))
                    if dbid is not None and dbid not in CACHE['rows'] and dbid not in VOLUNTEERS:
                        data = result if isinstance(result, dict) else {}
                        row = {'dbid': dbid, 'name': _get(data, 'userName', _info_value(info, ('name','getName'))), 'clan': _get(data, 'clanAbbrev', _info_value(info, ('clanAbbrev','getClanAbbrev')))}
                        VOLUNTEERS[dbid] = row; _log('volunteer added: dbID=%s name=%s clan=%s' % (dbid, row['name'], row['clan']))
        except Exception: pass
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _is_stronghold_watcher(instance):
    try:
        from gui.prb_control.entities.stronghold.unit.vehicles_watcher import StrongholdVehiclesWatcher
        return isinstance(instance, StrongholdVehiclesWatcher)
    except Exception:
        try:
            cls = instance.__class__
            return cls.__module__ == 'gui.prb_control.entities.stronghold.unit.vehicles_watcher' and cls.__name__ == 'StrongholdVehiclesWatcher'
        except Exception: return False

def _watcher_hook(name, original):
    def hook(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        if not _is_stronghold_watcher(self): return result
        global _stronghold_watcher_active, _stronghold_watcher_generation, _pending_exit_token
        global WATCHER_FILTER_LOGGED
        if not WATCHER_FILTER_LOGGED:
            WATCHER_FILTER_LOGGED = True; _log('watcher filter confirmed: class=StrongholdVehiclesWatcher')
        _stronghold_watcher_generation += 1
        if name == 'start':
            _stronghold_watcher_active = True; _cancel_pending_exit('watcher restarted')
            _log('Stronghold watcher started: generation=' + str(_stronghold_watcher_generation))
        else:
            _stronghold_watcher_active = False; _pending_exit_token = _stronghold_watcher_generation
            token = _pending_exit_token; population = _populated_generation
            _log('Stronghold watcher stopped: generation=' + str(_stronghold_watcher_generation)); _log('Stronghold exit clear scheduled: token=' + str(token))
            def confirm():
                if (_pending_exit_token == token and not _stronghold_watcher_active and _stronghold_watcher_generation == token and _populated_generation == population and CACHE['rows']):
                    clear_roster_cache('Stronghold watcher stopped')
            try:
                import BigWorld; BigWorld.callback(1.0, confirm)
            except Exception: pass
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _origin(cls, name):
    for base in getattr(cls, '__mro__', (cls,)):
        if name in base.__dict__: return base.__module__ + '.' + base.__name__
    return '<missing>'

def _install_watcher():
    try:
        import gui.prb_control.entities.base.pre_queue.vehicles_watcher as base_module
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as stronghold_module
        base_cls = getattr(base_module, 'BaseVehiclesWatcher', None)
        cls = getattr(stronghold_module, 'StrongholdVehiclesWatcher', None)
        if base_cls is None or cls is None: return
        _log('watcher method origin: start=' + _origin(cls, 'start'))
        _log('watcher method origin: stop=' + _origin(cls, 'stop'))
        installed = 0
        for name in ('start','stop'):
            if name not in base_cls.__dict__ or not callable(base_cls.__dict__[name]):
                _log('watcher lifecycle hook missing: ' + name); continue
            original = base_cls.__dict__[name]
            if getattr(original, MARK + 'wrapped', False):
                installed += 1; continue
            WATCHER_ORIGINALS[name] = original
            setattr(base_cls, name, _watcher_hook(name, original)); installed += 1
        _log('watcher lifecycle hooks installed: ' + str(installed))
    except Exception as error:
        _log('watcher lifecycle hook missing: import (' + _text(error, 200) + ')')

def _install():
    count = 0
    try: module = __import__(CONVERTER_MODULE, fromlist=['*'])
    except Exception as error: _log('converter import failed: ' + _text(error)); return
    for name in (PRIMARY,) + SUPPORTING:
        try:
            original = getattr(module, name, None)
            if callable(original) and not getattr(original, MARK + 'wrapped', False): setattr(module, name, _primary_hook(original) if name == PRIMARY else _support_hook(name, original)); count += 1
        except Exception as error: _log('converter hook skipped: %s (%s)' % (name, _text(error)))
    _install_watcher(); _log('roster converter hooks installed: ' + str(count))
def init(): _log('loaded'); _install()
def fini(): clear_roster_cache('mod unloaded'); _log('unloaded')
