"""Build the WGMods review archive using standard Python 2.7 compileall."""
from __future__ import print_function
import sys
import build_native_lookup_migration as migration

migration.PACKAGE_NAME = 'shotcaller_0.0.77_wgmods_compileall.wotmod'
migration.SOURCE_ARCHIVE_PATH = 'source/mod_shotcaller.py'
migration.META_XML = '<?xml version="1.0" encoding="UTF-8"?><root><id>shotcaller</id><version>0.0.77</version><name>Shot-caller WGMods Compileall Review</name></root>'

if __name__ == '__main__':
    sys.exit(migration.main())
