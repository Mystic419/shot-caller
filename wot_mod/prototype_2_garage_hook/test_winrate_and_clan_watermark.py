# -*- coding: utf-8 -*-
"""Python 2.7 unit coverage for WR display normalization and emblem cache safety."""
import imp
import os
import shutil
import time

mod = imp.load_source('shotcaller_wr_clan_test', 'mod_shotcaller.py')
assert mod._win_rate_text({'battles': 376, 'wins': 197}) == u'52.4%'
assert mod._win_rate_text({'battles': 1204, 'wins': 600}) == u'49.8%'
assert mod._win_rate_text({'battles': 0, 'wins': 0}) == u'—'
assert mod._win_rate_text({'battles': 10}) == u'—'  # 0.0.63 cache record
assert mod._win_rate_text({'battles': 10, 'wins': 11}) == u'—'
records = [{'tank_id': 1, 'all': {'battles': 4, 'wins': 3}}, {'tank_id': 2, 'all': {'battles': 0}}, {'tank_id': 3, 'all': {'battles': 2, 'wins': 3}}]
result = mod._native_result({'dbid': 1, 'name': 'tester'}, records, {1: {'name': 'Zulu', 'tier': 8, 'type': 'heavyTank'}, 2: {'name': 'Alpha', 'tier': 8, 'type': 'mediumTank'}, 3: {'name': 'Bad', 'tier': 8, 'type': 'lightTank'}}, 8)
assert [row['name'] for row in result['vehicles']] == ['Alpha', 'Bad', 'Zulu']
assert result['vehicles'][2]['wins'] == 3 and 'wins' not in result['vehicles'][0] and 'wins' not in result['vehicles'][1]

assert mod._clan_image_extension('\x89PNG\r\n\x1a\n' + 'x') == 'png'
assert mod._clan_image_extension('\xff\xd8\xff' + 'x') == 'jpg'
assert mod._clan_image_extension('<html>not an image</html>') is None
assert mod._clan_image_extension('x' * (mod.CLAN_EMBLEM_MAX_BYTES + 1)) is None

root = 'clan_emblem_test_cache'
if os.path.isdir(root): shutil.rmtree(root)
mod.CLAN_EMBLEM_DIR = root
os.makedirs(root)
image = os.path.join(root, 'na_12.png'); open(image, 'wb').write('\x89PNG\r\n\x1a\n')
meta = {'account_id': 44, 'realm': 'NA', 'clan_id': 12, 'tag': 'TAG', 'image_path': image, 'fetched_at': time.time()}
mod._native_atomic_write(mod._clan_emblem_meta_path('NA'), meta)
assert mod._load_clan_emblem_cache('NA')['clan_id'] == 12
assert '12' in mod._clan_emblem_image_path('NA', 12, 'png')
shutil.rmtree(root)
print('win rate and clan watermark test: ok')
