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
SOURCE_ARCHIVE_PATH = None
PYTHON27 = r'C:\Python27\python.exe'
META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.60</version>
  <name>Shot-caller Native Lookup Migration (test build)</name>
</root>
'''

def _run(py27, cwd, name): return subprocess.call([py27, name], cwd=cwd) == 0

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(root, 'mod_shotcaller.py')
    output = os.path.join(root, 'dist', PACKAGE_NAME)
    inputs = (source_path, os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleWindow.swf'), os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleFilters.swf'))
    if not os.path.isfile(PYTHON27):
        print('Native migration build requires Python 2.7.'); return 1
    if not all(os.path.isfile(path) for path in inputs): print('Native migration build input missing.'); return 1
    for test in ('test_history_state_classifier.py', 'test_platoon_source_precedence.py', 'test_vehicle_battles.py', 'test_vehicle_catalog_cache_scope.py', 'test_native_lookup.py', 'test_navigation_refresh.py', 'test_wg_api_batch_recovery.py', 'test_winrate_and_clan_watermark.py', 'test_wgmods_lifecycle.py'):
        if not _run(PYTHON27, root, test): print('Regression test failed: ' + test); return 1
    source = open(source_path, 'rb').read()
    forbidden = (b'127.0.0.1', b'localhost', b'sidecar unavailable', b'sidecar roster lookup', b'python -m shot_caller.sidecar')
    if b"LOOKUP_TRANSPORT = 'native'" not in source or any(value in source.lower() for value in forbidden):
        print('Native-only source audit failed.'); return 1
    temporary = tempfile.mkdtemp(prefix='shotcaller_compileall_')
    try:
        runtime_relative = os.path.join('res', 'scripts', 'client', 'gui', 'mods', 'mod_shotcaller.py')
        staged_source = os.path.join(temporary, runtime_relative)
        readable_source = os.path.join(temporary, 'source', 'mod_shotcaller.py')
        staged_pyc = staged_source + 'c'
        if not os.path.isdir(os.path.dirname(staged_source)): os.makedirs(os.path.dirname(staged_source))
        if not os.path.isdir(os.path.dirname(readable_source)): os.makedirs(os.path.dirname(readable_source))
        open(staged_source, 'wb').write(source)
        open(readable_source, 'wb').write(source)
        compile_command = [PYTHON27, '-m', 'compileall', runtime_relative]
        print('Python 2.7 executable: ' + PYTHON27)
        print('Compileall command: ' + ' '.join(compile_command))
        compile_exit = subprocess.call(compile_command, cwd=temporary)
        print('Compileall exit code: ' + str(compile_exit))
        if compile_exit != 0 or not os.path.isfile(staged_pyc):
            print('Compileall did not create the required runtime .pyc.'); return 1
        # Print hexadecimal text rather than raw bytes: on Windows a raw magic
        # value ending in CR/LF would be text-translated while crossing stdout.
        expected_magic = subprocess.check_output([PYTHON27, '-c', "import imp; print imp.get_magic().encode('hex')"]).strip().decode('hex')
        actual_magic = open(staged_pyc, 'rb').read(4)
        if actual_magic != expected_magic:
            print('Compiled .pyc magic number does not match Python 2.7.'); return 1
        if open(readable_source, 'rb').read() != open(staged_source, 'rb').read():
            print('Staged readable source does not match the compileall source.'); return 1
        os.remove(staged_source)
        if os.path.isfile(staged_source):
            print('Raw runtime source was not removed after compileall.'); return 1
        if not os.path.isdir(os.path.dirname(output)): os.makedirs(os.path.dirname(output))
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', META_XML)
            if SOURCE_ARCHIVE_PATH:
                archive.write(readable_source, SOURCE_ARCHIVE_PATH)
            archive.write(staged_pyc, PYC_ARCHIVE_PATH)
            archive.write(inputs[1], SWF_ARCHIVE_PATH)
            archive.write(inputs[2], FILTER_SWF_ARCHIVE_PATH)
        with zipfile.ZipFile(output) as archive:
            expected = ['meta.xml', PYC_ARCHIVE_PATH, SWF_ARCHIVE_PATH, FILTER_SWF_ARCHIVE_PATH]
            if SOURCE_ARCHIVE_PATH: expected.append(SOURCE_ARCHIVE_PATH)
            expected = sorted(expected)
            source_matches = not SOURCE_ARCHIVE_PATH or archive.read(SOURCE_ARCHIVE_PATH) == source
            forbidden_entries = any(name.lower().endswith(('.log', '.pyc.v3')) or 'bootstrap' in name.lower() or 'cache' in name.lower() or '.env' in name.lower() or 'config' in name.lower() or 'credential' in name.lower() or 'secret' in name.lower() for name in archive.namelist())
            if sorted(archive.namelist()) != expected or any(info.compress_type != zipfile.ZIP_STORED for info in archive.infolist()) or not source_matches or forbidden_entries:
                print('Archive inspection failed.'); return 1
        print('Generated .pyc: ' + staged_pyc)
        print('Python magic number: ' + actual_magic.encode('hex'))
        print('Readable source/runtime compileall source match: yes')
        print('Built native migration package: ' + output)
        return 0
    finally: shutil.rmtree(temporary, ignore_errors=True)

if __name__ == '__main__': sys.exit(main())
