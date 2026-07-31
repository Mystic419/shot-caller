"""Build the 0.0.66 clan account parsing repair."""
from __future__ import print_function
import sys
import build_native_lookup_migration as migration
migration.PACKAGE_NAME = 'shotcaller_0.0.66_clan_api_parsing_fix.wotmod'
migration.META_XML = '''<?xml version="1.0" encoding="UTF-8"?><root><id>shotcaller</id><version>0.0.66</version><name>Shot-caller Clan API Parsing Fix</name></root>'''
if __name__ == '__main__': sys.exit(migration.main())
