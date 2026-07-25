"""Build the one-session native HTTPS diagnostic package (not a release)."""
from __future__ import print_function

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile


PACKAGE_NAME = 'shotcaller_0.0.59_native_https_probe.wotmod'
PYC_ARCHIVE_PATH = 'res/scripts/client/gui/mods/mod_shotcaller.pyc'
SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleWindow.swf'
FILTER_SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleFilters.swf'
PYTHON27 = r'C:\Python27\python.exe'
META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.59</version>
  <name>Shot-caller Native HTTPS Probe (development only)</name>
</root>
'''


def _get_env_value(path, name):
    if not os.path.isfile(path):
        return None
    for raw_line in open(path, 'rb'):
        line = raw_line.strip()
        if not line or line.startswith(b'#') or b'=' not in line:
            continue
        key, value = line.split(b'=', 1)
        if key.strip() != name:
            continue
        value = value.strip().strip(b'\"\'')
        return value or None
    return None


def _run_python27(script_directory, test_name):
    return subprocess.call([PYTHON27, test_name], cwd=script_directory) == 0


def _compile_python27(source_path, pyc_path):
    command = [PYTHON27, '-c',
               'import py_compile,sys; py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)',
               source_path, pyc_path]
    subprocess.check_call(command)


def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    project_directory = os.path.dirname(os.path.dirname(script_directory))
    source_path = os.path.join(script_directory, 'mod_shotcaller.py')
    swf_path = os.path.join(script_directory, 'custom_ui', 'dist', 'shotcallerVehicleWindow.swf')
    filter_swf_path = os.path.join(script_directory, 'custom_ui', 'dist', 'shotcallerVehicleFilters.swf')
    output_directory = os.path.join(script_directory, 'dist')
    output_path = os.path.join(output_directory, PACKAGE_NAME)
    app_id = _get_env_value(os.path.join(project_directory, '.env'), b'WG_APP_ID')

    if not os.path.isfile(PYTHON27):
        print('Python 2.7 compiler unavailable: {0}'.format(PYTHON27))
        return 1
    if not app_id:
        print('WG application ID unavailable for development probe (value not printed).')
        return 1
    for path in (source_path, swf_path, filter_swf_path):
        if not os.path.isfile(path):
            print('Missing required package input: {0}'.format(path))
            return 1
    for test_name in ('test_history_state_classifier.py', 'test_platoon_source_precedence.py', 'test_vehicle_battles.py'):
        if not _run_python27(script_directory, test_name):
            print('Regression test failed: {0}'.format(test_name))
            return 1

    source = open(source_path, 'rb').read()
    source = source.replace(b'NATIVE_PROBE_ENABLED = False', b'NATIVE_PROBE_ENABLED = True', 1)
    source = source.replace(b'NATIVE_WG_APP_ID = None', b'NATIVE_WG_APP_ID = ' + repr(app_id.decode('ascii')).encode('ascii'), 1)
    if b'NATIVE_PROBE_ENABLED = True' not in source or b"LOOKUP_TRANSPORT = 'sidecar'" not in source:
        print('Development probe source injection check failed.')
        return 1

    temporary_directory = tempfile.mkdtemp(prefix='shotcaller_native_probe_')
    try:
        staged_source = os.path.join(temporary_directory, 'mod_shotcaller.py')
        staged_pyc = os.path.join(temporary_directory, 'mod_shotcaller.pyc')
        open(staged_source, 'wb').write(source)
        _compile_python27(staged_source, staged_pyc)
        if not os.path.isdir(output_directory):
            os.makedirs(output_directory)
        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', META_XML)
            archive.write(staged_pyc, PYC_ARCHIVE_PATH)
            archive.write(swf_path, SWF_ARCHIVE_PATH)
            archive.write(filter_swf_path, FILTER_SWF_ARCHIVE_PATH)
        with zipfile.ZipFile(output_path, 'r') as archive:
            names = archive.namelist()
            expected = [PYC_ARCHIVE_PATH, FILTER_SWF_ARCHIVE_PATH, SWF_ARCHIVE_PATH, 'meta.xml']
            if sorted(names) != sorted(expected) or any(info.compress_type != zipfile.ZIP_STORED for info in archive.infolist()):
                print('Archive inspection failed.')
                return 1
        print('Built development probe package: {0}'.format(output_path))
        print('WG application ID configured: yes (value not printed)')
        return 0
    finally:
        shutil.rmtree(temporary_directory, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
