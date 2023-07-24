import time
import random
import os

import utils
from rafdplib import RAFDPProcess
from core import MerkleTree
from utils import MemFS, encode_peers

from flask import Flask, request
from werkzeug.serving import make_server
import threading
import bencodepy

import pytest

def test_varint():
    anumber = random.randint(0, (16 ** 15) - 1)
    randomdata = os.urandom(random.randint(5, 20))
    convertback = utils.fromvarint(utils.tovarint(anumber) + randomdata)
    assert anumber == convertback[0]
    assert randomdata == convertback[1]

def test_merkle_tree():
    tree = MerkleTree()
    roothash = tree.generate_tree("cat.jpg")

    newtree = MerkleTree()
    newtree.set(roothash)
    while not newtree.is_complete():
        findthis = random.choice(newtree.get_missing())
        foundresult = tree.get(findthis, expandtuple=False)[1]
        newtree.set(findthis, foundresult)

    assert sorted(tree.tree.items()) == sorted(newtree.tree.items())

def generate_test_range(estfilesize, chunksize, startinrange=True, endinrange=True, condition=0):
    """
    Generate random test ranges until one is found that matches the condition requested, the conditions are:
    0 - a range smaller than the chunk size
    1 - a range larger than the chunk size
    2 - a range the same size as the chunk size
    """
    while True:
        selectedrange = []
        if startinrange:
            selectedrange.append(random.randrange(0, estfilesize))
        else:
            selectedrange.append(random.randrange(estfilesize, estfilesize+int(estfilesize/2)))
        if endinrange:
            selectedrange.append(random.randrange(0, estfilesize))
        else:
            selectedrange.append(random.randrange(estfilesize, estfilesize+int(estfilesize/2)))
        selectedrange = sorted(selectedrange)

        size, offset = selectedrange[1] - selectedrange[0], selectedrange[0]
        if condition == 0:
            if size < chunksize:
                return (size, offset)
        elif condition == 1:
            if size > chunksize:
                return (size, offset)
        elif condition == 2:
            if size > chunksize:
                return (chunksize, offset)

class Test_RAFDP_Processes:
    @classmethod
    def setup_class(cls):
        firstrpcport = 7284
        secondrpcport = 7285
        cls.first = RAFDPProcess(firstrpcport)
        cls.second = RAFDPProcess(secondrpcport)

        time.sleep(2)

    @classmethod
    def teardown_class(cls):
        cls.first.close()
        cls.second.close()

    def test_rafdp_get_hash(self):
        first, second = self.first, self.second

        firstport = first.getport()
        secondport = second.getport()

        assert first.addpeer("127.0.0.1", secondport)
        thehash = first.addfile("cat.jpg")
        assert second.addhash(thehash)

        result = second.gethash(thehash)
        while result is None:
            time.sleep(1)
            result = second.gethash(thehash)
        assert result == "RAFDP10zQmTfnKu1PbUMP2uwWTyBGT9cGauFkqjjHNwZpDUyWtGS4X,RAFDP10zQmX4c768h5bDfmo9NNpkz56PmdHYf3cx8vkf748QXD2zJs"

    def test_rafdp_getting_whole_file(self):
        first, second = self.first, self.second

        filename = "greatexpectations.txt"

        firstport = first.getport()
        secondport = second.getport()

        thehash = first.addfile(filename)
        assert second.addpeer("127.0.0.1", firstport)
        assert second.addhash(thehash)

        newtree = MerkleTree()
        newtree.set(thehash)
        while not newtree.is_complete():
            findthis = random.choice(newtree.get_missing())
            result = second.gethash(findthis)
            while result is None:
                time.sleep(0.1)
                result = second.gethash(thehash)
            newtree.set(findthis, result)

        chunks = {}
        for item in newtree.tree.values():
            if type(item) == bytes:
                chunkindex, item = utils.fromvarint(item)
                chunks[chunkindex] = item
        gathereddata = b"".join(chunks[key] for key in sorted(chunks))

        with open(filename, "rb") as file:
            data = file.read()

        assert gathereddata == data

    @pytest.mark.parametrize("inrange", [(False, False), (False, True), (True, True)])
    @pytest.mark.parametrize("condition", [0, 1, 2])
    def test_rafdp_getting_random_range_file(self, inrange, condition):
        first, second = self.first, self.second

        filename = "greatexpectations.txt"

        firstport = first.getport()
        secondport = second.getport()

        roothash = first.addfile(filename)
        assert second.addpeer("127.0.0.1", firstport)
        assert second.addhash(roothash)

        chunksize, lastchunksize, numchunks, estfilesize = second.gethashstats(roothash)
        assert estfilesize == os.path.getsize(filename)

        size, offset = generate_test_range(estfilesize, chunksize, *inrange, condition)
        gathereddata = second.getsizeoffsetfromhash(roothash, size, offset)
        with open(filename, "rb") as file:
            file.seek(offset)
            data = file.read(size)
        print(inrange, condition, len(data))
        assert gathereddata == data

def test_memfs():
    vfs = MemFS()
    vfs.addfile(9963739, "0100444", "videotest.webm")

    assert vfs.getattrs("/thisdoesnotexist") is None
    assert vfs.getattrs("/thisdoesnotexist/thisdoesnotexist.txt") is None

    rootfolder = vfs.getattrs("/")
    videotest = vfs.getattrs("/videotest.webm")

    assert rootfolder is not None
    assert videotest is not None

    assert rootfolder.filename == ""
    assert rootfolder.st_size == 8192
    assert oct(rootfolder.st_mode)[2] == "4"

    assert videotest.filename == "videotest.webm"
    assert videotest.st_size == 9963739
    assert oct(videotest.st_mode)[2] == "1"

    assert vfs.listdir("/thisdoesnotexist") is None
    assert vfs.listdir("/") == [videotest]

    vfs.addfile(490934, "0100444", "videotest.webm")
    videotest = vfs.getattrs("/videotest.webm")

    assert videotest.filename == "videotest.webm"
    assert videotest.st_size == 490934
    assert oct(videotest.st_mode)[2] == "1"
    assert len(vfs.files) == 2

def test_rafdp_tracker_support():
    app = Flask(__name__)

    peerlists = {}

    @app.route("/announce")
    def announce():
        ip, port, infohash = request.remote_addr, request.args["port"], request.args["info_hash"]
        port = int(port)

        if infohash in peerlists:
            peers = encode_peers(peerlists[infohash])
        else:
            peers = b""

        response = {b"complete": 0, b"downloaded": 0, b"incomplete": 0, b"interval": 0, b"peers": peers}
        response = bencodepy.encode(response)

        if infohash not in peerlists:
            peerlists[infohash] = []
        pair = (ip, port)
        if pair not in peerlists[infohash]:
            peerlists[infohash].append(pair)

        return response

    server = make_server("localhost", 7000, app)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()

    firstrpcport = 7284
    secondrpcport = 7285
    first = RAFDPProcess(firstrpcport)
    second = RAFDPProcess(secondrpcport)

    time.sleep(2)

    first.addurl("http://localhost:7000/announce")
    second.addurl("http://localhost:7000/announce")

    thehash = first.addfile("cat.jpg")
    second.addhash(thehash)

    while len(first.getpeers()) == 0 or len(second.getpeers()) == 0:
        time.sleep(1)

    first.close()
    second.close()

    server.shutdown()
    thread.join()