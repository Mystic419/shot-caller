"""Prototype 2D: read-only modern WULF/Gameface Hangar discovery probe."""


TAG = '[shotcaller]'
MODULE_CANDIDATES = (
    'gui.impl.lobby.hangar',
    'gui.impl.lobby.hangar.random_hangar',
    'gui.impl.lobby.hangar.presenters',
    'gui.impl.lobby.hangar.presenters.random_hangar',
    'gui.impl.lobby.hangar.presenters.teaser_presenter',
    'gui.impl.pub.window_impl',
    'gui.impl.pub.main_window',
    'frameworks.wulf.windows_system.window',
    'gui.lobby_state_machine.lobby_state_machine',
    'gui.lobby_state_machine.states',
)
NAME_HINTS = ('hangar', 'random', 'window', 'state', 'load', 'loaded',
              'initialize', 'enter', 'create')
MAX_CANDIDATES_PER_MODULE = 30


def _log(message):
    print(TAG + ' ' + message)


def _log_module_candidates(module_name, module):
    try:
        candidate_count = 0
        for name in sorted(dir(module)):
            if name.startswith('_'):
                continue
            name_lower = name.lower()
            if not any(hint in name_lower for hint in NAME_HINTS):
                continue
            _log('candidate: ' + module_name + '.' + name)
            candidate_count += 1
            if candidate_count >= MAX_CANDIDATES_PER_MODULE:
                _log('candidate limit reached: ' + module_name)
                break
    except Exception as error:
        _log('inspect failed: ' + module_name + ': ' + str(error))


def _probe_module(module_name):
    try:
        module = __import__(module_name, fromlist=['*'])
        _log('import ok: ' + module_name)
        _log_module_candidates(module_name, module)
    except Exception as error:
        _log('import missing: ' + module_name + ': ' + str(error))


def _run_modern_hangar_probe():
    for module_name in MODULE_CANDIDATES:
        _probe_module(module_name)


def init():
    _log('loaded')
    try:
        _run_modern_hangar_probe()
    except Exception as error:
        _log('probe failed: ' + str(error))


def fini():
    _log('unloaded')
