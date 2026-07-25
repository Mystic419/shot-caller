"""Python 2.7 normalization coverage for history battle counts."""
import imp
mod = imp.load_source('shotcaller_battles_test', 'mod_shotcaller.py')
assert mod._battles({'battles': 837}) == 837
assert mod._battles({'battles': 1}) == 1
assert mod._battles({}) == 0
assert mod._battles({'battles': -7}) == 0
assert mod._battles({'battles': 'invalid'}) == 0
visible, total = mod._filtered_vehicles({'vehicles': [{'tank_id': 1, 'battles': 837}, {'tank_id': 2}]})
assert total == 2 and mod._battles(visible[0]) == 837 and mod._battles(visible[1]) == 0
print('vehicle battles test: ok')
