"""Prototype 3D: safe Stronghold entity lifecycle and data discovery hooks."""


TAG = '[shotcaller]'
ENTITY_MARKER_PREFIX = '_shotcaller_stronghold_entity_hook_'
WATCHER_MARKER_PREFIX = '_shotcaller_stronghold_watcher_'
WINDOW_MARKER_PREFIX = '_shotcaller_stronghold_window_'
ENTITY_NAME_HINTS = ('unit', 'roster', 'member', 'player', 'slot', 'vehicle',
                     'settings', 'state', 'commander', 'stats')
VALUE_NAME_HINTS = ('unit', 'full', 'roster', 'member', 'player', 'slot',
                    'vehicle', 'account', 'dbid', 'name', 'tier', 'level',
                    'division')
MUTATING_HINTS = ('set', 'change', 'join', 'leave', 'assign', 'kick',
                  'invite', 'ready', 'select', 'start', 'stop', 'create',
                  'destroy', 'clear', 'update')
METHOD_HINTS = ('init', 'fini', 'enter', 'exit', 'unit', 'roster', 'member',
                'player', 'slot', 'vehicle', 'settings', 'state', 'update',
                'data', 'stats', 'commander')
ENTITY_METHOD_CANDIDATES = (
    '__init__', 'init', 'fini', 'leave', '_createActionsHandler',
    '_createPermissions', '_createVehiclesWatcher', '_createStats',
    '_createSettings', '_onUnitChanged', '_onUnitPlayerStateChanged',
    '_onUnitPlayerOnlineStatusChanged', '_onUnitPlayerAdded',
    '_onUnitPlayerRemoved', '_onUnitRosterChanged', '_onUnitSettingChanged',
    '_onUnitVehiclesChanged',
)
MAX_ENTITY_HOOKS_PER_CLASS = 6
MAX_DEEP_INSPECTIONS_PER_HOOK = 3
MAX_ENTITY_ATTRIBUTES = 30
MAX_ENTITY_GETTERS = 20
_entity_hook_fire_counts = {}


def _log(message):
    print(TAG + ' ' + message)


def _short_repr(value, limit=300):
    try:
        return repr(value)[:limit]
    except Exception:
        return '<repr unavailable>'


def _short_string(value, limit=300):
    try:
        return str(value)[:limit]
    except Exception:
        return '<string unavailable>'


def _matches_hints(name, hints):
    name_lower = name.lower()
    return any(hint in name_lower for hint in hints)


def _is_safe_getter_name(name):
    name_lower = name.lower()
    if any(hint in name_lower for hint in MUTATING_HINTS):
        return False
    return (name_lower.startswith('get') or name_lower.startswith('is') or
            name_lower.startswith('has') or name_lower.startswith('can'))


def _inspect_value(class_name, value_name, value):
    _log('stronghold entity value: ' + class_name + '.' + value_name +
         ' type=' + type(value).__name__ + ' repr=' + _short_repr(value))
    try:
        if isinstance(value, dict):
            _log('stronghold entity value keys: ' + class_name + '.' +
                 value_name + ' ' + _short_repr(sorted(value.keys())[:MAX_ENTITY_ATTRIBUTES]))
            return
        if isinstance(value, (list, tuple)):
            _log('stronghold entity value len: ' + class_name + '.' +
                 value_name + ' ' + str(len(value)))
            return
    except Exception as error:
        _log('stronghold entity value inspect failed: ' + class_name + '.' +
             value_name + ': ' + str(error))

    try:
        count = 0
        for attribute_name in sorted(dir(value)):
            if attribute_name.startswith('_'):
                continue
            if not _matches_hints(attribute_name, VALUE_NAME_HINTS):
                continue
            _log('stronghold entity value attribute: ' + class_name + '.' +
                 value_name + '.' + attribute_name)
            count += 1
            if count >= MAX_ENTITY_ATTRIBUTES:
                break
    except Exception as error:
        _log('stronghold entity value attributes failed: ' + class_name + '.' +
             value_name + ': ' + str(error))


def _inspect_entity_instance(class_name, instance):
    _log('stronghold entity class: ' + instance.__class__.__name__)
    _log('stronghold entity self: ' + _short_repr(instance))
    try:
        names = sorted(dir(instance))
    except Exception as error:
        _log('stronghold entity dir failed: ' + class_name + ': ' + str(error))
        return

    attribute_count = 0
    getter_count = 0
    for name in names:
        if name.startswith('__') or name.startswith('_shotcaller_'):
            continue
        if not _matches_hints(name, ENTITY_NAME_HINTS):
            continue
        try:
            value = getattr(instance, name)
        except Exception as error:
            _log('stronghold entity attr read failed: ' + class_name + '.' +
                 name + ': ' + str(error))
            continue

        if callable(value):
            _log('stronghold entity method: ' + class_name + '.' + name)
            if getter_count < MAX_ENTITY_GETTERS and _is_safe_getter_name(name):
                getter_count += 1
                try:
                    result = value()
                    _inspect_value(class_name, name + '()', result)
                except Exception as error:
                    _log('stronghold entity getter failed: ' + class_name + '.' +
                         name + ': ' + str(error))
            continue

        if attribute_count < MAX_ENTITY_ATTRIBUTES:
            attribute_count += 1
            _inspect_value(class_name, name, value)


def _make_entity_hook(class_name, method_name, original_method):
    hook_key = class_name + '.' + method_name

    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('stronghold entity original failed: ' + hook_key + ': ' + str(error))
            except Exception:
                pass
            raise

        try:
            _log('stronghold entity hook fired: ' + hook_key)
            fire_count = _entity_hook_fire_counts.get(hook_key, 0) + 1
            _entity_hook_fire_counts[hook_key] = fire_count
            if fire_count <= MAX_DEEP_INSPECTIONS_PER_HOOK:
                _inspect_entity_instance(class_name, instance)
        except Exception as error:
            try:
                _log('stronghold entity inspect failed: ' + hook_key + ': ' + str(error))
            except Exception:
                pass
        return result

    return hooked_method


def _install_entity_hook(entity_class, class_name, method_name):
    marker_name = ENTITY_MARKER_PREFIX + method_name
    try:
        if getattr(entity_class, marker_name, False):
            return True
        original_method = getattr(entity_class, method_name, None)
        if not callable(original_method):
            return False
        setattr(entity_class, method_name,
                _make_entity_hook(class_name, method_name, original_method))
        setattr(entity_class, marker_name, True)
        return True
    except Exception as error:
        _log('stronghold entity hook install failed: ' + class_name + '.' +
             method_name + ': ' + str(error))
        return False


def _inspect_and_install_entity_hooks():
    try:
        import gui.prb_control.entities.stronghold.unit.entity as entity_module
        for class_name in ('StrongholdEntity', 'StrongholdBrowserEntity'):
            entity_class = getattr(entity_module, class_name, None)
            if entity_class is None:
                _log('stronghold entity class missing: ' + class_name)
                continue

            _log('stronghold entity class: ' + class_name)
            try:
                for method_name in sorted(dir(entity_class)):
                    if method_name.startswith('__') and method_name != '__init__':
                        continue
                    if not _matches_hints(method_name, METHOD_HINTS):
                        continue
                    if callable(getattr(entity_class, method_name, None)):
                        _log('stronghold entity method: ' + class_name + '.' + method_name)
            except Exception as error:
                _log('stronghold entity method inspect failed: ' + class_name +
                     ': ' + str(error))

            installed_count = 0
            for method_name in ENTITY_METHOD_CANDIDATES:
                if installed_count >= MAX_ENTITY_HOOKS_PER_CLASS:
                    break
                if _install_entity_hook(entity_class, class_name, method_name):
                    installed_count += 1
    except Exception as error:
        _log('stronghold entity import failed: ' + str(error))


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
            if method_name == 'start':
                _log('stronghold watcher started')
            else:
                _log('stronghold watcher stopped')
        except Exception:
            pass
        return result
    return hooked_method


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
            text = _short_string(instance) + ' | ' + ' | '.join(_short_string(arg) for arg in args[:3])
            text_lower = text.lower()
            if 'strongholdbattleroomwindow' in text_lower:
                _log('stronghold battle room window detected')
                _log('stronghold battle room window: ' + _short_string(instance, 300))
            if 'wgsh-wotus-static' in text_lower or 'battlerooms' in text_lower:
                _log('stronghold browser url detected: ' + text[:300])
        except Exception as error:
            try:
                _log('stronghold window inspect failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
        return result
    return hooked_method


def _install_generic_hook(target_class, marker_prefix, class_name, method_name, hook_factory):
    marker_name = marker_prefix + method_name
    try:
        if getattr(target_class, marker_name, False):
            return True
        original_method = getattr(target_class, method_name, None)
        if not callable(original_method):
            return False
        setattr(target_class, method_name, hook_factory(class_name, method_name, original_method))
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
        for method_name in ('start', 'stop'):
            _install_generic_hook(watcher_class, WATCHER_MARKER_PREFIX,
                                  'StrongholdVehiclesWatcher', method_name,
                                  lambda class_name, name, original: _make_watcher_hook(name, original))
    except Exception as error:
        _log('stronghold watcher import failed: ' + str(error))


def _install_window_hooks():
    window_module = None
    window_impl_module = None
    try:
        import frameworks.wulf.windows_system.window as window_module
    except Exception as error:
        _log('WULF window import failed: ' + str(error))
    try:
        import gui.impl.pub.window_impl as window_impl_module
    except Exception as error:
        _log('GUI window implementation import failed: ' + str(error))
    try:
        if window_module is not None:
            window_class = getattr(window_module, 'Window', None)
            if window_class is not None:
                _install_generic_hook(window_class, WINDOW_MARKER_PREFIX,
                                      'frameworks.wulf.windows_system.window.Window',
                                      '__init__', _make_window_hook)
        if window_impl_module is not None:
            window_impl_class = getattr(window_impl_module, 'WindowImpl', None)
            if window_impl_class is not None:
                _install_generic_hook(window_impl_class, WINDOW_MARKER_PREFIX,
                                      'gui.impl.pub.window_impl.WindowImpl',
                                      '__init__', _make_window_hook)
    except Exception as error:
        _log('stronghold window hook setup failed: ' + str(error))


def init():
    _log('loaded')
    _inspect_and_install_entity_hooks()
    _install_watcher_hooks()
    _install_window_hooks()


def fini():
    _log('unloaded')
