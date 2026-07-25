"""Python 2.7 regression check for sparse entity platoon snapshots."""
import imp

mod = imp.load_source('shotcaller_precedence_test', 'mod_shotcaller.py')

converter = {
    'dbid': 1001921023, 'vehicle_intcd': 9521, 'vehicle_level': 8,
    'vehicle_name': 'T-832', 'vehicle_short_name': 'T-832', 'vehicle_internal_name': 'T-832',
    'vehicle_type': 'heavyTank', 'vehicle_nation_id': 1,
    'player_ready': True, 'vehicle_ready': True, 'player_status': 2,
    'name': 'tester', 'full_name': 'tester', 'clan': 'TAG', 'rating': 1,
    'slot_index': 0, 'commander': True, 'is_current_user': True
}
entity = dict(converter)
for field in ('vehicle_intcd', 'vehicle_level', 'vehicle_name', 'vehicle_short_name',
              'vehicle_internal_name', 'vehicle_type', 'vehicle_nation_id', 'player_ready',
              'vehicle_ready', 'player_status', 'name', 'full_name', 'clan', 'rating'):
    entity[field] = None
entity['slot_index'] = 1
entity['commander'] = False

merged = mod._merge_platoon_entity_row(converter, entity)
assert merged['vehicle_intcd'] == 9521
assert merged['vehicle_level'] == 8
assert merged['player_ready'] is True
assert merged['player_status'] == 2
assert merged['name'] == 'tester'
assert merged['slot_index'] == 1
assert merged['commander'] is False
print('platoon source precedence test: ok')
