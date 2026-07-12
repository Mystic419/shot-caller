"""Prototype 3L-repair: narrow, read-only Skirmish converter probe."""
import re

TAG = '[shotcaller]'
MARK = '_shotcaller_3l_safe_'
SENSITIVE = re.compile(r"(?i)(access_token|token2?|session|auth|password|secret)(\s*['\"]?\s*[:=]\s*['\"]?)([^,}\]\s'\"]+)")
MODULES = ('gui.Scaleform.daapi.view.lobby.rally',
           'gui.Scaleform.daapi.view.lobby.rally.data_providers',
           'gui.Scaleform.daapi.view.lobby.rally.vo_converters',
           'gui.Scaleform.daapi.view.lobby.strongholds',
           'gui.Scaleform.daapi.view.lobby.fortifications')
CONVERTER_MODULE = 'gui.Scaleform.daapi.view.lobby.rally.vo_converters'
CONVERTERS = ('getUnitRosterData', 'getUnitRosterModel', 'makeSortiePlayerVO',
              'makePlayerVO', 'makeUnitRosterVO', 'makeSlotsVOs',
              'makeVehicleVO', 'makeVehicleBasicVO', 'makeFortClanBattleRoomVO')
WAITING = ('processRequest', 'stopRequest',
           '_BaseExternalUnitWaitingManager__processResponse')
HINTS = ('name','dbid','databaseid','account','clan','rating','vehicle',
         'vehtypecd','slot','member','roster','candidate','volunteer',
         'commander','legionary','ready','battle')

def _log(text):
    print(TAG + ' ' + text)

def _text(value, limit=4000):
    try: return SENSITIVE.sub(r'\1\2***MASKED***', str(value)[:limit])
    except Exception: return '<unavailable>'

def _interesting(value):
    return any(word in _text(value, 4000).lower() for word in HINTS)

def _log_value(label, value):
    """One-level, bounded payload logging; never touches the original value."""
    if not _interesting(value): return
    _log(label + ': type=' + type(value).__name__ + ' repr=' + _text(value))
    if isinstance(value, (list, tuple)):
        _log(label + ' len=' + str(len(value)))
        for index, row in enumerate(value[:20]):
            _log(label + ' row=' + str(index) + ' type=' + type(row).__name__ + ' data=' + _text(row, 4000))
    elif isinstance(value, dict):
        _log(label + ' len=' + str(len(value)) + ' keys=' + _text(value.keys(), 1000))
        for key, row in list(value.items())[:20]:
            _log(label + ' entry=' + _text(key, 200) + ' type=' + type(row).__name__ + ' data=' + _text(row, 4000))

def _converter_hook(name, original):
    def hook(*args, **kwargs):
        # Let the exact client function fail/succeed precisely as it did before.
        result = original(*args, **kwargs)
        try:
            _log('converter hook fired: ' + name)
            _log_value('converter args', {'args': args, 'kwargs': kwargs})
            _log_value('converter result', result)
        except Exception:
            pass
        return result
    setattr(hook, MARK + 'wrapped', True)
    return hook

def _waiting_hook(name, original):
    def hook(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            if name.endswith('__processResponse'):
                _log('waiting response hook fired')
                _log_value('waiting response payload', {'args': args, 'kwargs': kwargs})
        except Exception:
            pass
        return result
    setattr(hook, MARK + 'wrapped', True)
    return hook

def _discover():
    for module_name in MODULES:
        try:
            module = __import__(module_name, fromlist=['*'])
            _log('skirmish ui import ok: ' + module_name)
        except Exception:
            _log('skirmish ui import missing: ' + module_name)
            continue
        for name in dir(module):
            if any(word in name.lower() for word in HINTS):
                _log('skirmish ui candidate: ' + module_name + '.' + name)

def _install_converters():
    count = 0
    try:
        module = __import__(CONVERTER_MODULE, fromlist=['*'])
    except Exception as error:
        _log('converter import failed: ' + _text(error)); return count
    for name in CONVERTERS:
        target = CONVERTER_MODULE + '.' + name
        try:
            original = getattr(module, name, None)
            if not callable(original):
                _log('unsafe patch skipped: ' + target); continue
            if getattr(original, MARK + 'wrapped', False): continue
            setattr(module, name, _converter_hook(name, original)); count += 1
        except Exception as error:
            _log('unsafe patch skipped: ' + target + ' (' + _text(error) + ')')
    return count

def _install_waiting_manager():
    try:
        import gui.prb_control.entities.stronghold.unit.entity as entity
        cls = getattr(entity, 'BaseExternalUnitWaitingManager', None)
        if cls is None: return
        for name in WAITING:
            target = 'BaseExternalUnitWaitingManager.' + name
            # A direct __dict__ lookup prevents wrapping inherited/global methods.
            if name not in cls.__dict__:
                _log('unsafe patch skipped: ' + target); continue
            original = cls.__dict__[name]
            if not callable(original) or getattr(original, MARK + 'wrapped', False):
                _log('unsafe patch skipped: ' + target); continue
            setattr(cls, name, _waiting_hook(name, original))
    except Exception as error:
        _log('waiting manager import failed: ' + _text(error))

def _startup_check():
    try:
        import gui.Scaleform.daapi.view.lobby as lobby
        _log('lobby getViewSettings intact: ' + str(callable(getattr(lobby, 'getViewSettings', None))))
    except Exception as error:
        _log('lobby getViewSettings intact: False (' + _text(error) + ')')

def init():
    _log('loaded')
    _startup_check()
    _discover()
    count = _install_converters()
    _install_waiting_manager()
    _log('safe converter hooks installed: ' + str(count))

def fini():
    _log('unloaded')
