from __future__ import print_function
import sys
import build_native_lookup_migration as migration
migration.PACKAGE_NAME='shotcaller_0.0.77_standalone.wotmod'
migration.META_XML='<?xml version="1.0" encoding="UTF-8"?><root><id>shotcaller</id><version>0.0.77</version><name>Shot-caller Standalone</name></root>'
if __name__=='__main__':sys.exit(migration.main())
