"""Prototype 3I: safe StrongholdEvent and web response discovery probe."""

import json
import re


TAG = '[shotcaller]'
MARKER_PREFIX = '_shotcaller_3i_hook_'
TRACKED_WEB_IDS = {}
EVENT_SNAPSHOTS = {}
EVENT_DETAIL_COUNT = 0
SENSITIVE_PATTERN = re.compile(r"(?i)(access_token|token|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
PAYLOAD_HINTS = ('strongholds_battle', 'web_id', 'access_token', 'unit_id',
                 'roster', 'members', 'players', 'slots', 'vehicle',
                 'commander', 'legionary', 'periphery', 'battleroom')
EVENT_HINTS = ('data', 'ctx', 'args', 'kwargs', 'event', 'type', 'alias',
               'name', 'unit', 'roster', 'member', 'player', 'slot',
               'vehicle', 'commander', 'state', 'battle', 'division',
               'level', 'periphery')
IMPORT_MODULES = ('gui.shared.events', 'gui.impl.lobby.stronghold',
                  'gui.impl.lobby.stronghold.stronghold_view',
                  'gui.impl.lobby.stronghold.stronghold_presenter',
                  'gui.impl.lobby.stronghold.stronghold_helpers',
                  'gui.impl.lobby.stronghold.stronghold_constants',
                  'gui.clientgw.strongholds', 'gui.clientgw.strongholds.contexts')


def _log(message):
    print(TAG + ' ' + message)


def _mask(text):
    try:
        return SENSITIVE_PATTERN.sub(r'\1\2***MASKED***', text)
    except Exception:
        return text


def _text(value, limit=1000):
    try:
        return _mask(str(value)[:limit])
    except Exception:
        return '<string unavailable>'


def _combined(instance, args, kwargs):
    parts = [_text(instance)]
    try:
        parts.extend(_text(value) for value in args[:5])
    except Exception:
        pass
    try:
        parts.append(_text(kwargs))
    except Exception:
        pass
    return ' | '.join(parts)[:1500]


def _contains(text, hints):
    lower = text.lower()
    return any(hint in lower for hint in hints)


def _parse(args, kwargs):
    values = list(args) + [kwargs]
    for value in values:
        if isinstance(value, dict):
            return value
        try:
            if isinstance(value, basestring):
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
        except Exception:
            pass
    return None


def _remember_command(payload):
    if not isinstance(payload, dict):
        return
    params = payload.get('params') or {}
    web_id = payload.get('web_id') or params.get('web_id')
    command = payload.get('command')
    action = params.get('action')
    if web_id:
        TRACKED_WEB_IDS[str(web_id)] = (command, action)
    if command == 'strongholds_battle':
        _log('stronghold command: action=' + str(action) + ' web_id=' + str(web_id) +
             ' unit_id=' + str(params.get('unit_id')) + ' periphery_id=' + str(params.get('periphery_id')))


def _log_response(payload, text):
    web_id = None
    command = None
    data = None
    if isinstance(payload, dict):
        web_id = payload.get('web_id')
        command = payload.get('command')
        data = payload.get('data', payload.get('result', payload.get('params')))
    if web_id or _contains(text, ('strongholds_battle', 'web_id')):
        data_type = type(data).__name__
        try:
            data_len = str(len(data))
        except Exception:
            data_len = 'n/a'
        keys = []
        try:
            if isinstance(data, dict):
                keys = sorted(data.keys())[:5]
        except Exception:
            pass
        _log('stronghold response: web_id=' + str(web_id) + ' command=' +
             str(command) + ' data_type=' + data_type + ' data_len=' + data_len +
             ' data_keys=' + _text(keys, 300))
    for known_id, detail in TRACKED_WEB_IDS.items():
        if known_id in text:
            _log('web response matched: web_id=' + known_id + ' action=' +
                 str(detail[1]) + ' payload=' + text[:1500])


def _event_snapshot(event):
    values = []
    for name in sorted(dir(event)):
        if name.startswith('_') or not _contains(name, EVENT_HINTS):
            continue
        try:
            value = getattr(event, name)
            if callable(value):
                if name.lower().startswith(('get', 'is', 'has')) and not _contains(name, ('set', 'change', 'join', 'leave', 'assign', 'kick', 'invite', 'ready', 'select', 'start', 'stop', 'create', 'destroy')):
                    value = value()
                else:
                    continue
            values.append((name, type(value).__name__, _text(value, 1000)))
        except Exception as error:
            values.append((name, 'error', 'ERROR:' + str(error)))
    return tuple(values)


def _inspect_event(event, scope):
    global EVENT_DETAIL_COUNT
    snapshot = _event_snapshot(event)
    key = event.__class__.__name__
    previous = EVENT_SNAPSHOTS.get(key)
    EVENT_SNAPSHOTS[key] = snapshot
    text = _text(event, 1000)
    important = _contains(text + ' ' + _text(snapshot, 1000), ('roster', 'member', 'player', 'slot', 'vehicle', 'unit', 'battle'))
    if EVENT_DETAIL_COUNT >= 10 and previous == snapshot and not important:
        return
    EVENT_DETAIL_COUNT += 1
    _log('stronghold event fired: scope=' + _text(scope, 200) + ' type=' + text)
    try:
        event_dict = getattr(event, '__dict__', None)
        if event_dict is not None:
            _log('stronghold event attr: __dict__ type=' + type(event_dict).__name__ + ' repr=' + _text(event_dict, 1000))
    except Exception:
        pass
    for name, type_name, value in snapshot:
        _log('stronghold event attr: ' + name + ' type=' + type_name + ' repr=' + _text(value, 1000))


def _make_web_hook(class_name, method_name, original, command_hook):
    def hooked(instance, *args, **kwargs):
        try:
            result = original(instance, *args, **kwargs)
        except Exception as error:
            _log('web hook original failed: ' + class_name + '.' + method_name + ': ' + str(error))
            raise
        try:
            payload = _parse(args, kwargs)
            if command_hook:
                _remember_command(payload)
            text = _combined(instance, args, kwargs)
            if _contains(text, PAYLOAD_HINTS):
                _log('web response candidate: ' + class_name + '.' + method_name + ' ' + text)
                _log_response(payload, text)
        except Exception as error:
            _log('web hook inspect failed: ' + class_name + '.' + method_name + ': ' + str(error))
        return result
    return hooked


def _make_event_hook(class_name, method_name, original):
    def hooked(instance, *args, **kwargs):
        try:
            result = original(instance, *args, **kwargs)
        except Exception as error:
            _log('event hook original failed: ' + class_name + '.' + method_name + ': ' + str(error))
            raise
        try:
            for value in args:
                if 'strongholdevent' in value.__class__.__name__.lower():
                    _inspect_event(value, args[1] if len(args) > 1 else None)
        except Exception as error:
            _log('event hook inspect failed: ' + str(error))
        return result
    return hooked


def _make_simple_hook(message, original):
    def hooked(instance, *args, **kwargs):
        try:
            result = original(instance, *args, **kwargs)
        except Exception as error:
            _log(message + ' original failed: ' + str(error))
            raise
        _log(message)
        return result
    return hooked


def _install(target, class_name, method_name, factory):
    try:
        marker = MARKER_PREFIX + method_name
        if getattr(target, marker, False):
            return
        original = getattr(target, method_name, None)
        if not callable(original):
            return
        setattr(target, method_name, factory(class_name, method_name, original))
        setattr(target, marker, True)
    except Exception as error:
        _log('hook install failed: ' + class_name + '.' + method_name + ': ' + str(error))


def _probe_imports():
    for module_name in IMPORT_MODULES:
        try:
            module = __import__(module_name, fromlist=['*'])
            _log('import ok: ' + module_name)
            for name in sorted(dir(module))[:100]:
                if not name.startswith('_') and _contains(name, EVENT_HINTS):
                    _log('stronghold event candidate: ' + module_name + '.' + name)
        except Exception as error:
            _log('import missing: ' + module_name + ': ' + str(error))


def _install_hooks():
    try:
        import gui.Scaleform.daapi.view.lobby.browser as browser_module
        handlers = getattr(browser_module, 'BrowserViewWebHandlers', None)
        browser = getattr(browser_module, 'Browser', None)
        if handlers is not None:
            _install(handlers, 'BrowserViewWebHandlers', 'handleCommand', lambda c,n,o: _make_web_hook(c,n,o,True))
            for name in ('sendResponse', 'sendError', 'sendCommand', 'fireEvent', 'browserCallback', '_sendResponse', '_sendError', '_fireEvent', '_callBrowser'):
                _install(handlers, 'BrowserViewWebHandlers', name, lambda c,n,o: _make_web_hook(c,n,o,False))
        if browser is not None:
            for name in ('as_sendMessageS', 'as_callBrowserS', 'onBrowserCallback', 'onBrowserEvent', 'fireEvent'):
                _install(browser, 'Browser', name, lambda c,n,o: _make_web_hook(c,n,o,False))
    except Exception as error:
        _log('browser import failed: ' + str(error))
    try:
        import gui.game_control.BrowserController as controller_module
        for class_name in ('BrowserController', 'WebBrowser'):
            target = getattr(controller_module, class_name, None)
            if target is not None:
                for name in ('send', 'sendMessage', 'sendResponse', 'sendEvent', 'callback', 'call', 'execute', 'runScript', 'callBrowser', '_send', '_callback', '_sendEvent', '_callBrowser', 'onCallback', 'onEvent'):
                    _install(target, class_name, name, lambda c,n,o: _make_web_hook(c,n,o,False))
    except Exception as error:
        _log('BrowserController import failed: ' + str(error))
    try:
        import gui.shared.event_bus as event_bus_module
        event_bus = getattr(event_bus_module, 'EventBus', None)
        if event_bus is not None:
            for name in ('handleEvent', 'fireEvent'):
                _install(event_bus, 'EventBus', name, _make_event_hook)
    except Exception as error:
        _log('EventBus import failed: ' + str(error))


def _install_light_detections():
    try:
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as watcher_module
        watcher = getattr(watcher_module, 'StrongholdVehiclesWatcher', None)
        if watcher is not None:
            for name in ('start', 'stop'):
                _install(watcher, 'StrongholdVehiclesWatcher', name, lambda c,n,o: _make_simple_hook('stronghold watcher ' + ('started' if n == 'start' else 'stopped'), o))
    except Exception:
        pass
    try:
        import frameworks.wulf.windows_system.window as window_module
        window = getattr(window_module, 'Window', None)
        if window is not None:
            _install(window, 'Window', '__init__', lambda c,n,o: _make_simple_hook('stronghold window observed', o))
    except Exception:
        pass


def init():
    _log('loaded')
    _probe_imports()
    _install_hooks()
    _install_light_detections()


def fini():
    _log('unloaded')
