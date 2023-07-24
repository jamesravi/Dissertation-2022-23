import requests
import string
import random
import time
import bencodepy
from multiprocessing.pool import ThreadPool
from utils import decode_peers

peeridchars = string.ascii_letters + string.digits

def generate_peerid():
    return "".join(random.choice(peeridchars) for _ in range(20))

class TrackerClient:
    def __init__(self, port, peer_id=None):
        self.port = port
        if peer_id is None:
            peer_id = generate_peerid()
        self.peer_id = peer_id

        self.urls = {}
        self.infohashes = {}

        self.compact = True
        self.no_peer_id = True

    def _announce(self, url, info_hash, uploaded, downloaded, left, event=None):
        params = {
            "info_hash": info_hash[0:20],
            "peer_id": self.peer_id,
            "port": self.port,
            "uploaded": uploaded,
            "downloaded": downloaded,
            "left": left,
            "compact": int(self.compact),
            "no_peer_id": int(self.no_peer_id),
        }

        if event is not None:
            params["event"] = event

        try:
            r = requests.get(url, params=params, timeout=10)
            result = bencodepy.decode(r.content)
            result[b"peers"] = decode_peers(result[b"peers"])
            result[b"url"] = url
        except KeyboardInterrupt as e:
            raise e
        except Exception:
            result = None
        return result

    def announce(self, infohash, uploaded, downloaded, left, event=None):
        infohash = infohash[0:20]
        if infohash not in self.infohashes:
            self.infohashes[infohash] = set()

        function = lambda url: self._announce(url, infohash, uploaded, downloaded, left, event)

        filteredurls = []
        for url, values in self.urls.items():
            if values["lastcontacted"] is None:
                filteredurls.append(url)
            else:
                if (time.time() - values["lastcontacted"]) >= values["interval"]:
                    filteredurls.append(url)

        with ThreadPool(8) as pool:
            results = pool.map(function, filteredurls)

        for result in results:
            if result is not None:
                self.infohashes[infohash].update(result[b"peers"])
                if b"min interval" in result:
                    interval = result[b"min interval"]
                else:
                    interval = result[b"interval"]
                self.urls[result[b"url"]]["interval"] = interval
                self.urls[result[b"url"]]["lastcontacted"] = time.time()

        return self.infohashes[infohash]

    def add_url(self, url):
        if url not in self.urls:
            self.urls[url] = {"interval": None, "lastcontacted": None}
