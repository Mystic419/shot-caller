"""Build the 0.0.61 lookup-identity repair package."""
from __future__ import print_function

import sys
import build_native_lookup_migration as migration

migration.PACKAGE_NAME = 'shotcaller_0.0.61_native_generation_fix.wotmod'
migration.META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.61</version>
  <name>Shot-caller Native Lookup Identity Repair</name>
</root>
'''

if __name__ == '__main__': sys.exit(migration.main())
