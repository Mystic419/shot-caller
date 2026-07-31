"""Build the 0.0.64 WR/battles and local clan watermark package."""
from __future__ import print_function
import sys
import build_native_lookup_migration as migration

migration.PACKAGE_NAME = 'shotcaller_0.0.64_winrate_clan_watermark.wotmod'
migration.META_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<root>
  <id>shotcaller</id>
  <version>0.0.64</version>
  <name>Shot-caller Win Rate and Clan Watermark</name>
</root>
'''
if __name__ == '__main__': sys.exit(migration.main())
