"""Prototype 3A: safe Stronghold battle-room entry and exit detection."""


TAG = '[shotcaller]'
WATCHER_MARKER_PREFIX = '_shotcaller_stronghold_watcher_'
WINDOW_MARKER_PREFIX = '_shotcaller_stronghold_window_'
METHOD_HINTS = ('load', 'loaded', 'show', 'create', 'init')
MAX_PROBED_METHODS = 30


def _log(message):
    print(TAG + ' ' + message)


def _log_methods(prefix, class_name, target_class, hints=METHOD_HINTS):
    try:
        count = 0
        for method_name in sorted(dir(target_class)):
            if method_name.startswith('__') and method_name != '__init__':
                continue
            if hints is not None and not any(hint in method_name.lower() for hint in hints):
                continue
            if not callable(getattr(target_class, method_name, None)):
                continue
            _log(prefix + ': ' + class_name + '.' + method_name)
            count += 1
            if count >= MAX_PROBED_METHODS:
                _log(prefix + ' limit reached: ' + class_name)
                break
    except Exception as error:
        _log(prefix + ' inspect failed: ' + class_name + ': ' + str(error))


def _short_text(instance, args):
    parts = []
    try:
        parts.append(str(instance))
    except Exception:
        parts.append('<self unavailable>')

    try:
        for argument in args[:3]:
            try:
                parts.append(str(argument))
            except Exception:
                parts.append('<arg unavailable>')
    except Exception:
        pass

    return ' | '.join(parts)[:500]


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
            text = _short_text(instance, args)
            if 'strongholdbattleroomwindow' in text.lower():
                _log('stronghold battle room window detected')
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
        _log_methods('stronghold watcher method', 'StrongholdVehiclesWatcher',
                     watcher_class, None)

        for method_name in ('start', 'stop'):
            _install_hook(
                watcher_class,
                WATCHER_MARKER_PREFIX,
                'StrongholdVehiclesWatcher',
                method_name,
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

    if wulf_window_module is None and window_impl_module is None:
        return

    try:
        wulf_window_class = None
        if wulf_window_module is not None:
            wulf_window_class = getattr(wulf_window_module, 'Window', None)

        window_impl_class = None
        if window_impl_module is not None:
            window_impl_class = getattr(window_impl_module, 'WindowImpl', None)

        class_candidates = []
        if wulf_window_module is not None:
            class_candidates.extend((
                ('frameworks.wulf.windows_system.window.Window', wulf_window_class),
                ('frameworks.wulf.windows_system.window.PyObjectWindow',
                 getattr(wulf_window_module, 'PyObjectWindow', None)),
            ))
        if window_impl_module is not None:
            class_candidates.extend((
                ('gui.impl.pub.window_impl.Window',
                 getattr(window_impl_module, 'Window', None)),
                ('gui.impl.pub.window_impl.WindowImpl', window_impl_class),
            ))

        for class_name, window_class in class_candidates:
            if window_class is not None:
                _log_methods('window method', class_name, window_class)

        installed_count = 0
        if wulf_window_class is not None:
            if _install_hook(wulf_window_class, WINDOW_MARKER_PREFIX,
                             'frameworks.wulf.windows_system.window.Window',
                             '__init__', _make_window_hook):
                installed_count += 1

        if window_impl_class is not None:
            if _install_hook(window_impl_class, WINDOW_MARKER_PREFIX,
                             'gui.impl.pub.window_impl.WindowImpl',
                             '__init__', _make_window_hook):
                installed_count += 1

        if installed_count == 0:
            _log('no stronghold window hook method found')
    except Exception as error:
        _log('stronghold window import failed: ' + str(error))


def _probe_browser_support():
    try:
        import gui.shared.web_browser
        _log('browser support import ok: gui.shared.web_browser')
    except Exception as error:
        _log('browser support import missing: gui.shared.web_browser: ' + str(error))


def init():
    _log('loaded')
    _install_watcher_hooks()
    _install_window_hooks()
    _probe_browser_support()


def fini():
    _log('unloaded')
