"""Python 2.7 regression coverage for in-place custom history navigation."""
import imp

mod = imp.load_source('shotcaller_navigation_test', 'mod_shotcaller.py')

class Flash(object):
    def __init__(self): self.calls = []
    def as_setHistoryHeader(self, value): self.calls.append(('header', value))
    def as_beginHistoryRows(self): self.calls.append(('begin',))
    def as_addHistoryHeading(self, value): self.calls.append(('heading', value))
    def as_addHistoryVehicle(self, value, battles, wins=-1, ace=False): self.calls.append(('vehicle', value, battles, wins, ace))
    def as_finishHistoryRows(self): self.calls.append(('finish',))
    def as_setMessageState(self, context, title, detail): self.calls.append(('message', context, title, detail))

class View(object):
    def __init__(self): self.flashObject = Flash()

def row(dbid, slot, name):
    return {'dbid': dbid, 'slot_index': slot, 'name': name, 'full_name': name,
            'clan': 'VENUM', 'vehicle_level': 8, 'vehicle_intcd': 1,
            'in_battle': False, 'player_ready': True}

first = row(1, 0, 'First')
second = row(2, 1, 'Second')
mod.ROOM_CONTEXT = mod.ROOM_CONTEXT_STRONGHOLD
mod.CACHE.update({'rows': {1: first, 2: second}, 'order': [1, 2], 'unit_id': 9,
                  'tier': 8, 'resolved_tier': 8, 'generation': 1})
mod.LOOKUPS = {
    1: {'dbid': 1, 'name': 'First', 'status': 'ok', 'vehicles': [{'tank_id': 11, 'name': 'Alpha', 'type': 'heavyTank', 'battles': 3}]},
    2: {'dbid': 2, 'name': 'Second', 'status': 'ok', 'vehicles': [{'tank_id': 22, 'name': 'Bravo', 'type': 'mediumTank', 'battles': 8}]}
}
view = View()
mod.CUSTOM_WINDOW_VIEW = view
mod.PANEL.update({'open': True, 'dbid': 1, 'slot': 0, 'generation': 1,
                  'fingerprint': mod._panel_fingerprint(first, 'ready', mod.LOOKUPS[1]), 'opening': False, 'suppressed_logged': False})
mod._lobby_app = lambda: (_ for _ in ()).throw(AssertionError('loadView must not be needed for active navigation'))

mod._handle_panel_button('next')
assert mod.PANEL['dbid'] == 2
assert view.flashObject.calls[0][0] == 'header' and 'Second' in view.flashObject.calls[0][1]
assert view.flashObject.calls[1] == ('begin',)
assert ('vehicle', u'Bravo', 8, -1, False) in view.flashObject.calls
assert view.flashObject.calls[-1] == ('finish',)

view.flashObject.calls = []
mod._handle_panel_button('previous')
assert mod.PANEL['dbid'] == 1 and ('vehicle', u'Alpha', 3, -1, False) in view.flashObject.calls

# Pending target becomes ready later and refreshes the same view in place.
mod.LOOKUPS.pop(2)
view.flashObject.calls = []
mod._handle_panel_button('next')
assert mod.PANEL['dbid'] == 2 and view.flashObject.calls[-1] == ('finish',)
mod.LOOKUPS[2] = {'dbid': 2, 'name': 'Second', 'status': 'ok', 'vehicles': [{'tank_id': 22, 'name': 'Bravo', 'type': 'mediumTank', 'battles': 8}]}
view.flashObject.calls = []
mod._refresh_panel('lookup')
assert ('vehicle', u'Bravo', 8, -1, False) in view.flashObject.calls

# Removing the selected player chooses a valid remaining player without loading another alias.
mod.CACHE['rows'].pop(2); mod.CACHE['order'] = [1]; view.flashObject.calls = []
mod._refresh_panel('roster')
assert mod.PANEL['dbid'] == 1 and ('vehicle', u'Alpha', 3, -1, False) in view.flashObject.calls
mod.CUSTOM_WINDOW_VIEW = None
assert mod.CUSTOM_WINDOW_VIEW is None
print('navigation in-place refresh test: ok')
