import os
from pathlib import Path
from internetarchive import search_items

from processor.arte import ArteMetaFetcher


ARCHIVE_LOGIN = os.environ.get('ARCHIVE_LOGIN')

amf = ArteMetaFetcher()

for i in search_items(f"uploader:{ARCHIVE_LOGIN} ArteTV-"):
    _id = i['identifier'].replace('ArteTV-', '')
    if os.path.exists(f'cache/done/{_id}'):
        continue
    print(f"https://archive.org/details/{i['identifier']}")
    amf.fix_meta(_id)
    Path(f"cache/done/{_id}").touch()
    # print(amf.fetch(i['identifier']))
