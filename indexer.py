import os
from pathlib import Path
from internetarchive import search_items
import json
import logging

logging.basicConfig(level=logging.INFO)
from processor import ArteMetaFetcher, MediathekMetaFetcher, ArdProgrammMetaFetcher

ARCHIVE_LOGIN = os.environ.get('ARCHIVE_LOGIN')

apm = ArdProgrammMetaFetcher()
for i in search_items(f"uploader:{ARCHIVE_LOGIN} ARDMediathek-"):
    _id = i['identifier']
    if os.path.exists(f'cache/done/{_id}.programm'):
        continue
    print(i['identifier'])
    if (apm.upload(i['identifier'], force=True)):
        Path(f"cache/done/{_id}.programm").touch()

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
