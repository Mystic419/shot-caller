"""Prototype 3B: safe Stronghold watcher context diagnostics."""

import time


TAG = '[shotcaller]'
WATCHER_MARKER_PREFIX = '_shotcaller_stronghold_watcher_'
WINDOW_MARKER_PREFIX = '_shotcaller_stronghold_window_'
WINDOW_METHOD_HINTS = ('load', 'loaded', 'show', 'create', 'init')
CONTEXT_HINTS = ('unit', 'entity', 'roster', 'player', 'member', 'commander',
                 'vehicles', 'selected', 'level', 'division', 'mode', 'queue',
                 'settings', 'state')
MUTATING_METHOD_HINTS = ('start', 'stop', 'update', 'set', 'clear', 'select',
                         'leave', 'join', 'assign', 'kick', 'invite', 'ready')
MAX_CONTEXT_ATTRIBUTES = 50
MAX_CONTEXT_METHODS = 50
UPDATE_LOG_INTERVAL_SECONDS = 5.0
_start_context_probed = set()
_update_context_probed = set()
_last_update_log = {}


def _log(message):
    print(TAG + ' ' + message)


def _short_repr(value, limit=200):
    try:
        return repr(value)[:limit]
    except Exception:
        return '<repr unavailable>'


def _short_string(value, limit=300):
    try:
        return str(value)[:limit]
    except Exception:
        return '<string unavailable>'


def _is_context_name(name):
    name_lower = name.lower()
    return any(hint in name_lower for hint in CONTEXT_HINTS)


def _is_safe_reader_method(name):
    name_lower = name.lower()
    if any(hint in name_lower for hint in MUTATING_METHOD_HINTS):
        return False
    return name_lower.startswith('get') or name_lower.startswith('is') or name_lower.startswith('has')


def _log_context_value(kind, name, value):
    _log('stronghold context ' + kind + ': ' + name + ' type=' +
         type(value).__name__ + ' repr=' + _short_repr(value))


def _probe_watcher_context(instance, phase):
    _log('stronghold context phase: ' + phase)
    _log('stronghold context class: ' + instance.__class__.__name__)
    _log('stronghold context self: ' + _short_repr(instance, 300))

    try:
        names = sorted(dir(instance))
    except Exception as error:
        _log('stronghold context dir failed: ' + str(error))
        return

    attribute_count = 0
    method_count = 0
    for name in names:
        if name.startswith('__'):
            continue
        if name.startswith('_shotcaller_'):
            continue
        try:
            value = getattr(instance, name)
        except Exception as error:
            if _is_context_name(name):
                _log('stronghold context attribute read failed: ' + name + ': ' + str(error))
            continue

        if callable(value):
            if method_count < MAX_CONTEXT_METHODS:
                _log('stronghold context method: ' + name)
                method_count += 1
            if _is_context_name(name) and _is_safe_reader_method(name):
                try:
                    _log_context_value('method result', name, value())
                except Exception as error:
                    _log('stronghold context method read failed: ' + name + ': ' + str(error))
            continue

        if attribute_count < MAX_CONTEXT_ATTRIBUTES:
            _log('stronghold context attribute name: ' + name)
            attribute_count += 1
        if _is_context_name(name):
            _log_context_value('attribute', name, value)


def _should_log_update(instance):
    instance_id = id(instance)
    now = time.time()
    previous = _last_update_log.get(instance_id)
    if previous is not None and now - previous < UPDATE_LOG_INTERVAL_SECONDS:
        return False
    _last_update_log[instance_id] = now
    return True


def _make_watcher_hook(method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('stronghold watcher original failed: ' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise

        try:
            instance_id = id(instance)
            if method_name == 'start':
                _log('stronghold watcher started')
                if instance_id not in _start_context_probed:
                    _start_context_probed.add(instance_id)
                    _probe_watcher_context(instance, 'start')
            elif method_name == 'stop':
                _log('stronghold watcher stopped')
            elif _should_log_update(instance):
                _log('stronghold watcher update')
                if instance_id not in _update_context_probed:
                    _update_context_probed.add(instance_id)
                    _probe_watcher_context(instance, 'first update')
        except Exception as error:
            try:
                _log('stronghold watcher context probe failed: ' + str(error))
            except Exception:
                pass
        return result

    return hooked_method


def _short_text(instance, args):
    parts = [_short_string(instance)]
    try:
        for argument in args[:3]:
            parts.append(_short_string(argument))
    except Exception:
        pass
    return ' | '.join(parts)[:500]


def _make_window_hook(class_name, method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('stronghold window original failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise

        try:
            text = _short_text(instance, args)
            if 'strongholdbattleroomwindow' in text.lower():
                _log('stronghold battle room window detected')
                _log('stronghold battle room window: ' + _short_string(instance, 300))
        except Exception as error:
            try:
                _log('stronghold window inspect failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
        return result

    return hooked_method


def _install_hook(target_class, marker_prefix, class_name, method_name, hook_factory):
    marker_name = marker_prefix + method_name
    try:
        if getattr(target_class, marker_name, False):
            return True
        original_method = getattr(target_class, method_name, None)
        if not callable(original_method):
            return False
        setattr(target_class, method_name,
                hook_factory(class_name, method_name, original_method))
        setattr(target_class, marker_name, True)
        return True
    except Exception as error:
        _log('hook install failed: ' + class_name + '.' + method_name + ': ' + str(error))
        return False


def _install_watcher_hooks():
    try:
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as watcher_module
        watcher_class = getattr(watcher_module, 'StrongholdVehiclesWatcher', None)
        if watcher_class is None:
            _log('stronghold watcher class missing')
            return
        _log('stronghold watcher class: StrongholdVehiclesWatcher')
        for method_name in ('start', 'stop', '_update'):
            _install_hook(
                watcher_class, WATCHER_MARKER_PREFIX,
                'StrongholdVehiclesWatcher', method_name,
                lambda class_name, name, original: _make_watcher_hook(name, original))
    except Exception as error:
        _log('stronghold watcher import failed: ' + str(error))


def _install_window_hooks():
    wulf_window_module = None
    window_impl_module = None
    try:
        import frameworks.wulf.windows_system.window as wulf_window_module
    except Exception as error:
        _log('WULF window import failed: ' + str(error))

    try:
        import gui.impl.pub.window_impl as window_impl_module
    except Exception as error:
        _log('GUI window implementation import failed: ' + str(error))

    try:
        if wulf_window_module is not None:
            window_class = getattr(wulf_window_module, 'Window', None)
            if window_class is not None:
                _install_hook(window_class, WINDOW_MARKER_PREFIX,
                              'frameworks.wulf.windows_system.window.Window',
                              '__init__', _make_window_hook)

        if window_impl_module is not None:
            window_impl_class = getattr(window_impl_module, 'WindowImpl', None)
            if window_impl_class is not None:
                _install_hook(window_impl_class, WINDOW_MARKER_PREFIX,
                              'gui.impl.pub.window_impl.WindowImpl',
                              '__init__', _make_window_hook)
    except Exception as error:
        _log('stronghold window hook setup failed: ' + str(error))


def init():
    _log('loaded')
    _install_watcher_hooks()
    _install_window_hooks()


def fini():
    _log('unloaded')
