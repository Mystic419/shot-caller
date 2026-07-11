"""Prototype 3C: safe Stronghold entity, unit, and roster discovery probe."""


TAG = '[shotcaller]'
WATCHER_MARKER_PREFIX = '_shotcaller_stronghold_watcher_'
WINDOW_MARKER_PREFIX = '_shotcaller_stronghold_window_'
NAME_HINTS = ('stronghold', 'unit', 'roster', 'member', 'commander', 'player',
              'slot', 'division', 'level', 'tier', 'vehicle', 'settings',
              'state', 'entity', 'ctx', 'request')
MUTATING_HINTS = ('join', 'leave', 'set', 'assign', 'kick', 'invite', 'ready',
                  'select', 'change', 'update', 'start', 'stop', 'create',
                  'destroy', 'clear')
MAX_MODULE_CANDIDATES = 30
MAX_OBJECT_ATTRIBUTES = 30
_entity_probe_started = set()

MODULE_CANDIDATES = (
    'gui.prb_control',
    'gui.prb_control.dispatcher',
    'gui.prb_control.entities',
    'gui.prb_control.entities.stronghold',
    'gui.prb_control.entities.stronghold.unit',
    'gui.prb_control.entities.stronghold.unit.entity',
    'gui.prb_control.entities.stronghold.unit.actions_handler',
    'gui.prb_control.entities.stronghold.unit.permissions',
    'gui.prb_control.entities.stronghold.unit.ctx',
    'gui.prb_control.entities.base.unit.entity',
    'gui.prb_control.entities.base.unit.ctx',
    'gui.prb_control.items',
    'gui.prb_control.items.unit_items',
    'gui.shared.utils.requesters',
)


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


def _is_interesting_name(name):
    name_lower = name.lower()
    return any(hint in name_lower for hint in NAME_HINTS)


def _is_safe_getter_name(name):
    name_lower = name.lower()
    if any(hint in name_lower for hint in MUTATING_HINTS):
        return False
    return name_lower.startswith('get') or name_lower.startswith('is') or name_lower.startswith('has')


def _log_probe_value(name, value):
    _log('stronghold probe value: ' + name + ' type=' + type(value).__name__ +
         ' repr=' + _short_repr(value))


def _log_module_candidates(module_name, module):
    try:
        count = 0
        for name in sorted(dir(module)):
            if name.startswith('_'):
                continue
            if not _is_interesting_name(name):
                continue
            _log('import candidate: ' + module_name + '.' + name)
            count += 1
            if count >= MAX_MODULE_CANDIDATES:
                _log('import candidate limit reached: ' + module_name)
                break
    except Exception as error:
        _log('import inspect failed: ' + module_name + ': ' + str(error))


def _probe_module_imports():
    for module_name in MODULE_CANDIDATES:
        try:
            module = __import__(module_name, fromlist=['*'])
            _log('import ok: ' + module_name)
            _log_module_candidates(module_name, module)
        except Exception as error:
            _log('import missing: ' + module_name + ': ' + str(error))

    try:
        import gui.shared.utils.requesters as requesters_module
        requester_class = getattr(requesters_module, 'StrongholdRequester', None)
        if requester_class is None:
            raise AttributeError('StrongholdRequester not found')
        _log('import ok: gui.shared.utils.requesters.StrongholdRequester')
        _log_module_candidates('gui.shared.utils.requesters.StrongholdRequester', requester_class)
    except Exception as error:
        _log('import missing: gui.shared.utils.requesters.StrongholdRequester: ' + str(error))


def _inspect_probe_object(name, value):
    _log_probe_value(name, value)

    try:
        if isinstance(value, dict):
            keys = sorted(value.keys())[:MAX_OBJECT_ATTRIBUTES]
            _log('stronghold probe keys: ' + name + ' ' + _short_repr(keys))
            return
    except Exception as error:
        _log('stronghold probe keys failed: ' + name + ': ' + str(error))

    try:
        count = 0
        for attribute_name in sorted(dir(value)):
            if attribute_name.startswith('_'):
                continue
            if not _is_interesting_name(attribute_name):
                continue
            _log('stronghold probe attribute: ' + name + '.' + attribute_name)
            count += 1
            if count >= MAX_OBJECT_ATTRIBUTES:
                break
    except Exception as error:
        _log('stronghold probe attributes failed: ' + name + ': ' + str(error))


def _call_safe_getter(owner, owner_name, getter_name):
    try:
        getter = getattr(owner, getter_name, None)
        if not callable(getter) or not _is_safe_getter_name(getter_name):
            return None
        value = getter()
        _inspect_probe_object(owner_name + '.' + getter_name + '()', value)
        return value
    except Exception as error:
        _log('stronghold probe getter failed: ' + owner_name + '.' + getter_name + ': ' + str(error))
        return None


def _probe_entity(entity, entity_name):
    if entity is None:
        return
    _inspect_probe_object(entity_name, entity)
    for getter_name in ('getUnitFullData', 'getUnitData', 'getRoster',
                        'getPlayerInfo', 'getPlayers', 'getMembers',
                        'getCommanderDBID'):
        _call_safe_getter(entity, entity_name, getter_name)


def _probe_prb_getters():
    try:
        import gui.prb_control.prb_getters as prb_getters
        _log('import ok: gui.prb_control.prb_getters')
        for getter_name in ('getClientPrebattle', 'getPrebattleType',
                            'getPrebattleSettings', 'getUnitMgr',
                            'getControlSettings'):
            _call_safe_getter(prb_getters, 'prb_getters', getter_name)
    except Exception as error:
        _log('stronghold probe prb_getters failed: ' + str(error))


def _probe_dispatcher_entity():
    dispatcher_object = None
    try:
        import gui.prb_control as prb_control_module
        import gui.prb_control.dispatcher as dispatcher_module
        from dependencies import dependency

        dispatcher_interface = getattr(prb_control_module, 'IPrbDispatcher', None)
        if dispatcher_interface is None:
            dispatcher_interface = getattr(dispatcher_module, 'IPrbDispatcher', None)
        if dispatcher_interface is not None:
            dispatcher_object = dependency.instance(dispatcher_interface)
            _inspect_probe_object('dependency.instance(IPrbDispatcher)', dispatcher_object)
    except Exception as error:
        _log('stronghold probe dispatcher dependency failed: ' + str(error))

    if dispatcher_object is not None:
        _probe_entity(_call_safe_getter(dispatcher_object, 'dispatcher', 'getEntity'),
                      'dispatcher.getEntity()')


def _run_entity_probe(instance):
    instance_id = id(instance)
    if instance_id in _entity_probe_started:
        return
    _entity_probe_started.add(instance_id)
    try:
        _probe_prb_getters()
        _probe_dispatcher_entity()
    except Exception as error:
        _log('stronghold entity probe failed: ' + str(error))


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
                _run_entity_probe(instance)
            else:
                _log('stronghold watcher stopped')
        except Exception as error:
            try:
                _log('stronghold entity probe failed: ' + str(error))
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


def _install_hook(target_class, marker_prefix, class_name, method_name, hook_factory):
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
        _log('stronghold watcher class: StrongholdVehiclesWatcher')
        for method_name in ('start', 'stop'):
            _install_hook(watcher_class, WATCHER_MARKER_PREFIX,
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
    _probe_module_imports()
    _install_watcher_hooks()
    _install_window_hooks()


def fini():
    _log('unloaded')
