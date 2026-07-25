"""Build 0.0.60 native-only lookup migration package without a sidecar."""
from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

PACKAGE_NAME = 'shotcaller_0.0.60_native_lookup_migration.wotmod'
PYC_ARCHIVE_PATH = 'res/scripts/client/gui/mods/mod_shotcaller.pyc'
SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleWindow.swf'
FILTER_SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleFilters.swf'
PYTHON27 = r'C:\Python27\python.exe'
META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.60</version>
  <name>Shot-caller Native Lookup Migration (test build)</name>
</root>
'''

def _app_id(path):
    if not os.path.isfile(path): return None
    for raw in open(path, 'rb'):
        line = raw.strip()
        if not line or line.startswith(b'#') or b'=' not in line: continue
        key, value = line.split(b'=', 1)
        if key.strip().lstrip(b'\xef\xbb\xbf') == b'WG_APP_ID': return value.strip().strip(b'\"\'') or None
    return None

def _run(py27, cwd, name): return subprocess.call([py27, name], cwd=cwd) == 0

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    project = os.path.dirname(os.path.dirname(root))
    app_id = _app_id(os.path.join(project, '.env'))
    source_path = os.path.join(root, 'mod_shotcaller.py')
    output = os.path.join(root, 'dist', PACKAGE_NAME)
    inputs = (source_path, os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleWindow.swf'), os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleFilters.swf'))
    if not os.path.isfile(PYTHON27) or not app_id:
        print('Native migration build requires Python 2.7 and WG_APP_ID (value not printed).'); return 1
    if not all(os.path.isfile(path) for path in inputs): print('Native migration build input missing.'); return 1
    for test in ('test_history_state_classifier.py', 'test_platoon_source_precedence.py', 'test_vehicle_battles.py', 'test_vehicle_catalog_cache_scope.py', 'test_native_lookup.py'):
        if not _run(PYTHON27, root, test): print('Regression test failed: ' + test); return 1
    source = open(source_path, 'rb').read()
    source = source.replace(b'NATIVE_WG_APP_ID = None', b'NATIVE_WG_APP_ID = ' + repr(app_id.decode('ascii')).encode('ascii'), 1)
    forbidden = (b'127.0.0.1', b'localhost', b'sidecar unavailable', b'sidecar roster lookup', b'python -m shot_caller.sidecar')
    if b"LOOKUP_TRANSPORT = 'native'" not in source or any(value in source.lower() for value in forbidden):
        print('Native-only source audit failed.'); return 1
    temporary = tempfile.mkdtemp(prefix='shotcaller_native_lookup_')
    try:
        staged_source = os.path.join(temporary, 'mod_shotcaller.py'); staged_pyc = os.path.join(temporary, 'mod_shotcaller.pyc')
        open(staged_source, 'wb').write(source)
        subprocess.check_call([PYTHON27, '-c', 'import py_compile,sys; py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)', staged_source, staged_pyc])
        if not os.path.isdir(os.path.dirname(output)): os.makedirs(os.path.dirname(output))
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', META_XML)
            archive.write(staged_pyc, PYC_ARCHIVE_PATH)
            archive.write(inputs[1], SWF_ARCHIVE_PATH)
            archive.write(inputs[2], FILTER_SWF_ARCHIVE_PATH)
        with zipfile.ZipFile(output) as archive:
            expected = sorted(('meta.xml', PYC_ARCHIVE_PATH, SWF_ARCHIVE_PATH, FILTER_SWF_ARCHIVE_PATH))
            if sorted(archive.namelist()) != expected or any(info.compress_type != zipfile.ZIP_STORED for info in archive.infolist()):
                print('Archive inspection failed.'); return 1
        print('Built native migration package: ' + output)
        print('WG application ID configured: yes (value not printed)')
        return 0
    finally: shutil.rmtree(temporary, ignore_errors=True)

if __name__ == '__main__': sys.exit(main())
