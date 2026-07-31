"""Build a Python 2.7-only stock WoT module discovery probe."""
from __future__ import print_function
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

PYTHON27 = r'C:\Python27\python.exe'
PACKAGE = 'shotcaller_bootstrap_test_0.0.1.wotmod'
META = '''<?xml version="1.0" encoding="UTF-8"?>
<root><id>shotcaller-bootstrap-test</id><version>0.0.1</version><name>ShotCaller Stock Bootstrap Test</name></root>'''
ARCHIVE_PYC = 'res/scripts/client/gui/mods/mod_shotcaller_bootstrap_test.pyc'

def main():
    root = os.path.dirname(os.path.abspath(__file__))
    source = os.path.join(root, 'mod_shotcaller_bootstrap_test.py')
    output = os.path.join(root, 'dist', PACKAGE)
    if not os.path.isfile(PYTHON27):
        print('Python 2.7 unavailable: ' + PYTHON27); return 1
    temporary = tempfile.mkdtemp(prefix='shotcaller_bootstrap_test_')
    try:
        pyc = os.path.join(temporary, 'mod_shotcaller_bootstrap_test.pyc')
        subprocess.check_call([PYTHON27, '-c', 'import py_compile,sys; py_compile.compile(sys.argv[1], sys.argv[2], doraise=True)', source, pyc])
        if not os.path.isdir(os.path.dirname(output)): os.makedirs(os.path.dirname(output))
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('meta.xml', META)
            archive.write(pyc, ARCHIVE_PYC)
        with zipfile.ZipFile(output, 'r') as archive:
            expected = sorted(('meta.xml', ARCHIVE_PYC))
            if sorted(archive.namelist()) != expected or any(item.compress_type != zipfile.ZIP_STORED for item in archive.infolist()):
                print('Archive audit failed.'); return 1
        print('Built: ' + output)
        print('Archive entries: meta.xml; ' + ARCHIVE_PYC)
        return 0
    finally:
        shutil.rmtree(temporary, ignore_errors=True)

if __name__ == '__main__': sys.exit(main())
