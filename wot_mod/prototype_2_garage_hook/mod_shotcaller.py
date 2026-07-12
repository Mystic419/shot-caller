"""Prototype 3G: safe Stronghold web/browser bridge discovery probe."""


TAG = '[shotcaller]'
BROWSER_MARKER_PREFIX = '_shotcaller_browser_hook_'
BRIDGE_MARKER_PREFIX = '_shotcaller_bridge_hook_'
ROSTER_MARKER_PREFIX = '_shotcaller_light_roster_hook_'
WATCHER_MARKER_PREFIX = '_shotcaller_watcher_hook_'
WINDOW_MARKER_PREFIX = '_shotcaller_window_hook_'
BROWSER_METHODS = ('create', 'createBrowser', 'load', 'show', 'close', 'delete',
                   'onBrowserCreated', 'onBrowserDeleted', '_createBrowser',
                   '_showBrowser', '_deleteBrowser')
BRIDGE_METHODS = ('handle', 'handleCommand', 'onCommand', 'onMessage',
                  'onWebMessage', 'processCommand', 'dispatch', 'invoke',
                  'receive')
ROSTER_METHODS = ('__init__', 'init', 'fini', '_loadUnit', '_unloadUnit')
BROWSER_MODULES = (
    'gui.game_control.browser_controller',
    'gui.Scaleform.daapi.view.lobby.browser',
    'gui.Scaleform.daapi.view.lobby.browser.browser',
    'gui.Scaleform.daapi.view.lobby.browser.web_handlers',
    'gui.shared.event_bus',
    'gui.shared.events',
)
BRIDGE_HINTS = ('web', 'browser', 'handler', 'callback', 'command', 'message',
                'js', 'client', 'receive', 'request', 'response', 'invoke',
                'event')
IMPORTANT_BRIDGE_HINTS = ('roster', 'member', 'player', 'slot', 'vehicle',
                          'unit', 'commander', 'legionary', 'invite',
                          'battleroom', 'detachment', 'division')
VIEW_ALIASES = ('strongholdview', 'strongholdbattleroomwindow',
                'browserwindowmodal', 'fortvehicleselectpopover',
                'forttifications/strongholdsendsinviteswindow')
MAX_MODULE_CANDIDATES = 30
MAX_BRIDGE_HOOKS = 10
MAX_FIRST_BRIDGE_LOGS = 100
_bridge_call_count = 0


def _log(message):
    print(TAG + ' ' + message)


def _short_text(value, limit=1000):
    try:
        return str(value)[:limit]
    except Exception:
        return '<string unavailable>'


def _combined_text(instance, args, kwargs, limit=1000):
    parts = [_short_text(instance, limit)]
    try:
        parts.extend(_short_text(argument, limit) for argument in args[:5])
    except Exception:
        pass
    try:
        parts.append(_short_text(kwargs, limit))
    except Exception:
        pass
    return ' | '.join(parts)[:limit]


def _contains_any(text, hints):
    text_lower = text.lower()
    return any(hint in text_lower for hint in hints)


def _log_module_candidates(module_name, module):
    try:
        count = 0
        for name in sorted(dir(module)):
            if name.startswith('_'):
                continue
            if not _contains_any(name, BRIDGE_HINTS):
                continue
            _log('web bridge candidate class/function: ' + module_name + '.' + name)
            count += 1
            if count >= MAX_MODULE_CANDIDATES:
                break
    except Exception as error:
        _log('web bridge candidate inspect failed: ' + module_name + ': ' + str(error))


def _make_browser_hook(class_name, method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('browser hook original failed: ' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise
        try:
            _log('browser hook fired: ' + method_name)
            text = _combined_text(instance, args, kwargs, 1000)
            if _contains_any(text, ('wgsh-wotus-static', 'battlerooms', 'units',
                                    'stronghold', 'invites', 'battle')):
                _log('browser url: ' + text[:1000])
        except Exception as error:
            try:
                _log('browser hook inspect failed: ' + method_name + ': ' + str(error))
            except Exception:
                pass
        return result
    return hooked_method


def _make_bridge_hook(class_name, method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        global _bridge_call_count
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('web bridge original failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise
        try:
            _bridge_call_count += 1
            text = _combined_text(instance, args, kwargs, 1000)
            if _bridge_call_count <= MAX_FIRST_BRIDGE_LOGS or _contains_any(text, IMPORTANT_BRIDGE_HINTS):
                _log('web bridge candidate: ' + class_name + '.' + method_name + ' ' + text[:1000])
        except Exception as error:
            try:
                _log('web bridge inspect failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
        return result
    return hooked_method


def _make_light_roster_hook(method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('roster hook original failed: ' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise
        _log('roster hook fired: ' + method_name)
        return result
    return hooked_method


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
        _log('stronghold watcher ' + ('started' if method_name == 'start' else 'stopped'))
        return result
    return hooked_method


def _make_window_hook(class_name, method_name, original_method):
    def hooked_method(instance, *args, **kwargs):
        try:
            result = original_method(instance, *args, **kwargs)
        except Exception as error:
            try:
                _log('window hook original failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
            raise
        try:
            text = _combined_text(instance, args, kwargs, 1000)
            text_lower = text.lower()
            for alias in VIEW_ALIASES:
                if alias in text_lower:
                    _log('stronghold view detected: ' + text[:500])
                    break
            if ('http' in text_lower or 'wgsh-wotus-static' in text_lower) and _contains_any(
                    text, ('battlerooms', '/units/create', '/units/', 'skirmish',
                           'detachment', 'battle', 'stronghold')):
                _log('stronghold browser url detected: ' + text[:1000])
        except Exception as error:
            try:
                _log('window hook inspect failed: ' + class_name + '.' + method_name + ': ' + str(error))
            except Exception:
                pass
        return result
    return hooked_method


def _install_hook(target, marker_prefix, class_name, method_name, hook_factory):
    marker_name = marker_prefix + method_name
    try:
        if getattr(target, marker_name, False):
            return False
        original_method = getattr(target, method_name, None)
        if not callable(original_method):
            return False
        setattr(target, method_name, hook_factory(class_name, method_name, original_method))
        setattr(target, marker_name, True)
        return True
    except Exception as error:
        _log('hook install failed: ' + class_name + '.' + method_name + ': ' + str(error))
        return False


def _install_light_roster_hooks():
    try:
        import gui.prb_control.entities.stronghold.unit.entity as entity_module
        entity_class = getattr(entity_module, 'StrongholdBrowserEntity', None)
        if entity_class is None:
            return
        _log('stronghold browser entity class: StrongholdBrowserEntity')
        for method_name in ROSTER_METHODS:
            _install_hook(entity_class, ROSTER_MARKER_PREFIX,
                          'StrongholdBrowserEntity', method_name,
                          lambda class_name, name, original: _make_light_roster_hook(name, original))
    except Exception as error:
        _log('stronghold browser entity import failed: ' + str(error))


def _install_watcher_hooks():
    try:
        import gui.prb_control.entities.stronghold.unit.vehicles_watcher as watcher_module
        watcher_class = getattr(watcher_module, 'StrongholdVehiclesWatcher', None)
        if watcher_class is None:
            return
        for method_name in ('start', 'stop'):
            _install_hook(watcher_class, WATCHER_MARKER_PREFIX,
                          'StrongholdVehiclesWatcher', method_name,
                          lambda class_name, name, original: _make_watcher_hook(name, original))
    except Exception as error:
        _log('stronghold watcher import failed: ' + str(error))


def _install_window_hooks():
    modules = ()
    try:
        import frameworks.wulf.windows_system.window as wulf_window_module
        modules = modules + (('frameworks.wulf.windows_system.window.Window',
                              getattr(wulf_window_module, 'Window', None)),)
    except Exception as error:
        _log('WULF window import missing: ' + str(error))
    try:
        import gui.impl.pub.window_impl as window_impl_module
        modules = modules + (('gui.impl.pub.window_impl.WindowImpl',
                              getattr(window_impl_module, 'WindowImpl', None)),)
    except Exception as error:
        _log('GUI window implementation import missing: ' + str(error))
    for class_name, window_class in modules:
        if window_class is not None:
            _install_hook(window_class, WINDOW_MARKER_PREFIX, class_name,
                          '__init__', _make_window_hook)


def _probe_browser_modules():
    imported_modules = []
    try:
        import gui.game_control as game_control_module
        browser_controller = getattr(game_control_module, 'BrowserController', None)
        if browser_controller is None:
            raise AttributeError('BrowserController not found')
        _log('import ok: gui.game_control.BrowserController')
        imported_modules.append(('gui.game_control.BrowserController', browser_controller))
        for method_name in BROWSER_METHODS:
            _install_hook(browser_controller, BROWSER_MARKER_PREFIX,
                          'BrowserController', method_name, _make_browser_hook)
    except Exception as error:
        _log('import missing: gui.game_control.BrowserController: ' + str(error))

    for module_name in BROWSER_MODULES:
        try:
            module = __import__(module_name, fromlist=['*'])
            _log('import ok: ' + module_name)
            imported_modules.append((module_name, module))
            if module_name == 'gui.game_control.browser_controller':
                browser_controller = getattr(module, 'BrowserController', None)
                if browser_controller is not None:
                    _log('browser controller found: gui.game_control.browser_controller.BrowserController')
                    for method_name in BROWSER_METHODS:
                        _install_hook(browser_controller, BROWSER_MARKER_PREFIX,
                                      'BrowserController', method_name,
                                      _make_browser_hook)
        except Exception as error:
            _log('import missing: ' + module_name + ': ' + str(error))

    return imported_modules


def _install_bridge_hooks(imported_modules):
    installed_count = 0
    for module_name, module in imported_modules:
        _log_module_candidates(module_name, module)
        try:
            for name in sorted(dir(module)):
                if installed_count >= MAX_BRIDGE_HOOKS:
                    return
                if name.startswith('_') or not _contains_any(name, BRIDGE_HINTS):
                    continue
                target = getattr(module, name, None)
                if target is None:
                    continue
                for method_name in BRIDGE_METHODS:
                    if installed_count >= MAX_BRIDGE_HOOKS:
                        return
                    if _install_hook(target, BRIDGE_MARKER_PREFIX,
                                     module_name + '.' + name, method_name,
                                     _make_bridge_hook):
                        installed_count += 1
        except Exception as error:
            _log('web bridge hook inspect failed: ' + module_name + ': ' + str(error))


def init():
    _log('loaded')
    _install_light_roster_hooks()
    _install_watcher_hooks()
    _install_window_hooks()
    _install_bridge_hooks(_probe_browser_modules())


def fini():
    _log('unloaded')
