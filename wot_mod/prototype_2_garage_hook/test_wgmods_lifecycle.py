"""Python 2.7 lifecycle contract coverage for the WGMods review package."""
import imp
import os
import sys
import types

callbacks = []
BigWorld = types.ModuleType('BigWorld')
BigWorld.callback = lambda delay, fn: callbacks.append((delay, fn))
sys.modules['BigWorld'] = BigWorld

# The converter is deliberately available before the import.  A module-scope
# init() call would immediately replace these functions and fail this test.
package_names = ('gui', 'gui.Scaleform', 'gui.Scaleform.daapi',
                 'gui.Scaleform.daapi.view', 'gui.Scaleform.daapi.view.lobby',
                 'gui.Scaleform.daapi.view.lobby.rally')
for name in package_names:
    module = types.ModuleType(name); module.__path__ = []
    sys.modules[name] = module
converter_name = 'gui.Scaleform.daapi.view.lobby.rally.vo_converters'
converter = types.ModuleType(converter_name)
def make_slots(*args, **kwargs): return (True, [])
def make_player(*args, **kwargs): return {}
def make_vehicle(*args, **kwargs): return {}
converter.makeSlotsVOs = make_slots
converter.makePlayerVO = make_player
converter.makeVehicleVO = make_vehicle
converter.makeVehicleBasicVO = make_vehicle
sys.modules[converter_name] = converter

source_path = os.path.join(os.path.dirname(__file__), 'mod_shotcaller.py')
mod = imp.load_source('shotcaller_wgmods_lifecycle_test', source_path)

# Import is passive: it may log, but it neither claims BigWorld nor wraps hooks
# nor queues startup callbacks.
assert not getattr(BigWorld, '_shotcaller_standalone_initialized', False)
assert converter.makeSlotsVOs is make_slots
assert callbacks == []

mod.init()
assert getattr(BigWorld, '_shotcaller_standalone_initialized', False)
assert converter.makeSlotsVOs is not make_slots
assert getattr(converter.makeSlotsVOs, mod.MARK + 'wrapped', False)
installed = converter.makeSlotsVOs

# Stock startup gets one claim. A second call is harmless and cannot register
# another wrapper or schedule another initialization attempt.
mod.init()
assert converter.makeSlotsVOs is installed

source = open(source_path, 'rb').read()
assert b'_log(\'standalone module import started\')' in source
assert b'\ninit()' not in source
assert b'BigWorld.callback(0.0, init)' not in source
assert b'BigWorld.callback(0, init)' not in source
assert b'def _attempt_initialize(attempt):' in source
assert b'_attempt_initialize(next_attempt)' in source
print('wgmods lifecycle test: ok')
