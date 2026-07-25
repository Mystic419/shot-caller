"""Prototype 5A-repair: safe generic vehicle-selection refresh."""
import cgi
import codecs
import json
import os
import re
import socket
import time
import traceback
import urllib
import urllib2

TAG = '[shotcaller]'; MARK = '_shotcaller_5b_selection_'
CONVERTER_MODULE = 'gui.Scaleform.daapi.view.lobby.rally.vo_converters'
PRIMARY = 'makeSlotsVOs'; SUPPORTING = ('makePlayerVO', 'makeVehicleVO', 'makeVehicleBasicVO')
SENSITIVE = re.compile(r"(?i)(access_token|token2?|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
ROOM_CONTEXT_NONE = 'none'
ROOM_CONTEXT_STRONGHOLD = 'stronghold'
ROOM_CONTEXT_PLATOON = 'platoon'
CACHE = {'rows': {}, 'order': [], 'unit_id': None, 'tier': None, 'resolved_tier': None, 'tier_reason': None, 'last_update': None, 'generation': 0}
ROOM_CONTEXT = ROOM_CONTEXT_NONE
HISTORY_STATE_READY = 'ready'
HISTORY_STATE_LOADING = 'loading'
HISTORY_STATE_UNSUPPORTED_TIER = 'unsupported_tier'
HISTORY_STATE_MIXED_TIER = 'mixed_tier'
HISTORY_STATE_INCOMPLETE = 'incomplete'
HISTORY_STATE_EMPTY_ROSTER = 'empty_roster'
VOLUNTEERS = {}; EMPTY_SNAPSHOTS = 0
_stronghold_watcher_active = False
_stronghold_watcher_generation = 0
_pending_exit_token = None
_populated_generation = 0
WATCHER_ORIGINALS = {}
VEHICLE_VIEW_ORIGINALS = {}
PLATOON_ENTITY_ORIGINALS = {}
PLATOON_REBUILD_TOKEN = 0
ROW_FIELD_SOURCES = {}
PLATOON_MERGE_LOGGED = set()
WATCHER_FILTER_LOGGED = False
LOOKUP_TRANSPORT = 'native'
# The 0.0.60 development builder injects a project public WG application ID
# into temporary compilation source. The repository never contains its value.
NATIVE_WG_APP_ID = None
NATIVE_REALMS = {'NA': 'https://api.worldoftanks.com', 'EU': 'https://api.worldoftanks.eu', 'ASIA': 'https://api.worldoftanks.asia'}
NATIVE_DEFAULT_REALM = 'NA'
NATIVE_CACHE_TTL = 6 * 60 * 60
NATIVE_MAX_BATCH_ACCOUNTS = 15
NATIVE_CACHE_DIR = os.path.join('mods', 'configs', 'shotcaller', 'cache')
NATIVE_CACHE_SCHEMA = 1
NATIVE_REQUEST_SERIAL = 0
NATIVE_ACTIVE_REQUESTS = {}
NATIVE_INFLIGHT_BATCHES = set()
NATIVE_TANKOPEDIA = {}
NATIVE_TANKOPEDIA_REALM = None
NATIVE_TANKOPEDIA_HANDLE = None
LOOKUPS = {}
LOOKUP_STATUS = {'lookup_state': 'idle', 'last_attempt_generation': None, 'inflight': False, 'pending': False, 'transport': 'native'}
HOVER_ACTIVE = None
PANEL = {'open': False, 'dbid': None, 'slot': None, 'generation': None,
         'fingerprint': None, 'suppressed_logged': False, 'opening': False}
KEY_HANDLER_INSTALLED = False
USE_CUSTOM_VEHICLE_WINDOW = True
SHOTCALLER_VEHICLE_WINDOW_ALIAS = 'shotcallerVehicleWindow'
CUSTOM_WINDOW_NAME = 'shotcallerVehicleWindow'
CUSTOM_WINDOW_REGISTERED = False
CUSTOM_WINDOW_VIEW = None
CUSTOM_WINDOW_PENDING = None
CUSTOM_WINDOW_FALLBACK_QUEUED = False
SHOTCALLER_FILTER_WINDOW_ALIAS = 'shotcallerVehicleFilters'
FILTER_WINDOW_NAME = 'shotcallerVehicleFilters'
FILTER_WINDOW_REGISTERED = False
FILTER_WINDOW_VIEW = None
FILTER_WINDOW_PENDING = None
DEFAULT_FILTERS = {'schema_version': 1, 'hidden_vehicle_ids': {'6': [], '8': [], '10': []}}
FILTERS = {'schema_version': 1, 'hidden_vehicle_ids': {'6': set(), '8': set(), '10': set()}}
FILTER_PATH = os.path.join('mods', 'configs', 'shotcaller', 'vehicle_filters.json')
VEHICLE_CATALOG = None
VEHICLE_CATALOG_AVAILABLE = False
VEHICLE_CATALOG_ERROR = None
VEHICLE_CATALOG_SKIPPED = {}
PANEL['position'] = None

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

PANEL_NAME = 'shotcallerVehiclePanel'
PANEL_ALIAS = 'buttonDialog'
PANEL_TYPES = (('heavyTank', 'Heavy'), ('mediumTank', 'Medium'), ('lightTank', 'Light'), ('AT-SPG', 'Tank Destroyer'), ('SPG', 'SPG'))
PANEL_BUTTONS = ({'id': 'previous', 'label': 'Previous', 'focused': False},
                 {'id': 'next', 'label': 'Next', 'focused': True},
                 {'id': 'close', 'label': 'Close', 'focused': False})

def _html(value):
    try: return cgi.escape(unicode(value or ''), quote=True)
    except Exception: return ''

def _filter_counts(): return dict((tier, len(FILTERS['hidden_vehicle_ids'][tier])) for tier in ('6', '8', '10'))

def _reset_filters():
    FILTERS['schema_version'] = 1
    FILTERS['hidden_vehicle_ids'] = {'6': set(), '8': set(), '10': set()}

def _normalise_filter_data(value):
    output = {'schema_version': 1, 'hidden_vehicle_ids': {'6': set(), '8': set(), '10': set()}}
    if not isinstance(value, dict) or value.get('schema_version') != 1: return output, False
    hidden = value.get('hidden_vehicle_ids')
    if not isinstance(hidden, dict): return output, False
    for tier in ('6', '8', '10'):
        raw = hidden.get(tier, [])
        if not isinstance(raw, (list, tuple)): continue
        for item in raw:
            number = _int(item)
            if number is not None and number > 0: output['hidden_vehicle_ids'][tier].add(number)
    return output, True

def _load_filter_config():
    _reset_filters(); _log('filter config path: ' + FILTER_PATH)
    if not os.path.isfile(FILTER_PATH):
        _log('filter config missing; defaults used'); return
    try:
        stream = codecs.open(FILTER_PATH, 'r', 'utf-8')
        data = json.load(stream); stream.close()
        normalized, valid = _normalise_filter_data(data)
        if not valid: raise ValueError('schema')
        FILTERS.update(normalized)
        _log('filter config loaded: hidden=%s' % _filter_counts())
    except Exception:
        _reset_filters(); _log('filter config malformed; defaults used')

def _save_filter_config():
    directory = os.path.dirname(FILTER_PATH)
    temporary = FILTER_PATH + '.tmp'
    try:
        if not os.path.isdir(directory): os.makedirs(directory)
        data = {'schema_version': 1, 'hidden_vehicle_ids': dict((tier, sorted(FILTERS['hidden_vehicle_ids'][tier])) for tier in ('6', '8', '10'))}
        stream = codecs.open(temporary, 'w', 'utf-8'); json.dump(data, stream, sort_keys=True, indent=2); stream.flush()
        try: os.fsync(stream.fileno())
        except Exception: pass
        stream.close()
        try: os.rename(temporary, FILTER_PATH)
        except OSError:
            if os.path.isfile(FILTER_PATH): os.remove(FILTER_PATH)
            os.rename(temporary, FILTER_PATH)
        _log('filter config saved: hidden=%s' % _filter_counts()); return True
    except Exception as error:
        try:
            if os.path.isfile(temporary): os.remove(temporary)
        except Exception: pass
        _log('filter config save failed: ' + type(error).__name__); return False

def _vehicle_id(vehicle):
    if not isinstance(vehicle, dict): return None
    return _int(vehicle.get('tank_id', vehicle.get('intCD')))

def _battles(vehicle):
    try: return max(0, int(vehicle.get('battles', 0))) if isinstance(vehicle, dict) else 0
    except Exception: return 0

def _filtered_vehicles(result):
    vehicles = result.get('vehicles', []) if isinstance(result, dict) else []
    tier = str(CACHE['tier'])
    hidden = FILTERS['hidden_vehicle_ids'].get(tier, set())
    visible = []; stale = 0
    for vehicle in vehicles:
        vehicle_id = _vehicle_id(vehicle)
        if vehicle_id in hidden: continue
        visible.append(vehicle)
    if len(visible) != len(vehicles): _log('vehicles filtered from displayed result: tier=%s count=%s' % (tier, len(vehicles) - len(visible)))
    if hidden and not vehicles: stale = len(hidden)
    if stale: _log('filter unknown/stale vehicle IDs ignored: tier=%s count=%s' % (tier, stale))
    return visible, len(vehicles)

def _log_history_filters_reapplied():
    if not PANEL.get('open') or PANEL.get('dbid') not in LOOKUPS: return
    result = LOOKUPS.get(PANEL.get('dbid'))
    vehicles = result.get('vehicles', []) if isinstance(result, dict) else []
    visible, total = _filtered_vehicles(result)
    _log('history filters reapplied: total=%s hiddenMatches=%s visible=%s' % (total, total - len(visible), len(visible)))

def _catalog_vehicle_id(item, fallback=None):
    """Return the client compact descriptor, never a player-history identifier."""
    for name in ('compactDescr', 'intCD', 'compactDescriptor'):
        value = _int(getattr(item, name, None))
        if value is not None and value > 0: return value
    value = _int(fallback)
    return value if value is not None and value > 0 else None

def _catalog_skip(reason):
    VEHICLE_CATALOG_SKIPPED[reason] = VEHICLE_CATALOG_SKIPPED.get(reason, 0) + 1

def _catalog_class(vehicle_type, vehicles_module):
    """Use the client resolver; VehicleItem wrappers intentionally have no class."""
    value = vehicles_module.getVehicleClassFromVehicleType(vehicle_type)
    value = unicode(value or '')
    return value if value in ('heavyTank', 'mediumTank', 'lightTank', 'AT-SPG', 'SPG') else None

def _catalog_name(item):
    return (getattr(item, 'shortUserName', None) or getattr(item, 'userString', None) or
            getattr(item, 'userName', None) or getattr(item, 'name', None))

def _build_vehicle_catalog():
    """Use the 2.3.1 client pattern: getList(nationID).itervalues()."""
    global VEHICLE_CATALOG, VEHICLE_CATALOG_AVAILABLE, VEHICLE_CATALOG_ERROR, VEHICLE_CATALOG_SKIPPED
    if isinstance(VEHICLE_CATALOG, dict):
        _log('vehicle catalog cache reused')
        return VEHICLE_CATALOG
    VEHICLE_CATALOG_SKIPPED = {}
    catalog_by_id = {'6': {}, '8': {}, '10': {}}
    sample_classes = set()
    processed = 0; supported_tier = 0; added = 0
    try:
        from items import nations, vehicles
        getter = vehicles.g_list.getList
        _log('catalog source=items.vehicles.g_list.getList(nationID).itervalues')
        _log('catalog getList callable=%s attempted_args=nationID' % _text(getter, 160))
        for nation_id in nations.INDICES.itervalues():
            returned = getter(nation_id)
            _log('catalog getList returned: nation=%s type=%s' % (nation_id, type(returned).__name__))
            if not hasattr(returned, 'itervalues'):
                raise TypeError('getList(nationID) returned %s without itervalues' % type(returned).__name__)
            iterator = returned.itervalues()
            first = True
            for item in iterator:
                processed += 1
                if first:
                    _log('catalog first item: type=%s repr=%s' % (type(item).__name__, _text(item, 160)))
                    _log('catalog first item fields: compactDescr=%s intCD=%s level=%s type=%s typeName=%s userString=%s' %
                         (_text(getattr(item, 'compactDescr', None), 80), _text(getattr(item, 'intCD', None), 80),
                          _text(getattr(item, 'level', None), 80), _text(getattr(item, 'type', None), 80),
                          _text(getattr(item, 'typeName', None), 80), _text(getattr(item, 'userString', None), 80)))
                    first = False
                tier = _int(getattr(item, 'level', None))
                if tier not in (6, 8, 10): _catalog_skip('tier'); continue
                supported_tier += 1
                if getattr(item, 'isHidden', False) or getattr(item, 'isInternal', False): _catalog_skip('internal'); continue
                vehicle_id = _catalog_vehicle_id(item)
                if vehicle_id is None: _catalog_skip('missing_id'); continue
                name = _catalog_name(item)
                if not name: _catalog_skip('missing_name'); continue
                try:
                    vehicle_type = vehicles.getVehicleType(vehicle_id)
                    kind = _catalog_class(vehicle_type, vehicles)
                except Exception:
                    _catalog_skip('descriptor_failure'); continue
                if kind is None: _catalog_skip('unsupported_class'); continue
                if vehicle_id in catalog_by_id[str(tier)]:
                    _catalog_skip('duplicate'); continue
                catalog_by_id[str(tier)][vehicle_id] = {'id': vehicle_id, 'name': unicode(name), 'tier': tier, 'type': kind}
                added += 1
                if kind not in sample_classes and len(sample_classes) < 5:
                    sample_classes.add(kind)
                    _log('catalog resolved sample: name=%s intCD=%s descriptor=%s tags=%s class=%s' %
                         (_text(name, 80), vehicle_id, type(vehicle_type).__name__, _text(getattr(vehicle_type, 'tags', None), 180), kind))
        completed_catalog = {'6': [], '8': [], '10': []}
        for tier in ('6', '8', '10'):
            completed_catalog[tier] = sorted(catalog_by_id[tier].values(), key=lambda item: item['name'].lower())
            _log('catalog tier %s count=%s' % (tier, len(completed_catalog[tier])))
            names = [item['name'] for item in completed_catalog[tier]]
            _log('catalog audit tier=%s first5=%s last5=%s' % (tier, _text(', '.join(names[:5]), 400), _text(', '.join(names[-5:]), 400)))
        if supported_tier and VEHICLE_CATALOG_SKIPPED.get('descriptor_failure', 0) * 2 > supported_tier:
            raise RuntimeError('most supported-tier entries failed descriptor resolution')
        if not any(completed_catalog.values()): raise RuntimeError('all supported tier catalogs are empty')
        VEHICLE_CATALOG = completed_catalog
        VEHICLE_CATALOG_AVAILABLE = True
        _log('catalog processed=%s added=%s skipped_tier=%s skipped_descriptor_failure=%s skipped_unknown_class=%s skipped_invalid_id=%s skipped_missing_name=%s duplicates_removed=%s' %
             (processed, added, VEHICLE_CATALOG_SKIPPED.get('tier', 0), VEHICLE_CATALOG_SKIPPED.get('descriptor_failure', 0),
              VEHICLE_CATALOG_SKIPPED.get('unsupported_class', 0), VEHICLE_CATALOG_SKIPPED.get('missing_id', 0),
              VEHICLE_CATALOG_SKIPPED.get('missing_name', 0), VEHICLE_CATALOG_SKIPPED.get('duplicate', 0)))
        tier_eight = VEHICLE_CATALOG['8']
        counts = dict((key, len([item for item in tier_eight if item['type'] == key])) for key in ('heavyTank','mediumTank','lightTank','AT-SPG','SPG'))
        _log('catalog class counts tier=8 heavy=%s medium=%s light=%s td=%s spg=%s' % (counts['heavyTank'], counts['mediumTank'], counts['lightTank'], counts['AT-SPG'], counts['SPG']))
        _log('complete vehicle catalog built')
    except Exception as error:
        VEHICLE_CATALOG_ERROR = '%s: %s' % (type(error).__name__, _text(error, 240))
        _log('complete vehicle catalog failed: type=%s message=%s' % (type(error).__name__, _text(error, 240)))
        _log('complete vehicle catalog traceback: ' + _text(traceback.format_exc(), 1200))
        _log('complete vehicle catalog unavailable')
        VEHICLE_CATALOG = None
        VEHICLE_CATALOG_AVAILABLE = False
    return VEHICLE_CATALOG

def get_vehicle_catalog_audit():
    """Read-only Python 2.7 audit helper; runs against the live client definitions."""
    catalog = _build_vehicle_catalog() or {'6': [], '8': [], '10': []}
    report = {'available': VEHICLE_CATALOG_AVAILABLE, 'error': VEHICLE_CATALOG_ERROR,
              'skipped': dict(VEHICLE_CATALOG_SKIPPED), 'tiers': {}}
    for tier in ('6', '8', '10'):
        rows = list(catalog.get(tier, []))
        report['tiers'][tier] = {'count': len(rows), 'duplicates': len(rows) - len(set(row['id'] for row in rows)),
                                 'class_counts': dict((kind, len([row for row in rows if row['type'] == kind])) for kind in ('heavyTank','mediumTank','lightTank','AT-SPG','SPG')),
                                 'first_five': [row['name'] for row in rows[:5]], 'last_five': [row['name'] for row in rows[-5:]]}
    return report

def _known_vehicles(tier):
    return list((_build_vehicle_catalog() or {}).get(str(tier), []))

def _lobby_app():
    from helpers import dependency
    from skeletons.gui.app_loader import IAppLoader
    loader = dependency.instance(IAppLoader)
    return loader.getDefLobbyApp() or loader.getApp()

def _panel_state(row):
    classified = _classify_history_state(CACHE['rows'].values())
    if classified == HISTORY_STATE_UNSUPPORTED_TIER: return HISTORY_STATE_UNSUPPORTED_TIER, None
    if classified in (HISTORY_STATE_MIXED_TIER, HISTORY_STATE_INCOMPLETE, HISTORY_STATE_EMPTY_ROSTER): return classified, None
    result = LOOKUPS.get(row['dbid'])
    if result is not None:
        status = result.get('status')
        if status in ('ok', 'no_vehicle_history'): return 'ready', result
        return 'error', result
    if LOOKUP_STATUS['inflight'] or LOOKUP_STATUS['pending'] or LOOKUP_STATUS['lookup_state'] in ('queued', 'running'):
        return 'pending', None
    if LOOKUP_STATUS['lookup_state'] in ('error', 'timeout'):
        return 'error', None
    return 'missing', None

def _classify_history_state(rows):
    rows = list(rows or [])
    if not rows: return HISTORY_STATE_EMPTY_ROSTER
    levels = []
    for row in rows:
        if not row.get('vehicle_intcd') or row.get('vehicle_level') is None: return HISTORY_STATE_INCOMPLETE
        levels.append(row['vehicle_level'])
    if len(set(levels)) != 1: return HISTORY_STATE_MIXED_TIER
    if levels[0] not in (6, 8, 10): return HISTORY_STATE_UNSUPPORTED_TIER
    if LOOKUP_STATUS['inflight'] or LOOKUP_STATUS['pending'] or LOOKUP_STATUS['lookup_state'] in ('queued', 'running'): return HISTORY_STATE_LOADING
    return HISTORY_STATE_READY

def _tier_label(value):
    return {2: 'II', 5: 'V', 6: 'VI', 8: 'VIII', 10: 'X'}.get(value, str(value))

def _display_player_name(row):
    name = unicode(row.get('full_name') or row.get('name') or '')
    clan = unicode(row.get('clan') or '').strip()
    if clan:
        tag = '[%s]' % clan
        name = re.sub(r'(?:\s*' + re.escape(tag) + r')+', '', name, flags=re.IGNORECASE).strip()
        name += ' ' + tag
    return name.strip()

def _panel_rows():
    return [CACHE['rows'][dbid] for dbid in CACHE['order'] if dbid in CACHE['rows']]

def _panel_position(row):
    rows = _panel_rows()
    for index, item in enumerate(rows):
        if item['dbid'] == row['dbid']: return index + 1, len(rows)
    return 0, len(rows)

def _panel_fingerprint(row, state, result):
    vehicles = result.get('vehicles', []) if isinstance(result, dict) else []
    normalized = []
    for vehicle in vehicles:
        if isinstance(vehicle, dict): normalized.append((vehicle.get('type'), vehicle.get('name'), vehicle.get('tank_id')))
    current, total = _panel_position(row)
    return (row['dbid'], row['slot_index'], CACHE['tier'], current, total, _display_player_name(row), state, tuple(sorted(normalized)))

def _panel_message(row, state, result):
    tier = CACHE['tier']
    current, total = _panel_position(row)
    title = '<font size="16"><b>Shotcaller vehicle history</b></font><br/>' if tier not in (6, 8, 10) else '<font size="16"><b>Public vehicle history for Tier %s</b></font><br/>' % tier
    player = '<b>%s</b>' % _html(_display_player_name(row))
    indicator = 'Player %s of %s' % (current, total)
    subtitle = 'Skirmish roster' if ROOM_CONTEXT == ROOM_CONTEXT_STRONGHOLD else ('Platoon roster' if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON else '')
    message = title + (subtitle + '<br/>' if subtitle else '') + player + '<br/>' + indicator + '<br/>Lookup state: <b>%s</b><br/>' % _html(state)
    if state in (HISTORY_STATE_UNSUPPORTED_TIER, HISTORY_STATE_MIXED_TIER, HISTORY_STATE_INCOMPLETE, HISTORY_STATE_EMPTY_ROSTER):
        if CACHE.get('tier_reason') == 'unsupported' and CACHE.get('resolved_tier') is not None:
            return message + 'Tier %s is not supported.<br/>ShotCaller currently supports Tiers VI, VIII, and X.' % _tier_label(CACHE['resolved_tier'])
        guidance = 'No friendly roster is available.' if state == HISTORY_STATE_EMPTY_ROSTER else ('Platoon members must select matching Tier VI, VIII, or X vehicles.' if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON else 'Select a Tier VI, VIII, or X vehicle.')
        return message + guidance
    if state == 'pending':
        return message + 'Vehicles shown: <b>0</b><br/>Loading vehicle history...'
    if state == 'missing':
        return message + 'Vehicles shown: <b>0</b><br/>Vehicle history is not available yet.'
    if state == 'error':
        return message + 'Vehicles shown: <b>0</b><br/>Vehicle history lookup is unavailable.'
    vehicles, total = _filtered_vehicles(result)
    message += 'Vehicles shown: <b>%s of %s</b>' % (len(vehicles), total)
    if total and not vehicles: return message + '<br/>No vehicles shown by your filters.<br/>Open Settings to change the global vehicle filters.'
    if not vehicles: return message + '<br/>No public Tier %s vehicle history found.' % tier
    grouped = dict((label, []) for _, label in PANEL_TYPES)
    for vehicle in vehicles:
        vehicle_type = vehicle.get('type', 'unknown') if isinstance(vehicle, dict) else 'unknown'
        label = next((item[1] for item in PANEL_TYPES if item[0] == vehicle_type), 'Tank Destroyer')
        grouped[label].append(_html(vehicle.get('name', 'Unknown')))
    for _, label in PANEL_TYPES:
        names = sorted(grouped[label], key=lambda value: value.lower())
        if names:
            # This separator is the fixed-header/body boundary consumed by _custom_data.
            message += '<br/><b>%s</b><br/>%s' % (label, '<br/>'.join(names))
    return message

def _destroy_panel_view():
    try:
        app = _lobby_app()
        if app is not None and app.containerManager is not None:
            app.containerManager.destroyViews(PANEL_ALIAS, PANEL_NAME)
            app.containerManager.destroyViews(SHOTCALLER_VEHICLE_WINDOW_ALIAS, CUSTOM_WINDOW_NAME)
            app.containerManager.destroyViews(SHOTCALLER_FILTER_WINDOW_ALIAS, FILTER_WINDOW_NAME)
    except Exception: pass

def _history_header(row, state, result):
    current, total = _panel_position(row)
    context = 'Skirmish roster' if ROOM_CONTEXT == ROOM_CONTEXT_STRONGHOLD else 'Platoon roster'
    text = context + '<br/><b>%s</b><br/>Player %s of %s<br/>Lookup state: <b>%s</b>' % (_html(_display_player_name(row)), current, total, _html(state))
    if state == 'ready':
        visible, count = _filtered_vehicles(result)
        text += '<br/>Vehicles shown: <b>%s of %s</b>' % (len(visible), count)
    return text

def _custom_close(reason, destroy=True):
    global CUSTOM_WINDOW_VIEW, CUSTOM_WINDOW_PENDING
    if CUSTOM_WINDOW_VIEW is not None:
        try:
            if destroy: CUSTOM_WINDOW_VIEW.destroy()
        except Exception: pass
    CUSTOM_WINDOW_VIEW = None
    CUSTOM_WINDOW_PENDING = None
    _log('custom close: reason=' + reason)

def _fallback(row, reason, refresh=False, preserve_session=False):
    global CUSTOM_WINDOW_FALLBACK_QUEUED
    _log('fallback activation reason=' + reason)
    _custom_close('fallback ' + reason)
    if CUSTOM_WINDOW_FALLBACK_QUEUED: return
    CUSTOM_WINDOW_FALLBACK_QUEUED = True
    def show():
        global CUSTOM_WINDOW_FALLBACK_QUEUED
        CUSTOM_WINDOW_FALLBACK_QUEUED = False
        _show_generic_panel(row, refresh, preserve_session)
    try:
        import BigWorld
        BigWorld.callback(0.0, show)
    except Exception:
        show()

def _show_generic_panel(row, refresh=False, preserve_session=False):
    state, result = _panel_state(row)
    from gui.Scaleform.daapi.settings.views import VIEW_ALIAS
    from gui.Scaleform.framework import ScopeTemplates
    from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
    app = _lobby_app()
    app.loadView(SFViewLoadParams(VIEW_ALIAS.BUTTON_DIALOG, name=PANEL_NAME), _panel_message(row, state, result), 'Shotcaller', list(PANEL_BUTTONS), _handle_panel_button, ScopeTemplates.VIEW_SCOPE, 0)
    PANEL['open'] = True; PANEL['dbid'] = row['dbid']; PANEL['slot'] = row['slot_index']; PANEL['generation'] = CACHE['generation']
    PANEL['fingerprint'] = _panel_fingerprint(row, state, result); PANEL['suppressed_logged'] = PANEL['suppressed_logged'] if preserve_session else False
    _log('vehicle panel %s: slot=%s dbID=%s vehicles=%s state=%s' % ('refreshed' if refresh else 'opened', row['slot_index'], row['dbid'], len(result.get('vehicles', [])) if isinstance(result, dict) else 0, state))

class ShotcallerVehicleWindowView(object):
    """Late-bound View wrapper; replaced with the client View base during registration."""
    pass

def _push_history_view_data(view, row, state, result, reason):
    flash = getattr(view, 'flashObject', None)
    if state in (HISTORY_STATE_UNSUPPORTED_TIER, HISTORY_STATE_MIXED_TIER, HISTORY_STATE_INCOMPLETE, HISTORY_STATE_EMPTY_ROSTER):
        message = getattr(flash, 'as_setMessageState', None)
        if callable(message):
            context = 'Skirmish roster' if ROOM_CONTEXT == ROOM_CONTEXT_STRONGHOLD else 'Platoon roster'
            if state == HISTORY_STATE_UNSUPPORTED_TIER and CACHE.get('resolved_tier') is not None:
                detail = 'ShotCaller currently supports Tiers VI, VIII, and X.'
                _log('unsupported tier message opened: context=%s tier=%s displayTier=%s' % (ROOM_CONTEXT, CACHE['resolved_tier'], _tier_label(CACHE['resolved_tier'])))
                title = 'Tier %s is not supported.' % _tier_label(CACHE['resolved_tier'])
            else: detail = 'No friendly roster is available.' if state == HISTORY_STATE_EMPTY_ROSTER else ('Platoon members must select matching Tier VI, VIII, or X vehicles.' if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON else 'Select a Tier VI, VIII, or X vehicle.'); title = ''
            _log('history state selected: state=%s resolvedTier=%s supportedTier=%s' % (state, CACHE.get('resolved_tier'), CACHE.get('tier')))
            message(context, title, detail); return
    header = getattr(flash, 'as_setHistoryHeader', None)
    begin = getattr(flash, 'as_beginHistoryRows', None)
    add_heading = getattr(flash, 'as_addHistoryHeading', None)
    add_vehicle = getattr(flash, 'as_addHistoryVehicle', None)
    finish = getattr(flash, 'as_finishHistoryRows', None)
    if not all(callable(method) for method in (header, begin, add_heading, add_vehicle, finish)): raise RuntimeError('structured history methods unavailable')
    header(_history_header(row, state, result)); begin()
    if state == 'ready':
        vehicles, unused = _filtered_vehicles(result)
        grouped = dict((label, []) for _, label in PANEL_TYPES)
        for vehicle in vehicles:
            label = next((item[1] for item in PANEL_TYPES if item[0] == vehicle.get('type')), 'Tank Destroyer')
            grouped[label].append(unicode(vehicle.get('name', 'Unknown')))
        for unused, label in PANEL_TYPES:
            names = sorted(grouped[label], key=lambda value: value.lower())
            if names:
                add_heading(label)
                for vehicle in sorted([item for item in vehicles if next((entry[1] for entry in PANEL_TYPES if entry[0] == item.get('type')), 'Tank Destroyer') == label], key=lambda item: unicode(item.get('name', '')).lower()): add_vehicle(unicode(vehicle.get('name', 'Unknown')), _battles(vehicle))
    finish()
    vehicles = result.get('vehicles', []) if isinstance(result, dict) else []
    visible, total = _filtered_vehicles(result) if isinstance(result, dict) else ([], 0)
    with_battles = len([vehicle for vehicle in visible if _battles(vehicle) > 0])
    _log('vehicle battles normalized: dbID=%s vehicles=%s withBattles=%s zeroBattles=%s' % (row['dbid'], total, with_battles, len(visible) - with_battles))
    _log('history rows pushed: dbID=%s tier=%s vehicles=%s battleCounts=yes' % (row['dbid'], CACHE['tier'], len(visible)))
    _log('history %s pushed: dbID=%s total=%s visible=%s hiddenMatches=%s' %
         (reason, row['dbid'], total, len(visible), total - len(visible)))

def _build_custom_view_class():
    """Create the dedicated View subclass only when Scaleform is available."""
    from gui.Scaleform.framework.entities.View import View
    class _ShotcallerVehicleWindowView(View):
        def __init__(self, ctx=None):
            try: View.__init__(self, ctx)
            except TypeError: View.__init__(self)
            _log('custom view constructed')

        def _populate(self):
            global CUSTOM_WINDOW_VIEW
            View._populate(self)
            CUSTOM_WINDOW_VIEW = self
            _log('custom view populated')
            pending = CUSTOM_WINDOW_PENDING
            if not isinstance(pending, dict):
                _custom_population_failed('missing pending data')
                return
            try:
                flash = getattr(self, 'flashObject', None)
                _push_history_view_data(self, pending['row'], pending['state'], pending['result'], 'first data')
                position = PANEL.get('position')
                position_method = getattr(flash, 'as_setPosition', None)
                if position and callable(position_method): position_method(position[0], position[1])
                _log('custom first data push: dbID=%s state=%s' % (pending['row']['dbid'], pending['state']))
            except Exception as error:
                _custom_population_failed('data push ' + type(error).__name__)

        def _dispose(self):
            global CUSTOM_WINDOW_VIEW
            if CUSTOM_WINDOW_VIEW is self: CUSTOM_WINDOW_VIEW = None
            _log('custom dispose')
            View._dispose(self)

        def onCloseS(self): _log('close callback received'); _custom_view_action('close')
        def onPreviousS(self): _log('previous callback received'); _custom_view_action('previous')
        def onNextS(self): _log('next callback received'); _custom_view_action('next')
        def onSettingsS(self):
            _log('settings callback received')
            _open_filter_window()
        def onPositionS(self, x=0, y=0):
            try: PANEL['position'] = (_int(x) or 0, _int(y) or 0)
            except Exception: pass
        def onClose(self): self.onCloseS()
        def onPrevious(self): self.onPreviousS()
        def onNext(self): self.onNextS()
        def onSettings(self): self.onSettingsS()
    return _ShotcallerVehicleWindowView

def _custom_population_failed(reason):
    pending = CUSTOM_WINDOW_PENDING
    row = pending.get('row') if isinstance(pending, dict) else None
    _log('custom population failed: reason=' + reason)
    _custom_close('population failed')
    if row is not None: _fallback(row, 'custom population ' + reason, True, True)

def _custom_view_action(action):
    if action == 'close':
        _close_panel('custom close'); return
    _handle_panel_button(action)

def _register_custom_window():
    global CUSTOM_WINDOW_REGISTERED, ShotcallerVehicleWindowView
    _log('custom feature flag: enabled=' + ('yes' if USE_CUSTOM_VEHICLE_WINDOW else 'no'))
    if not USE_CUSTOM_VEHICLE_WINDOW:
        CUSTOM_WINDOW_REGISTERED = False
        return
    try:
        from frameworks.wulf import WindowLayer
        from gui.Scaleform.framework import ViewSettings, ScopeTemplates, g_entitiesFactories
        ShotcallerVehicleWindowView = _build_custom_view_class()
        existing = g_entitiesFactories.getSettings(SHOTCALLER_VEHICLE_WINDOW_ALIAS)
        if existing is None:
            setting = ViewSettings(SHOTCALLER_VEHICLE_WINDOW_ALIAS, ShotcallerVehicleWindowView,
                                   'shotcaller/shotcallerVehicleWindow.swf', WindowLayer.OVERLAY,
                                   None, ScopeTemplates.GLOBAL_SCOPE)
            g_entitiesFactories.addSettings(setting)
        CUSTOM_WINDOW_REGISTERED = True
        _log('custom alias registration success: alias=%s swf=%s layer=OVERLAY scope=GLOBAL_SCOPE' % (SHOTCALLER_VEHICLE_WINDOW_ALIAS, 'shotcaller/shotcallerVehicleWindow.swf'))
    except Exception as error:
        CUSTOM_WINDOW_REGISTERED = False
        _log('custom alias registration failure: ' + type(error).__name__)

class ShotcallerFilterWindowView(object): pass

def _filter_payload(tier=8):
    catalog = _build_vehicle_catalog() or {'6': [], '8': [], '10': []}
    selected = catalog.get(str(tier), [])
    hidden = dict((key, sorted(FILTERS['hidden_vehicle_ids'][key])) for key in ('6', '8', '10'))
    notice = 'Checked vehicles are hidden from ShotCaller results. Hide All and Show All affect only currently displayed rows.'
    if not VEHICLE_CATALOG_AVAILABLE:
        notice = 'Vehicle catalog unavailable. See python.log for the guarded client catalog diagnostic.'
    wire_catalog = {}
    for key in ('6', '8', '10'):
        wire_catalog[key] = [{'id': int(item['id']), 'name': unicode(item['name']), 'tier': int(item['tier']),
                              'class': unicode(item['type'])} for item in catalog.get(key, [])]
    payload = {'schemaVersion': 1, 'selectedTier': int(tier), 'catalogs': wire_catalog,
               'hiddenVehicleIds': hidden, 'notice': notice, 'catalogAvailable': VEHICLE_CATALOG_AVAILABLE}
    first = selected[0] if selected else {}
    _log('initial filter payload: method=as_setData tier=%s vehicles=%s hidden=%s payload_type=str first=id=%s name=%s tier=%s class=%s' %
         (tier, len(selected), len(hidden[str(tier)]), first.get('id'), _text(first.get('name', ''), 80), first.get('tier'), first.get('type')))
    encoded = json.dumps(payload, ensure_ascii=True, separators=(',', ':'))
    _log('serialized filter payload length=%s' % len(encoded))
    return encoded

def _filter_native_data(tier=8):
    catalog = _build_vehicle_catalog() or {'6': [], '8': [], '10': []}
    hidden = dict((key, sorted(FILTERS['hidden_vehicle_ids'][key])) for key in ('6', '8', '10'))
    notice = 'Checked vehicles are hidden from ShotCaller results. Hide All and Show All affect only currently displayed rows.'
    if not VEHICLE_CATALOG_AVAILABLE:
        notice = 'Vehicle catalog unavailable. See python.log for the guarded client catalog diagnostic.'
    return {'tier': int(tier), 'catalog': catalog, 'hidden': hidden, 'notice': notice}

def _send_filter_native_data(flash, data):
    begin = getattr(flash, 'as_beginData', None)
    set_tier = getattr(flash, 'as_setTierCatalog', None)
    set_hidden = getattr(flash, 'as_setHiddenIds', None)
    finish = getattr(flash, 'as_finishData', None)
    if not (callable(begin) and callable(set_tier) and callable(set_hidden) and callable(finish)):
        raise RuntimeError('native filter DAAPI methods unavailable')
    begin(data['tier'], data['notice'])
    for key in ('6', '8', '10'):
        rows = data['catalog'].get(key, [])
        set_tier(int(key), [int(row['id']) for row in rows], [unicode(row['name']) for row in rows], [unicode(row['type']) for row in rows])
        set_hidden(int(key), list(data['hidden'][key]))
    finish()
    _log('initial filter native data pushed: tier=%s tier6=%s tier8=%s tier10=%s' %
         (data['tier'], len(data['catalog']['6']), len(data['catalog']['8']), len(data['catalog']['10'])))

def _build_filter_view_class():
    from gui.Scaleform.framework.entities.View import View
    class _ShotcallerFilterWindowView(View):
        def __init__(self, ctx=None):
            try: View.__init__(self, ctx)
            except TypeError: View.__init__(self)
            _log('filter view constructed')
        def _populate(self):
            global FILTER_WINDOW_VIEW
            View._populate(self); FILTER_WINDOW_VIEW = self; _log('filter view populated')
            try:
                flash = getattr(self, 'flashObject', None)
                _send_filter_native_data(flash, FILTER_WINDOW_PENDING or _filter_native_data())
            except Exception as error: _log('filter view population unavailable: ' + type(error).__name__)
        def _dispose(self):
            global FILTER_WINDOW_VIEW
            if FILTER_WINDOW_VIEW is self: FILTER_WINDOW_VIEW = None
            _log('filter view dispose'); View._dispose(self)
        def onCloseS(self): _log('filter close callback received'); _close_filter_window('close')
        def onCancelS(self): _log('filter cancel callback received'); _close_filter_window('cancel')
        def onSaveS(self, tier6=None, tier8=None, tier10=None):
            hidden = {'6': list(tier6 or []), '8': list(tier8 or []), '10': list(tier10 or [])}
            normalized, valid = _normalise_filter_data({'schema_version': 1, 'hidden_vehicle_ids': hidden})
            if valid: FILTERS.update(normalized)
            counts = _filter_counts()
            _log('filter save callback received: tier6=%s tier8=%s tier10=%s' % (counts['6'], counts['8'], counts['10']))
            if _save_filter_config():
                _log_history_filters_reapplied()
                _refresh_panel('filters')
            _close_filter_window('save')
        def onTierS(self, tier=8): _log('filter tier callback received: tier=%s' % (_int(tier) or 8))
        def onDefaultsS(self): _log('filter defaults callback received')
        def onPayloadDiagnosticS(self, message=''):
            _log('filter payload diagnostic: ' + _text(message, 700))
        def onClose(self): self.onCloseS()
        def onCancel(self): self.onCancelS()
        def onSave(self, tier6=None, tier8=None, tier10=None): self.onSaveS(tier6, tier8, tier10)
        def onTier(self, tier=8): self.onTierS(tier)
        def onToggle(self, vehicle_id=None, checked=False): self.onToggleS(vehicle_id, checked)
        def onHideAll(self): self.onHideAllS()
        def onShowAll(self): self.onShowAllS()
        def onDefaults(self): self.onDefaultsS()
        def onPayloadDiagnostic(self, message=''): self.onPayloadDiagnosticS(message)
    return _ShotcallerFilterWindowView

def _push_filter_payload(tier):
    global FILTER_WINDOW_PENDING
    FILTER_WINDOW_PENDING = _filter_native_data(tier)
    try:
        _send_filter_native_data(getattr(FILTER_WINDOW_VIEW, 'flashObject', None), FILTER_WINDOW_PENDING)
    except Exception: pass

def _register_filter_window():
    global FILTER_WINDOW_REGISTERED, ShotcallerFilterWindowView
    try:
        from frameworks.wulf import WindowLayer
        from gui.Scaleform.framework import ViewSettings, ScopeTemplates, g_entitiesFactories
        ShotcallerFilterWindowView = _build_filter_view_class()
        if g_entitiesFactories.getSettings(SHOTCALLER_FILTER_WINDOW_ALIAS) is None:
            g_entitiesFactories.addSettings(ViewSettings(SHOTCALLER_FILTER_WINDOW_ALIAS, ShotcallerFilterWindowView,
                'shotcaller/shotcallerVehicleFilters.swf', WindowLayer.OVERLAY, None, ScopeTemplates.GLOBAL_SCOPE))
        FILTER_WINDOW_REGISTERED = True; _log('filter alias registration success')
    except Exception as error:
        FILTER_WINDOW_REGISTERED = False; _log('filter alias registration failure: ' + type(error).__name__)

def _open_filter_window():
    global FILTER_WINDOW_PENDING
    if not FILTER_WINDOW_REGISTERED:
        _log('filter load request ignored: registration unavailable'); return
    if FILTER_WINDOW_VIEW is not None:
        _log('filter load request ignored: already open'); return
    FILTER_WINDOW_PENDING = _filter_native_data(CACHE['tier'] if CACHE['tier'] in (6,8,10) else 8)
    try:
        from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
        _log('filter load request: alias=' + SHOTCALLER_FILTER_WINDOW_ALIAS)
        _lobby_app().loadView(SFViewLoadParams(SHOTCALLER_FILTER_WINDOW_ALIAS, name=FILTER_WINDOW_NAME))
    except Exception as error: _log('filter window load failed: ' + type(error).__name__)

def _close_filter_window(reason):
    global FILTER_WINDOW_VIEW, FILTER_WINDOW_PENDING
    try:
        if FILTER_WINDOW_VIEW is not None: FILTER_WINDOW_VIEW.destroy()
        app = _lobby_app()
        if app is not None: app.containerManager.destroyViews(SHOTCALLER_FILTER_WINDOW_ALIAS, FILTER_WINDOW_NAME)
    except Exception: pass
    FILTER_WINDOW_VIEW = None; FILTER_WINDOW_PENDING = None; _log('filter window closed: reason=' + reason)

def _reset_panel_state():
    PANEL['open'] = False; PANEL['dbid'] = None; PANEL['slot'] = None; PANEL['generation'] = None
    PANEL['fingerprint'] = None; PANEL['suppressed_logged'] = False; PANEL['opening'] = False

def _close_panel(reason):
    if not PANEL['open']: return
    PANEL['open'] = False
    _close_filter_window('history ' + reason)
    _custom_close(reason)
    _destroy_panel_view(); _reset_panel_state()
    _log('vehicle panel closed: reason=' + reason)

def _show_panel(row, refresh=False, preserve_session=False):
    global CUSTOM_WINDOW_PENDING
    if PANEL['opening']: return
    PANEL['opening'] = True
    state, result = _panel_state(row)
    count = len(result.get('vehicles', [])) if isinstance(result, dict) else 0
    suppressed_logged = PANEL['suppressed_logged'] if preserve_session else False
    if PANEL['open']:
        PANEL['open'] = False; _destroy_panel_view()
    try:
        if USE_CUSTOM_VEHICLE_WINDOW and CUSTOM_WINDOW_REGISTERED:
            from gui.Scaleform.framework.managers.loaders import SFViewLoadParams
            app = _lobby_app()
            if app is None: raise RuntimeError('lobby app unavailable')
            CUSTOM_WINDOW_PENDING = {'row': row, 'state': state, 'result': result,
                                      'data': None}
            _log('custom load request: alias=' + SHOTCALLER_VEHICLE_WINDOW_ALIAS)
            app.loadView(SFViewLoadParams(SHOTCALLER_VEHICLE_WINDOW_ALIAS, name=CUSTOM_WINDOW_NAME))
            PANEL['open'] = True; PANEL['dbid'] = row['dbid']; PANEL['slot'] = row['slot_index']; PANEL['generation'] = CACHE['generation']; PANEL['fingerprint'] = _panel_fingerprint(row, state, result); PANEL['suppressed_logged'] = suppressed_logged
            pending = CUSTOM_WINDOW_PENDING
            def confirm_population():
                if (PANEL['open'] and CUSTOM_WINDOW_VIEW is None and CUSTOM_WINDOW_PENDING is pending):
                    _custom_population_failed('view did not populate')
            try:
                import BigWorld
                BigWorld.callback(1.0, confirm_population)
            except Exception: pass
        else: _fallback(row, 'custom unavailable', refresh, preserve_session)
    except Exception as error:
        _fallback(row, 'custom load ' + type(error).__name__, refresh, preserve_session)
    finally:
        PANEL['opening'] = False

def _selected_panel_row():
    if PANEL['dbid'] in CACHE['rows']: return CACHE['rows'][PANEL['dbid']]
    return next((CACHE['rows'][dbid] for dbid in CACHE['order'] if dbid in CACHE['rows']), None)

def _refresh_panel(source='lookup'):
    if not PANEL['open']: return
    selected_exists = PANEL['dbid'] in CACHE['rows']
    row = CACHE['rows'].get(PANEL['dbid']) if selected_exists else _selected_panel_row()
    if row is None:
        _close_panel('selected player removed'); return
    if row['in_battle']:
        _close_panel('battle started'); return
    state, result = _panel_state(row)
    fingerprint = _panel_fingerprint(row, state, result)
    if source == 'filters' and CUSTOM_WINDOW_VIEW is not None:
        try:
            _log('history live refresh requested after filter save')
            _log('history live refresh target found')
            _push_history_view_data(CUSTOM_WINDOW_VIEW, row, state, result, 'live refresh')
            PANEL['fingerprint'] = fingerprint
            PANEL['generation'] = CACHE['generation']
            return
        except Exception as error:
            _log('history live refresh push failed: ' + type(error).__name__)
    if source == 'filters' and CUSTOM_WINDOW_VIEW is None:
        _log('history live refresh skipped: history view not open')
        return
    if selected_exists and fingerprint == PANEL['fingerprint']:
        PANEL['generation'] = CACHE['generation']
        if source == 'roster' and not PANEL['suppressed_logged']:
            PANEL['suppressed_logged'] = True
            _log('vehicle panel refresh suppressed: reason=status-only roster change')
        return
    _show_panel(row, refresh=True, preserve_session=True)

def _schedule_panel_refresh():
    if not PANEL['open']: return
    try:
        import BigWorld
        BigWorld.callback(0.0, lambda: _refresh_panel('lookup'))
    except Exception: pass

def _navigation_target(step):
    rows = _panel_rows()
    if not rows: return None, 'no populated roster slots'
    if len(rows) < 2: return rows[0], 'only one populated roster slot'
    current = _selected_panel_row()
    if current not in rows: return rows[0], None
    return rows[(rows.index(current) + step) % len(rows)], None

def _handle_panel_button(button_id):
    if button_id == 'close':
        if PANEL['open']:
            _reset_panel_state(); _log('vehicle panel closed: reason=user')
        return
    if button_id not in ('previous', 'next'):
        _log('vehicle panel target unchanged: reason=unknown panel action'); return
    direction = button_id
    target, reason = _navigation_target(-1 if direction == 'previous' else 1)
    if target is None:
        _reset_panel_state(); _log('vehicle panel target unchanged: reason=' + reason); return
    state, result = _panel_state(target)
    count = len(result.get('vehicles', [])) if isinstance(result, dict) else 0
    if reason is not None:
        _log('vehicle panel target unchanged: reason=' + reason)
        return
    _log('vehicle panel target changed: direction=%s slot=%s dbID=%s vehicles=%s state=%s' % (direction, target['slot_index'], target['dbid'], count, state))
    suppressed_logged = PANEL['suppressed_logged']
    PANEL['open'] = False; PANEL['dbid'] = target['dbid']; PANEL['slot'] = target['slot_index']
    PANEL['suppressed_logged'] = suppressed_logged
    try:
        import BigWorld
        BigWorld.callback(0.0, lambda: _show_panel(target, refresh=True, preserve_session=True))
    except Exception: _reset_panel_state()

def _on_panel_key(event):
    try:
        import Keys
        if not event.isKeyDown() or not event.isCtrlDown() or not event.isAltDown(): return
        if event.key == Keys.KEY_V:
            if not is_supported_room_context(): _log('panel open ignored: no supported room context'); return
            if not CACHE['rows']: _log('panel open ignored: roster empty'); return
            if any(row.get('in_battle') for row in CACHE['rows'].values()):
                _log('battle transition detected: closing ShotCaller lobby views'); _close_panel('battle context'); _log('ShotCaller disabled in battle context'); return
            if PANEL['open']: _close_panel('shortcut')
            else:
                row = _selected_panel_row()
                if row is not None: _show_panel(row)
    except Exception: pass

def _install_panel_keys():
    global KEY_HANDLER_INSTALLED
    if KEY_HANDLER_INSTALLED: return
    try:
        from gui import InputHandler
        InputHandler.g_instance.onKeyDown += _on_panel_key
        KEY_HANDLER_INSTALLED = True
        _log('vehicle panel trigger installed: Ctrl+Alt+V open/close')
    except Exception as error: _log('vehicle panel trigger unavailable: ' + type(error).__name__)

def _remove_panel_keys():
    global KEY_HANDLER_INSTALLED
    if not KEY_HANDLER_INSTALLED: return
    try:
        from gui import InputHandler
        InputHandler.g_instance.onKeyDown -= _on_panel_key
    except Exception: pass
    KEY_HANDLER_INSTALLED = False

def get_roster_snapshot(): return [_copy(CACHE['rows'][key]) for key in CACHE['order'] if key in CACHE['rows']]
def get_roster_member(dbid): return _copy(CACHE['rows'].get(dbid))
def get_current_tier(): return CACHE['tier']
def get_current_unit_id(): return CACHE['unit_id']
def get_roster_generation(): return CACHE['generation']
def get_volunteer_snapshot(): return [_copy(row) for row in VOLUNTEERS.values()]
def is_stronghold_context_active(): return ROOM_CONTEXT == ROOM_CONTEXT_STRONGHOLD
def is_supported_room_context(): return ROOM_CONTEXT in (ROOM_CONTEXT_STRONGHOLD, ROOM_CONTEXT_PLATOON)
def get_lifecycle_snapshot():
    return {'watcher_active': bool(_stronghold_watcher_active), 'watcher_generation': _stronghold_watcher_generation,
            'pending_exit': _pending_exit_token is not None, 'roster_populated': bool(CACHE['rows']),
            'tier': CACHE['tier'], 'unit_id': CACHE['unit_id'], 'roster_generation': CACHE['generation']}
def get_lookup_snapshot(): return [_copy(value) for value in LOOKUPS.values()]
def get_player_lookup(dbid): return _copy(LOOKUPS.get(dbid))
def get_lookup_status(): return dict(LOOKUP_STATUS)

def _native_dispatch(callback):
    """Run a completion on the BigWorld script thread when available."""
    try:
        import BigWorld
        scheduler = getattr(BigWorld, 'callback', None)
        if callable(scheduler):
            scheduler(0.0, callback)
            return
    except Exception:
        pass
    callback()

def _native_error(category, http_status=None, body=None):
    outcome = {'status': 'error', 'category': category, 'http_status': http_status,
               'body_returned': body is not None}
    if body is not None:
        outcome['body_prefix'] = _text(body, 200)
    return outcome

def _native_exception_category(error):
    """Classify without leaking the request URL, credentials, or response body."""
    if isinstance(error, socket.timeout): return 'timeout'
    if isinstance(error, urllib2.HTTPError): return 'http'
    if isinstance(error, urllib2.URLError):
        reason = getattr(error, 'reason', None)
        if isinstance(reason, socket.timeout): return 'timeout'
        text = str(reason).lower()
        if 'certificate' in text or 'ssl' in text or 'tls' in text: return 'tls'
        if 'getaddrinfo' in text or 'name or service not known' in text or 'host not found' in text or 'no such host' in text: return 'dns'
        return 'network'
    text = str(error).lower()
    if 'certificate' in text or 'ssl' in text or 'tls' in text: return 'tls'
    return 'unknown'

def request_json(url, callback, errback=None, timeout=10.0):
    """Issue one HTTPS JSON GET through WoT's audited async fetchURL service.

    The returned handle can be cancelled logically. BigWorld.fetchURL itself has
    no audited cancellation API, so a late response is ignored after cancel.
    Completion is always scheduled back through BigWorld.callback when present.
    """
    global NATIVE_REQUEST_SERIAL
    NATIVE_REQUEST_SERIAL += 1
    token = NATIVE_REQUEST_SERIAL
    handle = {'token': token, 'cancelled': False, 'done': False, 'started': time.time()}
    NATIVE_ACTIVE_REQUESTS[token] = handle

    def finish_success(data, status):
        if handle['done'] or handle['cancelled']: return
        handle['done'] = True; NATIVE_ACTIVE_REQUESTS.pop(token, None)
        callback(data, {'status': 'success', 'http_status': status, 'seconds': time.time() - handle['started']})

    def finish_error(outcome):
        if handle['done'] or handle['cancelled']: return
        handle['done'] = True; NATIVE_ACTIVE_REQUESTS.pop(token, None)
        if errback is not None: errback(outcome)

    def receive(*args):
        # Client source uses response.responseCode and response.body in its own
        # BigWorld.fetchURL callbacks (uilogging/core/handler.py).
        response = args[0] if len(args) == 1 else None
        status = getattr(response, 'responseCode', None)
        body = getattr(response, 'body', None)
        try:
            body_length = len(body.encode('utf-8')) if isinstance(body, unicode) else len(body or '')
        except Exception:
            body_length = -1
        def process():
            if handle['cancelled'] or handle['done']: return
            if len(args) != 1 or response is None:
                outcome = _native_error('callback'); outcome.update({'callback_args': len(args), 'callback_types': ','.join(type(value).__name__ for value in args), 'body_type': type(body).__name__, 'body_bytes': body_length}); finish_error(outcome)
                return
            if status is None or status <= 0:
                finish_error(_native_error('network', status, body))
                return
            if status < 200 or status >= 300:
                finish_error(_native_error('http', status, body))
                return
            try:
                payload = json.loads(body)
            except (TypeError, ValueError):
                finish_error(_native_error('invalid_json', status, body))
                return
            if not isinstance(payload, dict):
                finish_error(_native_error('invalid_json', status, body))
                return
            if payload.get('status') != 'ok':
                finish_error(_native_error('wg_api', status, body))
                return
            finish_success(payload, status)
        _native_dispatch(process)

    try:
        import BigWorld
        fetch = getattr(BigWorld, 'fetchURL', None)
        if not callable(fetch): raise RuntimeError('BigWorld.fetchURL unavailable')
        # Exact argument order is verified from gui/clientgw/factory.py in the
        # 2.3.1.0 client: url, callback, headers, timeout, method, postData.
        fetch(url, receive, {}, float(timeout), 'GET', '')
    except Exception as error:
        category = _native_exception_category(error)
        _native_dispatch(lambda: finish_error(_native_error(category)))
    return handle

def cancel_native_request(handle):
    if isinstance(handle, dict):
        handle['cancelled'] = True
        NATIVE_ACTIVE_REQUESTS.pop(handle.get('token'), None)

def _cancel_native_requests():
    for handle in list(NATIVE_ACTIVE_REQUESTS.values()): cancel_native_request(handle)

def _native_realm():
    realm = NATIVE_DEFAULT_REALM
    try:
        from constants import CURRENT_REALM
        candidate = str(CURRENT_REALM).upper()
        if candidate in NATIVE_REALMS: realm = candidate
    except Exception: pass
    return realm

def _native_url(realm, path, params):
    if not NATIVE_WG_APP_ID: return None
    query = dict(params); query['application_id'] = NATIVE_WG_APP_ID
    return NATIVE_REALMS[realm] + '/wot/' + path + '/?' + urllib.urlencode(query)

def _native_cache_path(realm, dbid, tier):
    return os.path.join(NATIVE_CACHE_DIR, 'player_%s_%s_tier%s.json' % (realm.lower(), int(dbid), int(tier)))

def _native_read_cache(realm, dbid, tier):
    try:
        data = json.load(open(_native_cache_path(realm, dbid, tier), 'rb'))
        if data.get('schema') != NATIVE_CACHE_SCHEMA or data.get('realm') != realm or not isinstance(data.get('result'), dict): return None
        return data
    except Exception: return None

def _native_atomic_write(path, data):
    try:
        directory = os.path.dirname(path)
        if not os.path.isdir(directory): os.makedirs(directory)
        temporary = path + '.tmp'
        handle = open(temporary, 'wb')
        try:
            handle.write(json.dumps(data, separators=(',', ':'), ensure_ascii=True)); handle.flush()
            try: os.fsync(handle.fileno())
            except Exception: pass
        finally: handle.close()
        try:
            import ctypes
            if not ctypes.windll.kernel32.MoveFileExW(unicode(temporary), unicode(path), 0x1 | 0x8): raise OSError('MoveFileExW failed')
        except Exception:
            if os.path.exists(path): os.remove(path)
            os.rename(temporary, path)
        return True
    except Exception:
        try:
            if os.path.exists(path + '.tmp'): os.remove(path + '.tmp')
        except Exception: pass
        return False

def _native_write_player_cache(realm, dbid, tier, result):
    if _native_atomic_write(_native_cache_path(realm, dbid, tier), {'schema': NATIVE_CACHE_SCHEMA, 'realm': realm, 'dbid': int(dbid), 'tier': int(tier), 'fetched_at': time.time(), 'result': result}): _native_prune_cache()

def _native_prune_cache():
    """Bound public player-history retention without touching filter settings."""
    try:
        files = [os.path.join(NATIVE_CACHE_DIR, name) for name in os.listdir(NATIVE_CACHE_DIR) if name.startswith('player_') and name.endswith('.json')]
        files.sort(key=lambda path: os.path.getmtime(path), reverse=True)
        for path in files[120:]: os.remove(path)
    except Exception: pass

def _native_tankopedia_path(realm): return os.path.join(NATIVE_CACHE_DIR, 'tankopedia_%s.json' % realm.lower())

def _native_load_tankopedia_cache(realm):
    try:
        data = json.load(open(_native_tankopedia_path(realm), 'rb'))
        if data.get('schema') != NATIVE_CACHE_SCHEMA or data.get('realm') != realm or not isinstance(data.get('tanks'), dict): return None
        if time.time() - float(data.get('fetched_at', 0)) > NATIVE_CACHE_TTL: return None
        return dict((int(key), value) for key, value in data['tanks'].iteritems())
    except Exception: return None

def _native_write_tankopedia_cache(realm, tanks):
    encoded = dict((str(key), value) for key, value in tanks.iteritems())
    _native_atomic_write(_native_tankopedia_path(realm), {'schema': NATIVE_CACHE_SCHEMA, 'realm': realm, 'fetched_at': time.time(), 'tanks': encoded})

def _native_battles(record):
    try: return max(0, int((record.get('all') or {}).get('battles', 0)))
    except (TypeError, ValueError): return 0

def _native_battles_present(record):
    try:
        all_stats = record.get('all') or {}
        return 'battles' in all_stats and _int(all_stats.get('battles')) is not None
    except Exception: return False

def _native_result(player, records, tankopedia, tier):
    result = {'dbid': player['dbid'], 'name': player['name'], 'status': 'api_error', 'vehicles': []}
    if records is None:
        result['status'] = 'no_account'; return result
    vehicles = []
    for record in records:
        try: tank_id = int(record.get('tank_id', 0))
        except (TypeError, ValueError): continue
        tank = tankopedia.get(tank_id)
        if not tank or _int(tank.get('tier')) != tier: continue
        vehicles.append({'tank_id': tank_id, 'name': tank.get('name') or 'Unknown', 'tier': tier,
                         'type': tank.get('type') or 'unknown', 'battles': _native_battles(record),
                         'wins': _int((record.get('all') or {}).get('wins')) or 0})
    vehicles.sort(key=lambda item: (-item['battles'], item['name']))
    result['vehicles'] = vehicles; result['status'] = 'ok' if vehicles else 'no_vehicle_history'
    return result

def _native_lookup_key(realm, tier=None, rows=None):
    if rows is None: rows = CACHE['rows'].values()
    dbids = sorted(set(_int(row.get('dbid')) for row in rows if _int(row.get('dbid')) is not None and _int(row.get('dbid')) > 0))
    return (ROOM_CONTEXT, CACHE['unit_id'], realm, CACHE['tier'] if tier is None else tier, tuple(dbids))

def _native_key_log(key):
    return 'context=%s unit=%s realm=%s tier=%s accounts=%s' % (key[0], key[1], key[2], key[3], len(key[4]))

def _native_is_stale(lookup_key):
    if not is_supported_room_context() or any(row.get('in_battle') for row in CACHE['rows'].values()): return True
    return _native_lookup_key(lookup_key[2]) != lookup_key

def _native_finish(players, realm, tier, lookup_key, started, results, stale_fallback=None, reason=None):
    NATIVE_INFLIGHT_BATCHES.discard(lookup_key); LOOKUP_STATUS['inflight'] = False
    if _native_is_stale(lookup_key):
        active_key = _native_lookup_key(realm); LOOKUP_STATUS['lookup_state'] = 'idle'
        _log('native response stale: requestedKey=%s activeKey=%s' % (_native_key_log(lookup_key), _native_key_log(active_key)))
        current_rows = [CACHE['rows'][dbid] for dbid in CACHE['order'] if dbid in CACHE['rows']]
        if current_rows and is_supported_room_context() and not any(row.get('in_battle') for row in current_rows):
            _log('native replacement lookup queued: players=%s tier=%s' % (len(current_rows), CACHE['tier']))
            _queue_lookup(current_rows)
        _schedule_panel_refresh(); return
    if CACHE['generation'] != LOOKUP_STATUS.get('last_attempt_generation'):
        _log('native stale response accepted: reason=lookup identity unchanged')
    fallback_count = 0
    for player in players:
        dbid = player['dbid']; result = results.get(dbid)
        if result is None and stale_fallback and dbid in stale_fallback:
            result = dict(stale_fallback[dbid]); fallback_count += 1
        if result is None: result = {'dbid': dbid, 'name': player['name'], 'status': 'api_error', 'vehicles': []}
        LOOKUPS[dbid] = result
    if fallback_count: _log('native stale cache fallback: players=%s reason=%s' % (fallback_count, reason or 'transport'))
    LOOKUP_STATUS['lookup_state'] = 'complete' if not reason else 'error'
    _log('native lookup complete: players=%s tier=%s generation=%s seconds=%.2f' % (len(players), tier, CACHE['generation'], time.time() - started))
    _schedule_panel_refresh()
    if LOOKUP_STATUS['pending']:
        LOOKUP_STATUS['pending'] = False; _queue_lookup([CACHE['rows'][dbid] for dbid in CACHE['order'] if dbid in CACHE['rows']])

def _native_local_tankopedia():
    tanks = {}
    try:
        for level in ('6', '8', '10'):
            for item in (_build_vehicle_catalog() or {}).get(level, []):
                tanks[_int(item.get('id'))] = {'name': item.get('name'), 'tier': _int(item.get('tier')), 'type': item.get('type')}
    except Exception: pass
    return dict((key, value) for key, value in tanks.iteritems() if key is not None)

def _native_lookup(players, realm, tier, lookup_key):
    global NATIVE_TANKOPEDIA, NATIVE_TANKOPEDIA_REALM, NATIVE_TANKOPEDIA_HANDLE
    started = time.time(); cache_hits = {}; stale = {}; misses = []
    for player in players:
        cached = _native_read_cache(realm, player['dbid'], tier)
        if cached and time.time() - float(cached.get('fetched_at', 0)) < NATIVE_CACHE_TTL: cache_hits[player['dbid']] = dict(cached['result'])
        else:
            misses.append(player)
            if cached: stale[player['dbid']] = dict(cached['result'])
    if cache_hits: _log('native cache hit: players=%s' % len(cache_hits))
    if not misses:
        _native_finish(players, realm, tier, lookup_key, started, cache_hits); return
    def request_stats(tankopedia):
        account_ids = ','.join(str(player['dbid']) for player in misses)
        url = _native_url(realm, 'tanks/stats', {'account_id': account_ids, 'fields': 'tank_id,all.battles,all.wins'})
        _log('native WG request started: endpoint=tanks/stats accounts=%s realm=%s' % (len(misses), realm))
        def success(payload, meta):
            data = payload.get('data') or {}; results = dict(cache_hits); vehicle_count = 0; with_battles = 0; zero_battles = 0
            for player in misses:
                records = data.get(str(player['dbid']))
                result = _native_result(player, records, tankopedia, tier); results[player['dbid']] = result
                vehicle_count += len(result['vehicles'])
                normalized_ids = set(vehicle['tank_id'] for vehicle in result['vehicles'])
                with_battles += sum(1 for record in (records or []) if _int(record.get('tank_id')) in normalized_ids and _native_battles_present(record))
                zero_battles += sum(1 for vehicle in result['vehicles'] if vehicle['battles'] == 0)
                _native_write_player_cache(realm, player['dbid'], tier, result)
            _log('native WG request complete: status=%s seconds=%.2f' % (meta['http_status'], meta['seconds']))
            _log('native WG response parsed: players=%s vehicles=%s withBattles=%s zeroBattles=%s' % (len(misses), vehicle_count, with_battles, zero_battles))
            _native_finish(players, realm, tier, lookup_key, started, results)
        def failure(outcome):
            _log('native WG request failed: category=%s responseCode=%s' % (outcome.get('category'), outcome.get('http_status')))
            if outcome.get('category') == 'callback': _log('native callback diagnostics: args=%s types=%s' % (outcome.get('callback_args'), outcome.get('callback_types')))
            _native_finish(players, realm, tier, lookup_key, started, dict(cache_hits), stale, outcome.get('category'))
        request_json(url, success, failure, timeout=15.0)
    if NATIVE_TANKOPEDIA and NATIVE_TANKOPEDIA_REALM == realm:
        request_stats(NATIVE_TANKOPEDIA); return
    cached_tanks = _native_load_tankopedia_cache(realm)
    if cached_tanks:
        NATIVE_TANKOPEDIA = cached_tanks; NATIVE_TANKOPEDIA_REALM = realm; request_stats(cached_tanks); return
    url = _native_url(realm, 'encyclopedia/vehicles', {'fields': 'tank_id,name,tier,type'})
    _log('native WG request started: endpoint=encyclopedia/vehicles realm=%s' % realm)
    def tanks_success(payload, meta):
        global NATIVE_TANKOPEDIA, NATIVE_TANKOPEDIA_REALM, NATIVE_TANKOPEDIA_HANDLE
        NATIVE_TANKOPEDIA_HANDLE = None; raw = payload.get('data') or {}; tanks = {}
        for key, tank in raw.iteritems():
            try: tanks[int(key)] = {'name': tank.get('name'), 'tier': _int(tank.get('tier')), 'type': tank.get('type')}
            except Exception: pass
        NATIVE_TANKOPEDIA = tanks; NATIVE_TANKOPEDIA_REALM = realm; _native_write_tankopedia_cache(realm, tanks)
        _log('native WG request complete: endpoint=encyclopedia/vehicles status=%s seconds=%.2f tanks=%s' % (meta['http_status'], meta['seconds'], len(tanks))); request_stats(tanks)
    def tanks_failure(outcome):
        global NATIVE_TANKOPEDIA_HANDLE
        NATIVE_TANKOPEDIA_HANDLE = None; local_tanks = _native_local_tankopedia()
        if local_tanks:
            _log('native tankopedia fallback: source=local catalog tanks=%s' % len(local_tanks)); request_stats(local_tanks); return
        _log('native tankopedia unavailable: category=' + str(outcome.get('category')))
        _native_finish(players, realm, tier, lookup_key, started, dict(cache_hits), stale, outcome.get('category'))
    NATIVE_TANKOPEDIA_HANDLE = request_json(url, tanks_success, tanks_failure, timeout=15.0)

def _queue_lookup(rows, force=False):
    if not is_supported_room_context() or not rows or CACHE['tier'] not in (6, 8, 10) or CACHE['unit_id'] is None: return
    if any(row.get('in_battle') for row in rows): _log('ShotCaller disabled in battle context'); return
    if LOOKUP_STATUS['inflight']: LOOKUP_STATUS['pending'] = True; return
    players = []; seen = set()
    for row in rows:
        dbid = _int(row.get('dbid'))
        if dbid is None or dbid <= 0 or dbid in seen or (not force and dbid in LOOKUPS): continue
        seen.add(dbid); players.append({'dbid': dbid, 'name': row.get('name') or ''})
    if not players: return
    if not NATIVE_WG_APP_ID:
        LOOKUP_STATUS['lookup_state'] = 'error'; _log('native lookup unavailable: reason=application ID not configured'); _schedule_panel_refresh(); return
    realm = _native_realm(); host = NATIVE_REALMS[realm].split('//', 1)[1]
    _log('native WG realm resolved: realm=%s host=%s' % (realm, host))
    players = players[:NATIVE_MAX_BATCH_ACCOUNTS]; key = _native_lookup_key(realm, CACHE['tier'])
    if key in NATIVE_INFLIGHT_BATCHES: return
    NATIVE_INFLIGHT_BATCHES.add(key); LOOKUP_STATUS['inflight'] = True; LOOKUP_STATUS['lookup_state'] = 'queued'; LOOKUP_STATUS['last_attempt_generation'] = CACHE['generation']
    _log('native roster lookup queued: players=%s tier=%s generation=%s' % (len(players), CACHE['tier'], CACHE['generation']))
    _native_lookup(players, realm, CACHE['tier'], key)

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
    global EMPTY_SNAPSHOTS, _pending_exit_token, HOVER_ACTIVE
    _cancel_native_requests(); NATIVE_INFLIGHT_BATCHES.clear()
    if not CACHE['rows'] and not VOLUNTEERS:
        _close_panel(reason)
        EMPTY_SNAPSHOTS = 0; _pending_exit_token = None; return False
    _close_panel(reason)
    CACHE['rows'] = {}; CACHE['order'] = []; CACHE['unit_id'] = None; CACHE['tier'] = None; CACHE['resolved_tier'] = None; CACHE['tier_reason'] = None; CACHE['last_update'] = None; LOOKUPS.clear()
    VOLUNTEERS.clear(); ROW_FIELD_SOURCES.clear(); PLATOON_MERGE_LOGGED.clear(); EMPTY_SNAPSHOTS = 0; _pending_exit_token = None; HOVER_ACTIVE = None; CACHE['generation'] += 1
    _log('roster cache cleared: reason=' + reason)
    if reason == 'Stronghold watcher stopped': _log('lifecycle validation passed: detachment exit cleared cache')
    return True

def _set_room_context(context, reason=''):
    """Only enter supported contexts from an audited client entity/view signal."""
    global ROOM_CONTEXT
    if context not in (ROOM_CONTEXT_NONE, ROOM_CONTEXT_STRONGHOLD, ROOM_CONTEXT_PLATOON): context = ROOM_CONTEXT_NONE
    if ROOM_CONTEXT == context: return
    previous = ROOM_CONTEXT; ROOM_CONTEXT = context
    if previous == ROOM_CONTEXT_NONE and context != ROOM_CONTEXT_NONE:
        _log('room context entered: ' + context)
    elif previous != ROOM_CONTEXT_NONE and context == ROOM_CONTEXT_NONE:
        _log('room context exited: ' + previous)
    else:
        _log('room context changed: %s -> %s' % (previous, context))

def _detected_room_context():
    """Use the prebattle dispatcher type; roster data alone is never a context signal."""
    if _stronghold_watcher_active: return ROOM_CONTEXT_STRONGHOLD
    try:
        from gui.prb_control import prb_getters
        from gui.prb_control.settings import PREBATTLE_TYPE
        if prb_getters.getPrebattleType() == PREBATTLE_TYPE.SQUAD:
            return ROOM_CONTEXT_PLATOON
    except Exception: pass
    return ROOM_CONTEXT_NONE

def _platoon_value(value, key, default=None):
    try:
        if isinstance(value, dict): return value[key] if key in value else default
        result = getattr(value, key, default)
        return result() if callable(result) and key.startswith('get') else result
    except Exception: return default

def _platoon_row(entity, unit_id, slot_index, slot):
    """Normalize the actual UnitEntity slot iterator without importing a UI model."""
    player = _platoon_value(slot, 'player')
    if player is None: return None
    dbid = _int(_platoon_value(player, 'dbID', _platoon_value(player, 'getDBID')))
    if dbid is None: return None
    vehicle = _platoon_value(slot, 'vehicle')
    intcd = _int(_platoon_value(vehicle, 'vehTypeCD', _platoon_value(vehicle, 'intCD')))
    level = _int(_platoon_value(vehicle, 'vehLevel', _platoon_value(vehicle, 'level')))
    current = _current_vehicle_values(dbid, intcd)
    return {'slot_index': slot_index, 'unit_id': unit_id, 'dbid': dbid,
            'account_id': _platoon_value(player, 'accID'), 'name': _platoon_value(player, 'name', _platoon_value(player, 'userName')),
            'full_name': _platoon_value(player, 'fullName', _platoon_value(player, 'name')), 'clan': _platoon_value(player, 'clanAbbrev'),
            'rating': _platoon_value(player, 'rating'), 'player_ready': _platoon_value(player, 'isReady', _platoon_value(player, 'readyState')),
            'vehicle_ready': None, 'player_status': None, 'is_frozen': False, 'is_in_battle': False, 'in_battle': False,
            'commander': bool(_platoon_value(player, 'isCommander', _platoon_value(player, 'isCreator'))), 'offline': False, 'role': None,
            'is_legionnaire': False, 'is_current_user': bool(_platoon_value(player, 'isCurrentPlayer', False)), 'vehicle_intcd': intcd,
            'vehicle_name': current.get('vehicle_name'), 'vehicle_short_name': current.get('vehicle_short_name'),
            'vehicle_internal_name': current.get('vehicle_internal_name'), 'vehicle_level': current.get('vehicle_level', level) or level,
            'vehicle_type': current.get('vehicle_type'), 'vehicle_nation_id': current.get('vehicle_nation_id')}

def _rebuild_platoon_roster(entity, reason, attempt=0):
    """Authoritative random-squad source: UnitEntity.getUnit + getSlotsIterator."""
    if ROOM_CONTEXT != ROOM_CONTEXT_PLATOON: return False
    rows = []
    try:
        unit_id, unit = entity.getUnit(safe=True)
        if unit is not None:
            for index, slot in enumerate(entity.getSlotsIterator(unit_id, unit)):
                row = _platoon_row(entity, unit_id, index, slot)
                if row is not None: rows.append(row)
    except Exception as error:
        _log('platoon roster rebuild failed: reason=%s error=%s' % (reason, type(error).__name__))
    _log('platoon initial roster retry: attempt=%s generation=%s members=%s' % (attempt, CACHE['generation'], len(rows)))
    if rows:
        _log('platoon roster source=entity')
        _log('platoon roster accepted: members=%s dbIDs=%s commander=%s' % (len(rows), str([row['dbid'] for row in rows[:5]]), next((row['dbid'] for row in rows if row['commander']), None)))
        _apply(rows, source='entity'); return True
    return False

def _schedule_platoon_rebuilds(entity, reason):
    global PLATOON_REBUILD_TOKEN
    PLATOON_REBUILD_TOKEN += 1; token = PLATOON_REBUILD_TOKEN
    def run(attempt):
        if token != PLATOON_REBUILD_TOKEN or ROOM_CONTEXT != ROOM_CONTEXT_PLATOON: return
        if _rebuild_platoon_roster(entity, reason, attempt): return
    for attempt, delay in enumerate((0.0, 0.25, 0.75, 1.5), 1):
        try:
            import BigWorld; BigWorld.callback(delay, lambda value=attempt: run(value))
        except Exception:
            if delay == 0.0: run(attempt)

def _resolve_tier(rows):
    """Regular platoons require every occupied selected vehicle to agree."""
    if ROOM_CONTEXT != ROOM_CONTEXT_PLATOON:
        return next((row['vehicle_level'] for row in rows if row['vehicle_level'] in (6, 8, 10)), None), None
    selected = [row['vehicle_level'] for row in rows if row.get('vehicle_intcd') is not None and row.get('vehicle_level') is not None]
    if len(selected) != len(rows):
        return None, 'unknown'
    unique = sorted(set(selected))
    if len(unique) != 1:
        _log('platoon tier unresolved: selectedTiers=' + str(unique)); return None, 'mixed'
    if unique[0] not in (6, 8, 10):
        _log('platoon tier unsupported: tier=' + str(unique[0])); return None, 'unsupported'
    _log('platoon tier resolved: tier=' + str(unique[0])); return unique[0], None

def _cancel_pending_exit(reason):
    global _pending_exit_token
    if _pending_exit_token is not None:
        _pending_exit_token = None
        _log('Stronghold exit clear cancelled: reason=' + reason)
        if reason == 'watcher restarted': _log('lifecycle validation passed: transient watcher stop ignored')

def _remove_volunteer(dbid):
    row = VOLUNTEERS.pop(dbid, None)
    if row: _log('volunteer removed: dbID=%s name=%s' % (dbid, row['name']))

def _incoming_has_value(field, value):
    if field in ('player_ready', 'commander', 'is_current_user', 'is_frozen', 'in_battle'): return value is not None
    return value not in (None, '', 0)

def _merge_platoon_entity_row(existing, incoming):
    """Entity owns occupancy/slot identity; converter owns rich vehicle/status fields."""
    merged = dict(incoming)
    preserve = ('vehicle_intcd', 'vehicle_level', 'vehicle_name', 'vehicle_short_name', 'vehicle_internal_name',
                'vehicle_type', 'vehicle_nation_id', 'vehicle_ready', 'player_ready', 'player_status',
                'name', 'full_name', 'clan', 'rating')
    for field in preserve:
        old = existing.get(field); value = incoming.get(field)
        if not _incoming_has_value(field, value) and _incoming_has_value(field, old):
            merged[field] = old
            # One concise vehicle preservation line per player is enough; other
            # sparse fields follow the same merge rule without flooding python.log.
            marker = (incoming['dbid'], 'vehicle')
            if field == 'vehicle_intcd' and marker not in PLATOON_MERGE_LOGGED:
                PLATOON_MERGE_LOGGED.add(marker)
                _log('platoon merge preserved: dbID=%s field=%s existing=%s incoming=%s existingSource=converter incomingSource=entity' %
                     (incoming['dbid'], 'vehicle' if field == 'vehicle_intcd' else field, old, value))
    return merged

def _apply(rows, source='converter'):
    global EMPTY_SNAPSHOTS, _populated_generation, PLATOON_REBUILD_TOKEN
    if not rows:
        if CACHE['rows']:
            EMPTY_SNAPSHOTS += 1; _log('roster empty confirmation pending: %s/2' % EMPTY_SNAPSHOTS)
            if EMPTY_SNAPSHOTS >= 2: clear_roster_cache('two consecutive empty snapshots')
        return
    context = _detected_room_context()
    # RandomSquadEntity.init is an audited context signal and can precede the
    # dispatcher type becoming observable; preserve the proven 0.0.51 converter path.
    if context == ROOM_CONTEXT_NONE and ROOM_CONTEXT == ROOM_CONTEXT_PLATOON:
        context = ROOM_CONTEXT_PLATOON
    if context == ROOM_CONTEXT_NONE:
        # The shared legacy converter is also used by unsupported rooms.
        _log('platoon roster rejected: reason=unsupported prebattle context')
        return
    if context == ROOM_CONTEXT_PLATOON:
        try:
            from gui.prb_control import prb_getters
            prebattle_type = prb_getters.getPrebattleType()
        except Exception:
            prebattle_type = '<unavailable>'
        _log('platoon converter candidate: converter=makeSlotsVOs activePrebattleType=%s members=%s slots=%s' % (prebattle_type, len(rows), len(rows)))
        if rows:
            _log('platoon roster source=converter')
    _set_room_context(context, 'converter')
    if any(row.get('in_battle') for row in rows):
        if PANEL.get('open') or FILTER_WINDOW_VIEW is not None:
            _log('battle transition detected: closing ShotCaller lobby views')
            _close_panel('battle context')
        _log('ShotCaller disabled in battle context')
        return
    EMPTY_SNAPSHOTS = 0; _populated_generation += 1
    if _pending_exit_token is not None:
        _cancel_pending_exit('roster update')
        _log('lifecycle validation passed: transient watcher stop ignored')
    previous_unit = CACHE['unit_id']; previous_tier = CACHE['tier']
    new = {}; order = []
    for row in rows:
        existing = CACHE['rows'].get(row['dbid'])
        if context == ROOM_CONTEXT_PLATOON and source == 'entity' and existing is not None:
            row = _merge_platoon_entity_row(existing, row)
        new[row['dbid']] = row; order.append(row['dbid'])
    unit_id = next((row['unit_id'] for row in rows if row['unit_id'] is not None), None)
    tier, tier_reason = _resolve_tier(new.values())
    selected_levels = [row.get('vehicle_level') for row in new.values() if row.get('vehicle_intcd') and row.get('vehicle_level') is not None]
    resolved_tier = selected_levels[0] if selected_levels and len(set(selected_levels)) == 1 else None
    if CACHE['unit_id'] is not None and unit_id is not None and CACHE['unit_id'] != unit_id:
        clear_roster_cache('unit changed old=%s new=%s' % (CACHE['unit_id'], unit_id))
    old = CACHE['rows']
    changed = old != new or CACHE['order'] != order or CACHE['tier'] != tier or CACHE.get('resolved_tier') != resolved_tier or CACHE['tier_reason'] != tier_reason or CACHE['unit_id'] != unit_id
    if not changed: return
    first = not old
    for dbid, row in new.items():
        _remove_volunteer(dbid); previous = old.get(dbid)
        if previous is None: _log(('%s member added: dbID=%s name=%s vehicle=%s' % (ROOM_CONTEXT, dbid, row['name'], _vehicle(row))))
        else:
            if any(previous[key] != row[key] for key in ('vehicle_intcd','vehicle_name','vehicle_level')): _log(('%s vehicle changed: dbID=%s old=%s new=%s' % (ROOM_CONTEXT, dbid, previous['vehicle_intcd'], row['vehicle_intcd'])))
            if previous['player_ready'] != row['player_ready']: _log('roster player ready changed: name=%s old=%s new=%s' % (row['name'], previous['player_ready'], row['player_ready']))
            if previous['vehicle_ready'] != row['vehicle_ready']: _log('roster vehicle ready changed: name=%s old=%s new=%s' % (row['name'], previous['vehicle_ready'], row['vehicle_ready']))
            if previous['slot_index'] != row['slot_index']: _log('roster slot changed: name=%s old=%s new=%s' % (row['name'], previous['slot_index'], row['slot_index']))
            if previous['commander'] != row['commander']: _log('roster commander changed: name=%s old=%s new=%s' % (row['name'], previous['commander'], row['commander']))
            if previous['player_status'] != row['player_status']: _log('roster player status changed: name=%s old=%s new=%s' % (row['name'], previous['player_status'], row['player_status']))
            if previous['is_frozen'] != row['is_frozen']: _log('roster frozen changed: name=%s old=%s new=%s' % (row['name'], previous['is_frozen'], row['is_frozen']))
            if previous['in_battle'] != row['in_battle']: _log('roster battle state changed: name=%s old=%s new=%s' % (row['name'], previous['in_battle'], row['in_battle']))
    for dbid, row in old.items():
        if dbid not in new: _log('%s member removed: dbID=%s name=%s' % (ROOM_CONTEXT, dbid, row['name']))
    # Commander first, then the renderer's stable visible slot order.
    order = [row['dbid'] for row in sorted(new.values(), key=lambda item: (not bool(item.get('commander')), item['slot_index']))]
    CACHE['rows'] = new; CACHE['order'] = order; CACHE['unit_id'] = unit_id; CACHE['tier'] = tier; CACHE['resolved_tier'] = resolved_tier; CACHE['tier_reason'] = tier_reason; CACHE['last_update'] = time.time(); CACHE['generation'] += 1
    for dbid in new:
        if source == 'converter':
            ROW_FIELD_SOURCES[dbid] = 'converter'
        elif dbid not in ROW_FIELD_SOURCES:
            ROW_FIELD_SOURCES[dbid] = 'entity'
    for dbid in list(ROW_FIELD_SOURCES):
        if dbid not in new: ROW_FIELD_SOURCES.pop(dbid, None)
    # Unsupported/mixed tiers are an informational state, not evidence that a
    # previously cached supported-tier history became invalid. Keep it for a
    # later return to VI/VIII/X; _panel_state never displays it while tier=None.
    if previous_tier is not None and tier is not None and previous_tier != tier: LOOKUPS.clear()
    for dbid in list(LOOKUPS):
        if dbid not in new: LOOKUPS.pop(dbid, None)
    if tier is not None: _log(('platoon tier resolved: tier=' if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON else 'skirmish tier detected: ') + str(tier))
    if first:
        _log(('%s roster populated: members=%s tier=%s' % (ROOM_CONTEXT, len(rows), tier)) if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON else ('roster cache populated: members=%s tier=%s unit_id=%s' % (len(rows), tier, unit_id)))
        for row in rows: _print_initial(row)
    else: _log('roster cache changed: members=%s tier=%s generation=%s' % (len(rows), tier, CACHE['generation']))
    if context == ROOM_CONTEXT_PLATOON and source == 'converter' and tier in (6, 8, 10) and all(row.get('vehicle_intcd') for row in new.values()):
        PLATOON_REBUILD_TOKEN += 1
        _log('platoon initial retries stopped: reason=complete converter roster')
    _queue_lookup(rows, force=first or previous_unit != unit_id or previous_tier != tier)
    _refresh_panel('roster')

def _current_vehicle_values(dbid, intcd):
    """Read only the local selected item when it matches the unit update."""
    try:
        import account_helpers
        if dbid != account_helpers.getAccountDatabaseID(): return {}
        from CurrentVehicle import g_currentVehicle
        item = g_currentVehicle.item
        if item is None or getattr(item, 'intCD', None) != intcd: return {}
        return {'vehicle_name': getattr(item, 'userName', None),
                'vehicle_short_name': getattr(item, 'shortUserName', None),
                'vehicle_internal_name': getattr(item, 'name', None),
                'vehicle_level': _int(getattr(item, 'level', None)),
                'vehicle_type': getattr(item, 'type', None),
                'vehicle_nation_id': getattr(item, 'nationID', None)}
    except Exception: return {}

def _update_selected_vehicle(dbid, v_infos):
    """Apply the exact Stronghold vehicle event to one existing roster row."""
    if dbid not in CACHE['rows'] or not isinstance(v_infos, (tuple, list)) or not v_infos: return
    info = v_infos[0]
    try: intcd = getattr(info, 'vehTypeCD')
    except Exception: intcd = None
    try: level = _int(getattr(info, 'vehLevel'))
    except Exception: level = None
    intcd = _int(intcd)
    if intcd is not None and intcd <= 0: intcd = None
    if level is not None and level <= 0: level = None
    old = CACHE['rows'][dbid]
    updated = dict(old)
    updated['vehicle_intcd'] = intcd; updated['vehicle_level'] = level
    local_values = _current_vehicle_values(dbid, intcd)
    for key, value in local_values.iteritems():
        if value is not None: updated[key] = value
    new = dict(CACHE['rows']); new[dbid] = updated
    old_tier = CACHE['tier']
    new_tier = next((row['vehicle_level'] for row in [new[key] for key in CACHE['order'] if key in new] if row['vehicle_level'] in (6, 8, 10)), None)
    if old == updated and old_tier == new_tier: return
    CACHE['rows'] = new; CACHE['tier'] = new_tier; CACHE['last_update'] = time.time(); CACHE['generation'] += 1
    if old_tier != new_tier: LOOKUPS.clear()
    _log('selected vehicle changed: dbID=%s old_intCD=%s new_intCD=%s old_tier=%s new_tier=%s' %
         (dbid, old['vehicle_intcd'], intcd, old_tier, new_tier))
    if new_tier is not None: _log('skirmish tier detected: ' + str(new_tier))
    _queue_lookup([new[key] for key in CACHE['order'] if key in new], force=old_tier != new_tier)
    _refresh_panel('vehicle')

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

def _stronghold_vehicle_hook(original):
    def hook(self, dbid, v_infos, *args, **kwargs):
        result = original(self, dbid, v_infos, *args, **kwargs)
        try: _update_selected_vehicle(dbid, v_infos)
        except Exception as error: _log('selected vehicle refresh skipped: ' + type(error).__name__)
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _install_vehicle_selection_listener():
    """Hook only StrongholdBattleRoom's direct unit-vehicle callback."""
    try:
        module = __import__('gui.Scaleform.daapi.view.lobby.fortifications.stronghold_battle_room', fromlist=['*'])
        cls = getattr(module, 'StrongholdBattleRoom', None)
        if cls is None: raise RuntimeError('StrongholdBattleRoom unavailable')
        original = cls.__dict__.get('onUnitVehiclesChanged')
        if not callable(original): raise RuntimeError('onUnitVehiclesChanged unavailable')
        if getattr(original, MARK + 'wrapped', False):
            _log('selected vehicle listener installed: StrongholdBattleRoom.onUnitVehiclesChanged'); return
        VEHICLE_VIEW_ORIGINALS['onUnitVehiclesChanged'] = original
        setattr(cls, 'onUnitVehiclesChanged', _stronghold_vehicle_hook(original))
        _log('selected vehicle listener installed: StrongholdBattleRoom.onUnitVehiclesChanged')
    except Exception as error:
        _log('selected vehicle listener unavailable: ' + type(error).__name__)

def _platoon_entity_hook(name, original):
    """Exact random-platoon entity lifecycle; never touches BaseVehiclesWatcher."""
    def hook(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            if name == 'init':
                _set_room_context(ROOM_CONTEXT_PLATOON, 'RandomSquadEntity.init')
                _schedule_platoon_rebuilds(self, 'init')
            elif name == 'fini':
                if ROOM_CONTEXT == ROOM_CONTEXT_PLATOON:
                    global PLATOON_REBUILD_TOKEN
                    PLATOON_REBUILD_TOKEN += 1
                    _close_panel('platoon context exited'); clear_roster_cache('platoon context cleared'); _set_room_context(ROOM_CONTEXT_NONE, 'RandomSquadEntity.fini'); _log('platoon context cleared')
            elif name in ('unit_onUnitVehicleChanged', 'unit_onUnitVehiclesChanged', 'unit_onUnitRosterChanged', 'unit_onUnitPlayerAdded', 'unit_onUnitPlayerRemoved', 'unit_onUnitPlayerInfoChanged', 'unit_onUnitReadyMaskChanged'):
                _log('platoon vehicle event observed: method=' + name)
                _schedule_platoon_rebuilds(self, name)
        except Exception as error:
            _log('platoon lifecycle hook skipped: ' + type(error).__name__)
        return result
    setattr(hook, MARK + 'wrapped', True); return hook

def _install_platoon_lifecycle():
    """Audited 2.3 lineage: random.squad.entity.RandomSquadEntity.init/fini."""
    try:
        module = __import__('gui.prb_control.entities.random.squad.entity', fromlist=['*'])
        cls = getattr(module, 'RandomSquadEntity', None)
        if cls is None: raise RuntimeError('RandomSquadEntity unavailable')
        installed = 0
        for name in ('init', 'fini', 'unit_onUnitVehicleChanged', 'unit_onUnitVehiclesChanged', 'unit_onUnitRosterChanged', 'unit_onUnitPlayerAdded', 'unit_onUnitPlayerRemoved', 'unit_onUnitPlayerInfoChanged', 'unit_onUnitReadyMaskChanged'):
            original = cls.__dict__.get(name)
            if not callable(original):
                _log('platoon lifecycle hook missing: ' + name); continue
            if getattr(original, MARK + 'wrapped', False): installed += 1; continue
            PLATOON_ENTITY_ORIGINALS[name] = original
            setattr(cls, name, _platoon_entity_hook(name, original)); installed += 1
        _log('platoon lifecycle hooks installed: RandomSquadEntity=' + str(installed))
    except Exception as error:
        _log('platoon lifecycle hook unavailable: ' + type(error).__name__)

def _remove_platoon_lifecycle():
    if not PLATOON_ENTITY_ORIGINALS: return
    try:
        module = __import__('gui.prb_control.entities.random.squad.entity', fromlist=['*'])
        cls = getattr(module, 'RandomSquadEntity', None)
        for name, original in PLATOON_ENTITY_ORIGINALS.items():
            current = cls.__dict__.get(name) if cls is not None else None
            if getattr(current, MARK + 'wrapped', False): setattr(cls, name, original)
    except Exception: pass
    PLATOON_ENTITY_ORIGINALS.clear()

def _remove_vehicle_selection_listener():
    original = VEHICLE_VIEW_ORIGINALS.get('onUnitVehiclesChanged')
    if original is None: return
    try:
        module = __import__('gui.Scaleform.daapi.view.lobby.fortifications.stronghold_battle_room', fromlist=['*'])
        cls = getattr(module, 'StrongholdBattleRoom', None)
        current = cls.__dict__.get('onUnitVehiclesChanged') if cls is not None else None
        if getattr(current, MARK + 'wrapped', False): setattr(cls, 'onUnitVehiclesChanged', original)
    except Exception: pass
    VEHICLE_VIEW_ORIGINALS.clear()

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
            _stronghold_watcher_active = True; _set_room_context(ROOM_CONTEXT_STRONGHOLD, 'StrongholdVehiclesWatcher.start'); _cancel_pending_exit('watcher restarted')
            _log('Stronghold watcher started: generation=' + str(_stronghold_watcher_generation))
        else:
            _stronghold_watcher_active = False; _pending_exit_token = _stronghold_watcher_generation
            token = _pending_exit_token; population = _populated_generation
            _log('Stronghold watcher stopped: generation=' + str(_stronghold_watcher_generation)); _log('Stronghold exit clear scheduled: token=' + str(token))
            def confirm():
                if _pending_exit_token == token and ROOM_CONTEXT == ROOM_CONTEXT_PLATOON:
                    _log('stale Stronghold clear ignored: token=%s currentContext=platoon' % token); return
                if (_pending_exit_token == token and not _stronghold_watcher_active and _stronghold_watcher_generation == token and _populated_generation == population and CACHE['rows']):
                    clear_roster_cache('Stronghold watcher stopped'); _set_room_context(ROOM_CONTEXT_NONE, 'StrongholdVehiclesWatcher.stop')
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
    _load_filter_config(); _install_watcher(); _install_vehicle_selection_listener(); _install_platoon_lifecycle(); _register_custom_window(); _register_filter_window(); _install_panel_keys(); _log('roster converter hooks installed: ' + str(count))
def init(): _log('loaded'); _install()
def fini(): _close_panel('mod unloaded'); _remove_panel_keys(); _remove_vehicle_selection_listener(); _remove_platoon_lifecycle(); clear_roster_cache('mod unloaded'); _set_room_context(ROOM_CONTEXT_NONE, 'mod unloaded'); _log('unloaded')
