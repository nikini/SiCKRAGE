# Author: Idan Gutman
# URL: https://sickrage.ca
#
# This file is part of SickRage.
#
# SickRage is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SickRage is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SickRage.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
from urlparse import urljoin

from requests.utils import dict_from_cookiejar

import sickrage
from sickrage.core.caches.tv_cache import TVCache
from sickrage.core.helpers import bs4_parser, convert_size, try_int
from sickrage.providers import TorrentProvider


class TorrentLeechProvider(TorrentProvider):
    def __init__(self):
        super(TorrentLeechProvider, self).__init__("TorrentLeech", 'https://www.torrentleech.org', True)

        self.urls.update({
            'login': '{base_url}/user/account/login/'.format(**self.urls),
            'search': '{base_url}/torrents/browse'.format(**self.urls),
        })

        self.username = None
        self.password = None

        self.minseed = None
        self.minleech = None

        self.proper_strings = ['PROPER', 'REPACK']

        self.cache = TVCache(self, min_time=20)

    def login(self):
        if any(dict_from_cookiejar(sickrage.app.srWebSession.cookies).values()):
            return True

        login_params = {
            'username': self.username,
            'password': self.password,
        }

        try:
            response = sickrage.app.srWebSession.post(self.urls['login'], data=login_params, timeout=30).text
        except Exception:
            sickrage.app.srLogger.warning("Unable to connect to provider".format(self.name))
            return False

        if re.search('Invalid Username/password', response) or re.search('<title>Login :: TorrentLeech.org</title>',
                                                                         response):
            sickrage.app.srLogger.warning(
                "Invalid username or password. Check your settings".format(self.name))
            return False

        return True

    def search(self, search_strings, age=0, ep_obj=None):
        results = []

        if not self.login():
            return results

        for mode in search_strings:
            sickrage.app.srLogger.debug("Search Mode: %s" % mode)
            for search_string in search_strings[mode]:
                if mode != 'RSS':
                    sickrage.app.srLogger.debug("Search string: %s" % search_string)

                    categories = ["2", "7", "35"]
                    categories += ["26", "32"] if mode == "Episode" else ["27"]
                    if ep_obj.show and ep_obj.show.is_anime:
                        categories += ["34"]
                else:
                    categories = ["2", "26", "27", "32", "7", "34", "35"]

                search_params = {
                    "categories": ",".join(categories),
                    "query": search_string
                }

                try:
                    data = sickrage.app.srWebSession.get(self.urls["search"], params=search_params).text
                    results += self.parse(data, mode)
                except Exception:
                    sickrage.app.srLogger.debug("No data returned from provider")

        return results

    def parse(self, data, mode):
        """
        Parse search results from data
        :param data: response data
        :param mode: search mode
        :return: search results
        """

        results = []

        with bs4_parser(data) as html:
            torrent_table = html.find('table', attrs={'id': 'torrenttable'})
            torrent_rows = torrent_table.find_all('tr') if torrent_table else []

            # Continue only if one Release is found
            if len(torrent_rows) < 2:
                sickrage.app.srLogger.debug("Data returned from provider does not contain any torrents")
                return results

            for result in torrent_table.find_all('tr')[1:]:
                try:
                    title = result.find("td", class_="name").find("a").get_text(strip=True)
                    download_url = urljoin(self.urls['base_url'],
                                           result.find("td", class_="quickdownload").find("a")["href"])

                    if not all([title, download_url]):
                        continue

                    seeders = try_int(result.find('td', attrs={'class': 'seeders'}).text, 0)
                    leechers = try_int(result.find('td', attrs={'class': 'leechers'}).text, 0)

                    size = -1
                    if re.match(r'\d+([,.]\d+)?\s*[KkMmGgTt]?[Bb]',
                                result('td', class_="listcolumn")[1].text):
                        size = convert_size(result('td', class_="listcolumn")[1].text.strip(), -1)

                    item = {'title': title, 'link': download_url, 'size': size, 'seeders': seeders,
                            'leechers': leechers, 'hash': ''}

                    if mode != 'RSS':
                        sickrage.app.srLogger.debug("Found result: {}".format(title))

                    results.append(item)
                except Exception:
                    sickrage.app.srLogger.error("Failed parsing provider.")

        return results