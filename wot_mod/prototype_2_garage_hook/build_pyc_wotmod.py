"""Build the Prototype 2 .pyc World of Tanks package without compression."""

from __future__ import print_function

import os
import sys
import zipfile


PACKAGE_NAME = 'shotcaller_0.0.22_skirmish_roster_cache_validation.wotmod'
PYC_ARCHIVE_PATH = 'res/scripts/client/gui/mods/mod_shotcaller.pyc'
META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.22</version>
  <name>Shot-caller Skirmish Roster Cache Validation</name>
</root>
'''


def main():
    script_directory = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(script_directory, 'mod_shotcaller.py')
    pyc_path = os.path.join(script_directory, 'mod_shotcaller.pyc')
    output_directory = os.path.join(script_directory, 'dist')
    output_path = os.path.join(output_directory, PACKAGE_NAME)

    if not os.path.isfile(pyc_path):
        print('Missing mod_shotcaller.pyc. Compile mod_shotcaller.py with the WoT-compatible Python version first.')
        return 1

    if os.path.isfile(source_path) and os.path.getmtime(pyc_path) < os.path.getmtime(source_path):
        print('mod_shotcaller.pyc is older than mod_shotcaller.py. Compile mod_shotcaller.py with the WoT-compatible Python version first.')
        return 1

    if not os.path.isdir(output_directory):
        os.makedirs(output_directory)

    with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_STORED) as archive:
        archive.writestr('meta.xml', META_XML)
        archive.write(pyc_path, PYC_ARCHIVE_PATH)

    print('Built {0}'.format(output_path))
    return 0


if __name__ == '__main__':
    sys.exit(main())
