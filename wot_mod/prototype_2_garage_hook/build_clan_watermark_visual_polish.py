"""Build the 0.0.68 watermark visual polish package."""
from __future__ import print_function
import sys
import build_native_lookup_migration as migration
migration.PACKAGE_NAME = 'shotcaller_0.0.68_clan_watermark_visual_polish.wotmod'
migration.META_XML = '''<?xml version="1.0" encoding="UTF-8"?><root><id>shotcaller</id><version>0.0.68</version><name>Shot-caller Clan Watermark Visual Polish</name></root>'''
if __name__ == '__main__': sys.exit(migration.main())
