import requests
from typing import Optional
import re
NEXT_DATA_RE = re.compile('<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.I | re.M | re.S)


class baseFetcher():
    def __init__(self):
        self.r = requests.session()
        self.r.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36'
        })

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
