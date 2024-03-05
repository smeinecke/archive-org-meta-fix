import requests
from typing import Optional
import os
import re
import json
from internetarchive import get_files as ia_get_files, download as ia_download, get_item as ia_get_item


class baseFetcher():
    def __init__(self):
        self.r = requests.session()
        self.r.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
        })

    def cache_get(self, id: str, ext: str = 'json', raw: bool = False) -> Optional[dict]:
        if not os.path.exists(f'cache/{id}.{ext}'):
            return

        with open(f'cache/{id}.{ext}', 'r') as f:
            if raw:
                return f.read()

            return json.load(f)

    def cache_set(self, data, id: str, ext: str = 'json', raw: bool = False):
        with open(f'cache/{id}.{ext}', 'w') as f:
            if raw:
                f.write(data)
                return
            json.dump(data, f)

    def get_file_list(self, _id: str, cached: bool = True) -> list:
        if cached:
            data = self.cache_get(_id, 'list')
            if data:
                return data

        file_list = ia_get_files(_id)
        data = {}
        for _item in file_list:
            data[_item.name] = {
                'name': _item.name,
                'size': _item.size,
                'mtime': _item.mtime,
                'format': _item.format,
                'source': _item.source,
                'sha1': _item.sha1
            }
        self.cache_set(data, _id, 'list')
        return data

    def get_info_meta(self, _id: str) -> Optional[dict]:
        data = self.cache_get(_id, 'meta')
        if data:
            return data

        r = ia_download(_id, glob_pattern='*.info.json', no_directory=True, return_responses=True)
        if not r or r[0].status_code != 200:
            return None
        data = r[0].json()
        self.cache_set(data, _id, 'meta')
        return data

    def get_metadata(self, _id: str) -> Optional[dict]:
        data = self.cache_get(_id, 'json')
        if data:
            return data

        item = ia_get_item(_id)
        if not item:
            return

        data = item.metadata
        self.cache_set(data, _id, 'json')
        return data

    def fetch_via_wayback(self, url: str) -> Optional[requests.Response]:
        response = self.r.get(f"http://archive.org/wayback/available?url={url.split('?')[0]}")

        if not response or response.status_code != 200:
            return None

        r_json = response.json()

        if not 'closest' in r_json['archived_snapshots']:
            return None

        clo = r_json['archived_snapshots']['closest']
        if clo['status'] != '200':
            return None

        response_final = self.r.get(clo['url'])
        if not response_final or response_final.status_code != 200:
            return None

        return response_final
