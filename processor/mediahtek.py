
from .base import baseFetcher
from internetarchive import modify_metadata, upload
import re
import json
import requests
import logging
from io import StringIO

ARD_DATA_RE = re.compile(r'<script id="fetchedContextValue" type="application/json">(.+?)</script>', re.I | re.M | re.S)
DREISAT_DATA_RE = re.compile(r'<script type="application/ld\+json">(.+?)</script>', re.I | re.M | re.S)

CREATOR_MAP = {
    "10804": "SWR",
    "28106": "SWR",
    "© Bayerischer Rundfunk": "BR",
    "Das Erste": "ARD",
    "wdr": "WDR",
    "hr": "HR",
    "mdr": "MDR",
    "ndr": "NDR",
    "swr": "SWR",
    "rbb": "RBB",
    "MITTELDEUTSCHER RUNDFUNK": "MDR",
}


class MediathekMetaFetcher(baseFetcher):
    def fix_meta(self, _id: str, lang: str = "de"):
        info = self.get_info_meta(_id)
        if not info:
            return
        meta = self.get_metadata(_id)

        title = []
        if info.get('alt_title'):
            title.append(info['alt_title'])

        if title:
            title.append(' - ')

        if info.get('title'):
            title.append(info['title'])

        title = ''.join(title).strip()

        modify = {}
        cur_subject = meta.get('subject', [])
        if type(cur_subject) != list:
            cur_subject = [cur_subject]

        if info.get('series'):
            if info['series'] not in cur_subject:
                cur_subject.append(info['series'])
                modify['subject'] = cur_subject

            if not info['series'] in title:
                title = f"{info['series']}: {title}"

            if info.get('season_number') is not None and not re.search(r'\s+\(S\d+', title, re.I):
                title += f" (S{info['season_number']:0>2}/E{info['episode_number']:0>2})"

        creator = meta['creator']

        if info.get('channel'):
            creator = CREATOR_MAP.get(info['channel'], info['channel'])

            if re.search(r'^\d+$', creator):
                raise Exception("unknown creator: " + info['channel'])
        else:
            if _id.startswith('3sat'):
                creator = '3sat'
            elif _id.startswith('ARDMediathek'):
                creator = 'ARD'
            elif _id.startswith('orf'):
                creator = 'ORF'
            elif _id.startswith('ZDF'):
                creator = 'ZDF'
            elif _id.startswith('SRGSSR'):
                creator = 'SRF'

        if creator.startswith('Bayerischer Rundfunk'):
            creator = 'BR'

        if creator != meta['creator']:
            modify['creator'] = creator

        details = self.fetch(_id)
        if details and '3sat-' in _id and details.get('publisher') and details['publisher'].get('name'):
            series = details['publisher']['name'].replace('3sat -', '').strip()
            title = series + ': ' + title
            if series not in cur_subject:
                cur_subject.append(series)
                modify['subject'] = cur_subject

            if details['publisher']['name'] not in cur_subject:
                cur_subject.append(details['publisher']['name'])
                modify['subject'] = cur_subject


        title = re.sub(r'(\s+)$', ' ', title)

        if title != meta['title']:
            modify['title'] = title

        if info.get('language') and meta.get('language') != info.get('language', '').replace('deu', 'ger'):
            modify['language'] = info['language'].replace('deu', 'ger')
        if info.get('season_number') and meta.get('season') != info.get('season_number'):
            modify['season'] = info['season_number']
        if info.get('episode_number') and meta.get('episode') != info.get('episode_number'):
            modify['episode'] = info['episode_number']

        if modify:
            print("updating metadata, ", modify, end=' ')
            print(modify_metadata(_id, modify).json())

    def store_details(self, _id: str, lang: str = 'de'):
        (_id_prefix, _base_id) = _id.split('-', 1)
        file_list = self.get_file_list(_id)

        for fname in file_list.keys():
            if fname == f"{_base_id}.{lang}.details.json":
                return True

        file_list = self.get_file_list(_id, False)

        for fname in file_list.keys():
            if fname == f"{_base_id}.{lang}.details.json":
                return True

        details = self.fetch(_id)
        if details:
            print(upload(_id, files={f'{_base_id}.{lang}.html': f'cache/{_id}.html', f'{_base_id}.{lang}.details.json': StringIO(json.dumps(details))}))
        return True

    def fetch(self, _id: str):
        info = self.get_info_meta(_id)
        if not info:
            return

        body = self.cache_get(_id, 'html', True)
        if not body:
            if not info.get('webpage_url'):
                return

            try:
                response = self.r.get(info['webpage_url'], timeout=10)
                if response.status_code == 404:
                    # try wayback
                    response = self.fetch_via_wayback(info['webpage_url'])

                if not response:
                    return None

                response.raise_for_status()
                body = response.text
                self.cache_set(body, _id, 'html', True)

            except requests.exceptions.RequestException as e:
                logging.exception(e)
                return None

        f = ARD_DATA_RE.search(body)
        if  f:
            return json.loads(f.group(1))

        f = DREISAT_DATA_RE.findall(body)
        if f:
            for item in f:
                try:
                    data = json.loads(item)
                except json.JSONDecodeError as e:
                    logging.exception(e)
                    continue
                if data.get('@type') == 'VideoObject':
                    return data
        return None
