"""Python 2.7 coverage for staged WG application-ID release injection."""
import imp
import os
import shutil
import subprocess
import tempfile

builder = imp.load_source('shotcaller_build_application_id_test', 'build_native_lookup_migration.py')

valid = 'a' * 32
assert builder._validated_app_id(valid) == valid
for invalid in (None, '', '   ', 'None', 'NATIVE_WG_APP_ID = None', 'not-an-app-id', 'a' * 31, 'z' * 32):
    assert builder._validated_app_id(invalid) is None

source = open('mod_shotcaller.py', 'rb').read()
staged = builder._inject_application_id(source, valid)
assert staged is not None and staged != source
assert builder._source_has_configured_app_id(staged)
assert builder.APP_ID_PLACEHOLDER not in staged
assert builder._inject_application_id(source, None) is None
assert builder._inject_application_id(staged, valid) is None

# An unconfigured value fails before a builder can inspect or package inputs.
original_get_env_value = builder._get_env_value
builder._get_env_value = lambda path, name: b' '
assert builder.main() == 1
builder._get_env_value = original_get_env_value

temporary = tempfile.mkdtemp(prefix='shotcaller_app_id_test_')
try:
    staged_source = os.path.join(temporary, 'mod_shotcaller.py')
    open(staged_source, 'wb').write(staged)
    assert open(staged_source, 'rb').read() == staged
    assert subprocess.call([builder.PYTHON27, '-m', 'compileall', staged_source]) == 0
    staged_pyc = staged_source + 'c'
    assert os.path.isfile(staged_pyc)
    assert builder._verify_compiled_runtime(staged_pyc, valid)
finally:
    shutil.rmtree(temporary, ignore_errors=True)

report = builder._application_id_report(valid)
assert report == 'application ID configured: yes\nlength: 32\nsource: injected build value'
assert valid not in report
print('build application ID test: ok')
