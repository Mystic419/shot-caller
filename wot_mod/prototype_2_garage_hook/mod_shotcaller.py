"""Prototype 2: harmless garage/lobby lifecycle hook for Shot-caller."""


TAG = '[shotcaller]'
_hook_installed = False
_original_initialize = None


def _log(message):
    print(TAG + ' ' + message)


def _garage_initialize_hook(instance, *args, **kwargs):
    result = _original_initialize(instance, *args, **kwargs)
    _log('garage hook fired')
    return result


def _install_garage_hook():
    global _hook_installed
    global _original_initialize

    if _hook_installed:
        return

    try:
        from gui.impl.lobby.hangar.hangar import Hangar

        _original_initialize = Hangar._initialize
        Hangar._initialize = _garage_initialize_hook
        _hook_installed = True
    except Exception as error:
        _log('hook install failed: ' + str(error))


def init():
    _log('loaded')
    _install_garage_hook()


def fini():
    _log('unloaded')
