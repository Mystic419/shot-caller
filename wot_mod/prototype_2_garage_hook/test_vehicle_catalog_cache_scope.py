"""Python 2.7 mock tests for atomic caching and VehicleItem class resolution."""
from __future__ import print_function

import imp
import json
import os
import sys
import types


class VehicleItem(object):
    # Intentionally has no type/typeName: matches live 2.3.1 wrapper behavior.
    def __init__(self, compact_descr, name, level):
        self.compactDescr = compact_descr
        self.userString = name
        self.level = level
        self.type = None
        self.typeName = None


class VehicleType(object):
    def __init__(self, vehicle_class): self.tags = set((vehicle_class,))


class VehicleList(object):
    def __init__(self, fail=False): self.fail = fail
    def getList(self, nation_id):
        if self.fail: raise RuntimeError('simulated catalog failure')
        return {1: VehicleItem(101, 'Heavy', 6), 2: VehicleItem(201, 'Medium', 8),
                3: VehicleItem(301, 'Light', 10), 4: VehicleItem(401, 'TD', 8),
                5: VehicleItem(501, 'SPG', 8), 6: VehicleItem(601, 'Unknown', 8),
                7: VehicleItem(701, 'Broken', 8), 8: VehicleItem(201, 'Duplicate', 8),
                9: VehicleItem(901, 'UnsupportedTier', 5)}


class Namespace(object):
    def __init__(self, **values): self.__dict__.update(values)


class FlashCapture(object):
    def __init__(self): self.calls = []
    def as_beginData(self, tier, notice): self.calls.append(('begin', tier))
    def as_setTierCatalog(self, tier, ids, names, classes): self.calls.append(('tier', tier, len(ids), len(names), len(classes)))
    def as_setHiddenIds(self, tier, ids): self.calls.append(('hidden', tier, len(ids)))
    def as_finishData(self): self.calls.append(('finish',))


def install_items(fail=False):
    classes = {101: 'heavyTank', 201: 'mediumTank', 301: 'lightTank', 401: 'AT-SPG',
               501: 'SPG', 601: 'unknown'}
    def get_vehicle_type(compact_descr):
        if compact_descr == 701: raise RuntimeError('simulated descriptor failure')
        return VehicleType(classes[compact_descr])
    def get_vehicle_class(vehicle_type):
        for tag in vehicle_type.tags:
            return tag
    items = types.ModuleType('items')
    items.nations = Namespace(INDICES={0: 0})
    items.vehicles = Namespace(g_list=VehicleList(fail), getVehicleType=get_vehicle_type,
                               getVehicleClassFromVehicleType=get_vehicle_class)
    sys.modules['items'] = items


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    module = imp.load_source('shotcaller_catalog_scope_test', os.path.join(here, 'mod_shotcaller.py'))
    install_items(False); module.VEHICLE_CATALOG = None
    first = module._build_vehicle_catalog()
    assert first is not None and len(first['8']) == 3, 'class resolution or duplicate filtering failed'
    assert set(row['type'] for row in first['8']) == set(('mediumTank', 'AT-SPG', 'SPG'))
    second = module._build_vehicle_catalog()
    assert first is second, 'second build did not reuse module cache'
    module.VEHICLE_CATALOG = None; install_items(True)
    assert module._build_vehicle_catalog() is None, 'failed build cached a partial catalog'
    install_items(False)
    retry = module._build_vehicle_catalog()
    assert retry is not None and retry['10'][0]['type'] == 'lightTank', 'retry did not rebuild catalog'
    payload = json.loads(module._filter_payload(8))
    assert payload['schemaVersion'] == 1 and payload['selectedTier'] == 8
    assert isinstance(payload['catalogs']['8'], list) and payload['catalogs']['8'][0]['class'] == 'mediumTank'
    assert isinstance(payload['hiddenVehicleIds']['8'], list)
    capture = FlashCapture()
    module._send_filter_native_data(capture, module._filter_native_data(8))
    assert capture.calls[0] == ('begin', 8) and capture.calls[-1] == ('finish',)
    assert len([entry for entry in capture.calls if entry[0] == 'tier']) == 3
    print('vehicle catalog cache and class-resolution test: ok')


if __name__ == '__main__':
    main()
