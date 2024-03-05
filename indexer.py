import os
from pathlib import Path
from internetarchive import search_items
import json

from processor import ArteMetaFetcher, MediathekMetaFetcher

ARCHIVE_LOGIN = os.environ.get('ARCHIVE_LOGIN')

mmf = MediathekMetaFetcher()

for i in search_items(f"uploader:{ARCHIVE_LOGIN}"):
    _id = i['identifier']
    if 'ArteTV-' in _id or 'youtube-' in _id:
        continue

    if os.path.exists(f'cache/done/{_id}'):
        continue
    print(f"https://archive.org/details/{i['identifier']}")
    mmf.fix_meta(_id)
    if mmf.store_details(_id):
        Path(f"cache/done/{_id}").touch()

amf = ArteMetaFetcher()
for i in search_items(f"uploader:{ARCHIVE_LOGIN} ArteTV-"):
    _id = i['identifier'].replace('ArteTV-', '')
    if os.path.exists(f'cache/done/{_id}'):
        continue
    print(f"https://archive.org/details/{i['identifier']}")
    amf.fix_meta(_id)
    Path(f"cache/done/{_id}").touch()
    # print(amf.fetch(i['identifier']))
