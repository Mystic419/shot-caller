"""Prototype 2B: safe garage/lobby import and hook discovery for Shot-caller."""

import sys


TAG = '[shotcaller]'
MODULE_CANDIDATES = (
    'gui',
    'gui.Scaleform',
    'gui.Scaleform.daapi',
    'gui.Scaleform.daapi.view',
    'gui.Scaleform.daapi.view.lobby',
    'gui.Scaleform.daapi.view.lobby.hangar',
    'gui.impl',
    'gui.impl.lobby',
    'gui.impl.lobby.hangar',
    'gui.shared',
    'gui.app_loader',
)
LIFECYCLE_NAMES = ('_initialize', '_populate', 'onEnter', 'onLeave')
CLASS_NAMES = ('Hangar', 'HangarView', 'LobbyView')


def _log(message):
    print(TAG + ' ' + message)


def _log_lifecycle_candidates(module_name, module):
    for lifecycle_name in LIFECYCLE_NAMES:
        lifecycle = getattr(module, lifecycle_name, None)
        if callable(lifecycle):
            _log('hook candidate: ' + module_name + '.' + lifecycle_name)

    for class_name in CLASS_NAMES:
        candidate_class = getattr(module, class_name, None)
        if candidate_class is None:
            continue
        _log('class candidate: ' + module_name + '.' + class_name)
        for lifecycle_name in LIFECYCLE_NAMES:
            lifecycle = getattr(candidate_class, lifecycle_name, None)
            if callable(lifecycle):
                _log('hook candidate: ' + module_name + '.' + class_name + '.' + lifecycle_name)


def _probe_module(module_name):
    try:
        module = __import__(module_name, fromlist=['*'])
        _log('import ok: ' + module_name)
        _log_lifecycle_candidates(module_name, module)
    except Exception:
        _log('import missing: ' + module_name)


def _log_environment():
    _log('python version: ' + sys.version.replace('\n', ' '))

    try:
        import BigWorld
        _log('BigWorld import: ok')
    except Exception:
        _log('BigWorld import: missing')

    try:
        import dependencies
        _log('dependencies import: ok')
    except Exception:
        _log('dependencies import: missing')


def _run_import_probe():
    for module_name in MODULE_CANDIDATES:
        _probe_module(module_name)


def init():
    _log('loaded')
    try:
        _log_environment()
        _run_import_probe()
    except Exception as error:
        _log('probe failed: ' + str(error))


def fini():
    _log('unloaded')
