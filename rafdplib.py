import base64
import subprocess
import platform
import os
import signal
import json
import socket
import time

import utils

def sendjson(port, data):
    data = json.dumps(data).encode("ascii")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        sock.sendto(data, ("127.0.0.1", port))
        result, _ = sock.recvfrom(60000)
    return json.loads(result.decode("ascii"))

class RAFDPProcess:
    def __init__(self, rpcport, openprocess=True, newconsole=False, delay=0.01):
        self.rpcport = rpcport
        self.delay = delay
        self.hashstatscache = {}
        if openprocess:
            self.open(newconsole=newconsole)

    def open(self, newconsole=False):
        port = self.rpcport
        if type(port) != str:
            port = str(port)
        if os.name == "nt":
            pythonexe = "python"
        else:
            pythonexe = "python3"
        if not newconsole:
            self.process = subprocess.Popen([pythonexe, "rafdp.py", port])
        else:
            if os.name == "nt":
                self.process = subprocess.Popen(["cmd", "/k", pythonexe, "rafdp.py", port], creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                self.process = subprocess.Popen(["gnome-terminal", "--", "python3", "rafdp.py", port])

    def close(self):
        if platform.system() == "Linux":
            os.kill(self.getpid(), signal.SIGTERM)
        self.process.terminate()

    def getport(self):
        result = sendjson(self.rpcport, {"method": "getport"})
        if not result["success"]:
            raise Exception(result)
        return result["port"]

    def getpid(self):
        result = sendjson(self.rpcport, {"method": "getpid"})
        if not result["success"]:
            raise Exception(result)
        return result["pid"]

    def addpeer(self, address, port):
        result = sendjson(self.rpcport, {"method": "addpeer", "ip": address, "port": port})
        return result["success"]

    def addfile(self, filename):
        result = sendjson(self.rpcport, {"method": "addfile", "filename": filename})
        if not result["success"]:
            raise Exception(result)
        return result["hash"]

    def addhash(self, thehash):
        result = sendjson(self.rpcport, {"method": "addhash", "hash": thehash})
        return result["success"]

    def gethash(self, thehash):
        result = sendjson(self.rpcport, {"method": "gethash", "hash": thehash})
        if result["success"]:
            thehash = result["hashed"]
            if result["encoded"]:
                thehash = base64.b64decode(thehash)
            return thehash
        else:
            return None

    def addurl(self, url):
        result = sendjson(self.rpcport, {"method": "addurl", "url": url})
        if not result["success"]:
            raise Exception(result)
        return result["success"]

    def getpeers(self):
        result = sendjson(self.rpcport, {"method": "getpeers"})
        if not result["success"]:
            raise Exception(result)
        return result["peers"]

    def getoutermosthash(self, thehash, last=False, delay=None):
        if delay is None:
            delay = self.delay

        while True:
            result = self.gethash(thehash)
            while result is None:
                time.sleep(delay)
                result = self.gethash(thehash)
            if type(result) is str and result.startswith("RAFDP") and ",RAFDP" in result:
                thehash = result.split(",")[int(last)]
            elif type(result) is str:
                thehash = result
            elif type(result) is bytes:
                chunkindex, result = utils.fromvarint(result)
                if not last:
                    assert chunkindex == 0
                return chunkindex, result
            else:
                raise Exception(result)

    def getchunkofhashbyindex(self, thehash, index, highestindex, delay=None):
        if delay is None:
            delay = self.delay

        if highestindex != 0:
            directionlist = bin(index)[2:].zfill(len(bin(highestindex)[2:]))
            for direction in directionlist:
                result = self.gethash(thehash)
                while result is None:
                    time.sleep(delay)
                    result = self.gethash(thehash)
                thehash = result.split(",")[int(direction)]
        result = self.gethash(thehash)
        while result is None:
            time.sleep(delay)
            result = self.gethash(thehash)

        assert type(result) is bytes
        chunkindex, result = utils.fromvarint(result)
        assert chunkindex == index, f"Expected {index} as index, got {chunkindex} instead"
        return result

    def gethashstats(self, thehash, delay=None):
        if delay is None:
            delay = self.delay

        if thehash not in self.hashstatscache:
            _, firstchunk = self.getoutermosthash(thehash, last=False, delay=delay)
            chunkindex, lastchunk = self.getoutermosthash(thehash, last=True, delay=delay)

            chunksize, lastchunksize, numchunks = len(firstchunk), len(lastchunk), chunkindex + 1
            estfilesize = (chunksize * (numchunks - 1)) + lastchunksize

            self.hashstatscache[thehash] = (chunksize, lastchunksize, numchunks, estfilesize)

        return self.hashstatscache[thehash]

    def getsizeoffsetfromhash(self, thehash, size, offset, delay=None):
        if delay is None:
            delay = self.delay

        chunksize, lastchunksize, numchunks, estfilesize = self.gethashstats(thehash, delay=delay)
        if offset > estfilesize:
            offset = estfilesize
        if (size + offset) > estfilesize:
            size = estfilesize - offset
        startindex = int(offset / chunksize)
        endindex = int((offset + size) / chunksize) + 1
        if endindex > numchunks - 1:
            endindex = numchunks
        gathereddata = b""
        for index in range(startindex, endindex):
            gathereddata += self.getchunkofhashbyindex(thehash, index, numchunks - 1, delay=delay)
        gathereddata = gathereddata[offset - (startindex * chunksize):][0:size]
        return gathereddata