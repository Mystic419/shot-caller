"""Shared Python 2.7 builder for native-only Shot-caller releases.

The repository source intentionally contains the non-secret placeholder.  Each
release is injected into a temporary staging tree before compileall; the same
staged bytes are included for WGMods source review.
"""
from __future__ import print_function

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

PACKAGE_NAME = 'shotcaller_0.0.60_native_lookup_migration.wotmod'
PYC_ARCHIVE_PATH = 'res/scripts/client/gui/mods/mod_shotcaller.pyc'
SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleWindow.swf'
FILTER_SWF_ARCHIVE_PATH = 'res/gui/flash/shotcaller/shotcallerVehicleFilters.swf'
# All current shared-builder packages carry the exact injected source used by
# compileall, including ordinary release artifacts and WGMods review artifacts.
SOURCE_ARCHIVE_PATH = 'source/mod_shotcaller.py'
PYTHON27 = r'C:\Python27\python.exe'
APP_ID_ENV_NAME = b'WG_APP_ID'
APP_ID_PLACEHOLDER = b'NATIVE_WG_APP_ID = None'
APP_ID_PATTERN = re.compile(r'^[0-9a-fA-F]{32}$')
META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.60</version>
  <name>Shot-caller Native Lookup Migration (test build)</name>
</root>
'''


def _run(py27, cwd, name):
    return subprocess.call([py27, name], cwd=cwd) == 0


def _get_env_value(path, name):
    if not os.path.isfile(path):
        return None
    for raw_line in open(path, 'rb'):
        line = raw_line.strip()
        if not line or line.startswith(b'#') or b'=' not in line:
            continue
        key, value = line.split(b'=', 1)
        if key.strip() == name:
            value = value.strip().strip(b'\"\'')
            return value or None
    return None


def _validated_app_id(value):
    """Return an ASCII WG application ID, or None, without ever reporting it."""
    if not value:
        return None
    try:
        value = value.strip()
        text = value.decode('ascii') if isinstance(value, bytes) else value.encode('ascii').decode('ascii')
    except Exception:
        return None
    if not text or text == 'None' or text == APP_ID_PLACEHOLDER.decode('ascii'):
        return None
    return text if APP_ID_PATTERN.match(text) else None


def _inject_application_id(source, app_id):
    """Inject exactly one validated value into the staged source only."""
    app_id = _validated_app_id(app_id)
    if not app_id or source.count(APP_ID_PLACEHOLDER) != 1:
        return None
    replacement = b'NATIVE_WG_APP_ID = ' + repr(app_id.encode('ascii')).encode('ascii')
    staged = source.replace(APP_ID_PLACEHOLDER, replacement, 1)
    if APP_ID_PLACEHOLDER in staged or replacement not in staged:
        return None
    return staged


def _source_has_configured_app_id(source):
    for line in source.splitlines():
        if not line.startswith(b'NATIVE_WG_APP_ID') or b'=' not in line:
            continue
        value = line.split(b'=', 1)[1].strip()
        if len(value) != 34 or value[0:1] not in (b'\'', b'\"') or value[-1:] != value[0:1]:
            return False
        return _validated_app_id(value[1:-1]) is not None and APP_ID_PLACEHOLDER not in source
    return False


def _verify_compiled_runtime(pyc_path, app_id):
    """Load the generated Python 2.7 module and verify its injected value."""
    code = (
        "import imp,sys; m=imp.load_compiled('shotcaller_package_audit',sys.argv[1]); "
        "v=getattr(m,'NATIVE_WG_APP_ID',None); "
        "sys.exit(0 if isinstance(v,basestring) and v == sys.argv[2] else 1)"
    )
    return subprocess.call([PYTHON27, '-c', code, pyc_path, app_id], stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0


def _application_id_report(app_id):
    return 'application ID configured: yes\nlength: %s\nsource: injected build value' % len(app_id)


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(root))
    source_path = os.path.join(root, 'mod_shotcaller.py')
    output = os.path.join(root, 'dist', PACKAGE_NAME)
    inputs = (source_path, os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleWindow.swf'), os.path.join(root, 'custom_ui', 'dist', 'shotcallerVehicleFilters.swf'))
    app_id = _validated_app_id(_get_env_value(os.path.join(project_root, '.env'), APP_ID_ENV_NAME))
    if not os.path.isfile(PYTHON27):
        print('Native migration build requires Python 2.7.'); return 1
    if not app_id:
        print('Build failed: WG application ID is missing, empty, placeholder, or malformed.'); return 1
    if not all(os.path.isfile(path) for path in inputs): print('Native migration build input missing.'); return 1
    for test in ('test_history_state_classifier.py', 'test_platoon_source_precedence.py', 'test_vehicle_battles.py', 'test_vehicle_catalog_cache_scope.py', 'test_native_lookup.py', 'test_navigation_refresh.py', 'test_wg_api_batch_recovery.py', 'test_chunked_rate_limit_recovery.py', 'test_winrate_and_clan_watermark.py', 'test_wgmods_lifecycle.py', 'test_build_application_id.py'):
        if not _run(PYTHON27, root, test): print('Regression test failed: ' + test); return 1
    source = open(source_path, 'rb').read()
    staged_bytes = _inject_application_id(source, app_id)
    forbidden = (b'127.0.0.1', b'localhost', b'sidecar unavailable', b'sidecar roster lookup', b'python -m shot_caller.sidecar')
    if staged_bytes is None or not _source_has_configured_app_id(staged_bytes) or b"LOOKUP_TRANSPORT = 'native'" not in staged_bytes or any(value in staged_bytes.lower() for value in forbidden):
        print('Native-only staged source audit failed.'); return 1
    temporary = tempfile.mkdtemp(prefix='shotcaller_compileall_')
    try:
        runtime_relative = os.path.join('res', 'scripts', 'client', 'gui', 'mods', 'mod_shotcaller.py')
        staged_source = os.path.join(temporary, runtime_relative)
        readable_source = os.path.join(temporary, 'source', 'mod_shotcaller.py')
        staged_pyc = staged_source + 'c'
        if not os.path.isdir(os.path.dirname(staged_source)): os.makedirs(os.path.dirname(staged_source))
        if not os.path.isdir(os.path.dirname(readable_source)): os.makedirs(os.path.dirname(readable_source))
        open(staged_source, 'wb').write(staged_bytes)
        # This is deliberately copied after injection and before compileall.
        open(readable_source, 'wb').write(staged_bytes)
        compile_command = [PYTHON27, '-m', 'compileall', runtime_relative]
        print('Python 2.7 executable: ' + PYTHON27)
        print('Compileall command: ' + ' '.join(compile_command))
        compile_exit = subprocess.call(compile_command, cwd=temporary)
        print('Compileall exit code: ' + str(compile_exit))
        if compile_exit != 0 or not os.path.isfile(staged_pyc):
            print('Compileall did not create the required runtime .pyc.'); return 1
        expected_magic = subprocess.check_output([PYTHON27, '-c', "import imp; print imp.get_magic().encode('hex')"]).strip().decode('hex')
        actual_magic = open(staged_pyc, 'rb').read(4)
        if actual_magic != expected_magic:
            print('Compiled .pyc magic number does not match Python 2.7.'); return 1
        if open(readable_source, 'rb').read() != open(staged_source, 'rb').read():
            print('Staged readable source does not match the compileall source.'); return 1
        if not _verify_compiled_runtime(staged_pyc, app_id):
            print('Compiled runtime application ID verification failed.'); return 1
        os.remove(staged_source)
        if os.path.isfile(staged_source):
            print('Raw runtime source was not removed after compileall.'); return 1
        if not os.path.isdir(os.path.dirname(output)): os.makedirs(os.path.dirname(output))
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', META_XML)
            if SOURCE_ARCHIVE_PATH: archive.write(readable_source, SOURCE_ARCHIVE_PATH)
            archive.write(staged_pyc, PYC_ARCHIVE_PATH)
            archive.write(inputs[1], SWF_ARCHIVE_PATH)
            archive.write(inputs[2], FILTER_SWF_ARCHIVE_PATH)
        with zipfile.ZipFile(output) as archive:
            expected = ['meta.xml', PYC_ARCHIVE_PATH, SWF_ARCHIVE_PATH, FILTER_SWF_ARCHIVE_PATH]
            if SOURCE_ARCHIVE_PATH: expected.append(SOURCE_ARCHIVE_PATH)
            expected = sorted(expected)
            source_matches = not SOURCE_ARCHIVE_PATH or archive.read(SOURCE_ARCHIVE_PATH) == staged_bytes
            forbidden_entries = any(name.lower().endswith(('.log', '.pyc.v3')) or 'bootstrap' in name.lower() or 'cache' in name.lower() or '.env' in name.lower() or 'config' in name.lower() or 'credential' in name.lower() or 'secret' in name.lower() for name in archive.namelist())
            if sorted(archive.namelist()) != expected or any(info.compress_type != zipfile.ZIP_STORED for info in archive.infolist()) or not source_matches or forbidden_entries:
                print('Archive inspection failed.'); return 1
        print('Generated .pyc: ' + staged_pyc)
        print('Python magic number: ' + actual_magic.encode('hex'))
        print('Readable source/runtime compileall source match: yes')
        print(_application_id_report(app_id))
        print('Built native migration package: ' + output)
        return 0
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == '__main__': sys.exit(main())
