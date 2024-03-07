
from .base import baseFetcher
from internetarchive import modify_metadata, upload
import re
import json
import requests
import logging
from io import StringIO
import logging

SENDUNGSLINK_RE = re.compile(r"""<a class="sendungslink accordion-title last" href="([^"]+)""", re.I)

TAG_RE = re.compile(r"""<[^>]+>""", re.I | re.S)

TAGS = {
    'title': re.compile(r"""<meta property="og:title" content="([^"]+)""", re.I),
    'subtitle': re.compile(r"""<span class="subtitle">([^<]+)</span>""", re.I | re.S),
    'teaser': re.compile(r"""<div class="eventText">(.+?)</div>""", re.I | re.S),
    'mediathek_link': re.compile(r"""<a class="mediathek".+?href="([^"]+)""", re.I),
    'description': re.compile(r"""<div id="[^"]+" class="tabs-panel details-tab is-active">\s*<div class="eventText">(.+?)</div>""", re.I | re.S),
    'credits': re.compile(r"""<table class="besetzung">(.+?)</table>""", re.I | re.S),
    'sendungsnummer': re.compile(r"""<ul class="tabs" data-tabs id="tabs-(\d+)""", re.I | re.S),
}


CREDIT_RE = re.compile(r"""<tr>\s*<td class="role">(.+?)</td>\s*<td class="actor">(.+?)</td>""", re.I | re.S)

class ArdProgrammMetaFetcher(baseFetcher):

    def fetch(self, _id: str):
        info = self.get_info_meta(_id)
        if not info:
            return

        media_id = info.get('id')
        if not media_id:
            return

        body = self.cache_get(_id, 'programm.html', True)
        if body:
            return body

        response = self.r.get("https://programm.ard.de/TV/Programm/Detailsuche", params={
            "detailsuche": 1,
            "sendungstitel": info.get('title', ''),
            "mitwirkende": "",
            "volltext": media_id,
            "ausstrahlungswahl":"past",
            "sendezeitauswahl": "none",
            "senderauswahl": "all",
            "sort":"auto"
        })

        if response.status_code != 200:
            logging.error("Failed to fetch programm for %s - %s", _id, response.status_code)
            return

        #links = SENDUNGSLINK_RE.findall(response.text)
        #if len(links) > 1:
        #    logging.error("More than one link found for %s", _id)
        #    return

        f = SENDUNGSLINK_RE.search(response.text)
        if not f:
            logging.error("No link found for %s", _id)
            return

        # get details
        response = self.r.get('https://programm.ard.de' + f.group(1))
        if response.status_code != 200:
            logging.error("Failed to fetch detail programm for %s - %s", _id, response.status_code)
            return

        body = response.text
        self.cache_set(body, _id, 'programm.html', True)
        return body

    def parse(self, body:str):
        data = {}
        for k, v in TAGS.items():
            f = v.search(body)
            if not f:
                continue

            data[k] = f.group(1).strip()
            if k == 'subtitle' and ' | ' in data[k]:
                data[k] = data[k].split(' | ', 1)[0].strip()
            elif k == 'teaser':
                data[k] = TAG_RE.sub('', data[k]).strip()
            elif k == 'credits':
                persons = []
                for x in CREDIT_RE.findall(data[k]):
                    persons.append({
                        'role': TAG_RE.sub('', x[0]).strip(),
                        'actor': TAG_RE.sub('', x[1]).strip()
                    })
                data[k] = persons

        return data

    def upload(self, _id: str, lang: str = 'de', force:bool = False):
        (_id_prefix, _base_id) = _id.split('-', 1)
        if not force:
            file_list = self.get_file_list(_id)

            for fname in file_list.keys():
                if fname == f"{_base_id}.{lang}.programm.json":
                    return True

            file_list = self.get_file_list(_id, False)

            for fname in file_list.keys():
                if fname == f"{_base_id}.{lang}.programm.json":
                    return True

        data = self.fetch(_id)
        if data:
            programm = self.parse(data)
            print(upload(_id, files={f'{_base_id}.{lang}.programm.html': f'cache/{_id}.programm.html', f'{_base_id}.{lang}.programm.json': StringIO(json.dumps(programm))}))

            description = ""
            if programm.get('teaser'):
                description = '<strong>' + programm['teaser'] + '</strong><br><br>'

            if programm.get('description'):
                if programm.get('teaser'):
                    append = programm['description'].replace(programm['teaser'], '')
                else:
                    append = programm['description']
                description += append

            modify = {
                'description': description,
            }
            if programm.get('credits'):
                item = ""
                for x in programm['credits']:
                    item += f"{x['role']}: {x['actor']}\n"

                modify['credits'] = item
                logging.debug(modify['credits'])
            logging.info(modify)
            logging.info(modify_metadata(_id, modify).json())

        return True