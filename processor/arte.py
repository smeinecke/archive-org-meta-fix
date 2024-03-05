from typing import Optional
import logging
import os
import re
import json
from io import StringIO
import requests
from internetarchive import upload, get_item, modify_metadata

from .base import baseFetcher
NEXT_DATA_RE = re.compile('<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', re.I | re.M | re.S)


class ArteMetaFetcher(baseFetcher):
    def fetch(self, _id: str, lang: str = "de") -> Optional[str]:
        try:
            if os.path.exists(f'cache/{_id}.html'):
                with open(f'cache/{_id}.html', 'r') as f:
                    body = f.read()
            else:
                response = self.r.get(f'https://www.arte.tv/{lang}/videos/{_id}/')
                if response.status_code == 404:
                    # try wayback
                    response = self.fetch_via_wayback(f"https://www.arte.tv/{lang}/videos/{_id}/*")

                if not response:
                    return None

                response.raise_for_status()
                body = response.text
                with open(f'cache/{_id}.{lang}.html', 'w') as f:
                    f.write(body)

            f = NEXT_DATA_RE.search(body)
            if not f:
                return None
        except requests.exceptions.RequestException as e:
            logging.exception(e)
            return None
        data = f.group(1)
        return data

    def parse(self, data_json: str) -> Optional[dict]:
        try:
            data = json.loads(data_json)
        except json.JSONDecodeError as e:
            logging.exception(e)
            return None

        # print(data.get('props', {}).get('pageProps', {}).get('props', {}).get('page', {}).get('value', {}).get('zones', []))

        zones = data.get('props', {}).get('pageProps', {}).get('props', {}).get('page', {}).get('value', {}).get('zones', [])
        for zone in zones:
            for _data in zone.get('content', {}).get('data', []):
                if _data.get('type') == 'program':
                    return _data

        return None

    def fix_meta(self, _id: str, lang: str = "de"):
        res = self.fetch(_id, lang=lang)
        if not res:
            return

        data = self.parse(res)
        if not data:
            return

        item = get_item(f'ArteTV-{_id}')
        if not item:
            return

        subject = item.metadata.get('subject')
        if type(subject) != list:
            subject = [subject]

        modify = {}

        if lang == 'de':
            if data.get('shortDescription') and data.get('fullDescription'):
                description = '<strong>' + data['shortDescription'] + '</strong><br><br>' + data['fullDescription']
                if lang == 'de':
                    if item.metadata.get('description') != description:
                        modify['description'] = description
        else:
            if data.get('shortDescription'):
                modify[f'short_description-{lang}'] = data['shortDescription']
            if data.get('fullDescription'):
                modify[f'full_description-{lang}'] = data['fullDescription']

        if 'ArteTV;video;' in subject:
            subject.remove('ArteTV;video;')
            modify['subject'] = subject
            modify['subject'].append('ArteTV')
            modify['subject'].append('video')

        for col in data.get('parentCollections', []):
            if col['title'] not in subject:
                if not modify.get('subject'):
                    modify['subject'] = subject

                modify['subject'].append(col['title'])

        new_title = ""
        if data.get('title'):
            if data.get('title') not in subject:
                if not modify.get('subject'):
                    modify['subject'] = subject

                modify['subject'].append(data['title'])

            new_title = data['title']

        if data.get('genre') and data['genre'].get('label'):
            if data['genre'].get('label') not in subject:
                if not modify.get('subject'):
                    modify['subject'] = subject

                modify['subject'].append(data['genre'].get('label'))

        if data.get('subtitle'):
            if data.get('subtitle') not in subject:
                if not modify.get('subject'):
                    modify['subject'] = subject

                modify['subject'].append(data['subtitle'])

            if new_title:
                new_title += ' - ' + data['subtitle']
            else:
                new_title = data['subtitle']

        f = re.search('^ARTE Reportage - (.+)$', new_title)
        if f:
            new_title = f.group(1) + ' - ARTE Reportage'

        if lang == 'de':
            if new_title and item.metadata.get('title') != new_title:
                modify['title'] = new_title
        elif item.metadata.get(f'title-{lang}') != new_title:
            modify[f'title-{lang}'] = new_title

        if lang == 'de':
            for col in data.get('credits', []):
                if not col.get('values'):
                    continue

                curr = item.metadata.get(col['code'].lower(), [])
                if type(curr) != list:
                    curr = [curr]

                for vl in curr:
                    if ';' in vl:
                        curr.remove(vl)

                _curr = curr.copy()

                for x in curr:
                    if ',' in x or ' und ' in x or ' et ' in x:
                        curr.remove(x)

                if col['code'].lower() in ('aut', 'rea', 'pro', 'ima', 'mon') and len(col['values']) == 1:
                    if ' et ' in col.get('values')[0]:
                        col['values'] = [x.strip() for x in col.get('values')[0].split(' et ')]
                    elif ' und ' in col.get('values')[0]:
                        col['values'] = [x.strip() for x in col.get('values')[0].split(' und ')]
                    elif ',' in col.get('values')[0]:
                        col['values'] = [x.strip() for x in col.get('values')[0].split(',')]

                for vl in col.get('values'):
                    if vl not in curr:
                        curr.append(vl)

                curr = list(set([x.strip() for x in curr]))

                if curr != _curr:
                    modify[col['code'].lower()] = curr

        if item.metadata.get('creator') != 'ARTEde':
            modify['creator'] = 'ARTEde'

        if modify and not (modify.get('description') and len(modify.keys()) == 1):
            print("updating metadata, ", modify)
            r = modify_metadata(f'ArteTV-{_id}', modify).json()
            if r.get('success'):
                print(upload(f'ArteTV-{_id}', files={f'{_id}.{lang}.html': f'cache/{_id}.{lang}.html', f'{_id}.{lang}.details.json': StringIO(json.dumps(data))}))

        return True
