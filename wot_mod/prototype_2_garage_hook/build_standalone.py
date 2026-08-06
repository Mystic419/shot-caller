from __future__ import print_function
import sys
import build_native_lookup_migration as migration
migration.PACKAGE_NAME='shotcaller_0.0.78_standalone.wotmod'
migration.SOURCE_ARCHIVE_PATH='source/mod_shotcaller.py'
migration.META_XML='<?xml version="1.0" encoding="UTF-8"?><root><id>shotcaller</id><version>0.0.78</version><name>Shot-caller Standalone</name></root>'
if __name__=='__main__':sys.exit(migration.main())
