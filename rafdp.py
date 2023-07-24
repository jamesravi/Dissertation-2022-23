import socketserver
import threading
import time
import json
import argparse
import os
import logging
import tempfile
import base64
import platform
import subprocess
from pathlib import Path

import utils
from core import MerkleTree
from trackerclient import TrackerClient

files = {}
overalltree = MerkleTree()
peers = {}
reassemble = {}
tctimeout = time.time()
stopnow = False

def fix_udp_macos():
    if platform.system() == "Darwin":
        maxdatagram = subprocess.check_output(["sysctl", "net.inet.udp.maxdgram"])
        maxdatagram = int(maxdatagram.decode("ascii").strip().split(" ")[1])
        if maxdatagram != 65535:
            os.system("""osascript -e 'do shell script "sudo sysctl -w net.inet.udp.maxdgram=65535" with administrator privileges'""")

def add_file(filename):
    global overalltree
    if filename not in files:
        files[filename] = overalltree.generate_tree(filename)
    return files[filename]

def add_hash(rafdphash):
    global overalltree
    if not overalltree.key_in_tree(rafdphash):
        overalltree.set(rafdphash, setmissing=False)
    overalltree.addroothash(rafdphash)

def background(socket):
    global tctimeout
    global stopnow

    def addannouncedpeers(infohash):
        gotpeers = tc.announce(infohash, 0, 0, overalltree.roothashes[infohash])
        for peer in gotpeers:
            if peer not in peers:
                peers[peer] = {"valid": False, "lastcontact": 0, "missing": {}}

    while not stopnow:
        for peer in peers:
            if not peers[peer]["valid"]:
                if (time.time() - peers[peer]["lastcontact"]) > 30:
                    peers[peer]["lastcontact"] = time.time()
                    socket.sendto(b"RAFDPPING", peer)
            else:
                for missinghash in overalltree.get_missing():
                    if missinghash not in peers[peer]["missing"]:
                        peers[peer]["missing"][missinghash] = {"lastcontact": 0}
                    if (time.time() - peers[peer]["missing"][missinghash]["lastcontact"]) > 5:
                        peers[peer]["missing"][missinghash]["lastcontact"] = time.time()
                        socket.sendto((0).to_bytes(1, "big") + missinghash.encode("ascii"), peer)
        if (time.time() - tctimeout) > 10:
            for infohash in overalltree.roothashes:
                announce_thread = threading.Thread(target=addannouncedpeers, args=(infohash,))
                announce_thread.start()
            tctimeout = time.time()
        time.sleep(0.0000001)

class RAFDPHandler(socketserver.BaseRequestHandler):   
    def handle(self):
        data = self.request[0]
        socket = self.request[1]
        peer = self.client_address
        isunknown = False

        if data == b"RAFDPPING" or data == b"RAFDPPONG":
            if data == b"RAFDPPING":
                socket.sendto(b"RAFDPPONG", peer)
            if peer not in peers:
                peers[peer] = {"missing": {}}
            peers[peer]["valid"] = True
            peers[peer]["lastcontact"] = time.time()
        elif data[0] == 0:
            # Request from other peer for data belonging to some hash
            wantedhash = data[1:].decode("ascii")
            if overalltree.key_in_tree(wantedhash):
                typeid, tosendhash = overalltree.get(wantedhash, expandtuple=True)
                if typeid != 3:
                    # Non-binary data e.g. another hash (or pair of hashes)
                    tosendhash = tosendhash.encode("ascii")
                    socket.sendto((1).to_bytes(1, "big") + (0).to_bytes(1, "big") + tosendhash, peer)
                else:
                    # Actual binary data (the "leaf" of the Merkle tree)
                    # We split it into chunks so it will fit within a UDP packet
                    chunksize = 508
                    offsets = list(range(0, len(tosendhash), chunksize))
                    for index, i in enumerate(offsets):
                        tosendhashpart = (1).to_bytes(1, "big") + (1).to_bytes(1, "big")
                        tosendhashpart += utils.tovarint(index) + utils.tovarint(len(offsets))
                        tosendhashpart += utils.tovarint(len(wantedhash.encode("ascii")))
                        tosendhashpart += wantedhash.encode("ascii") + tosendhash[i:i + chunksize]
                        socket.sendto(tosendhashpart, peer)
        elif data[0] == 1:
            # Response from other peer containing result for requested hash
            datatypefield = data[1]
            gotdata = data[2:]
            if datatypefield == 0:
                # Non-binary data e.g. another hash (or pair of hashes)
                hasheddata = MerkleTree.generate_hash(gotdata)
                gotdata = gotdata.decode("ascii")
                if hasheddata in overalltree.get_missing():
                    overalltree.set(hasheddata, gotdata, setmissing=False)
                    overalltree.reduce_tree_size()
            elif datatypefield == 1:
                # Binary data chunk (which needs to be reassembled once all chunks received)
                index, gotdata = utils.fromvarint(gotdata)
                numoffsets, gotdata = utils.fromvarint(gotdata)
                hashlength, gotdata = utils.fromvarint(gotdata)
                thehash, gotdata = gotdata[0:hashlength].decode("ascii"), gotdata[hashlength:]
                if thehash not in reassemble:
                    reassemble[thehash] = {i:None for i in range(numoffsets)}
                reassemble[thehash][index] = gotdata
                if all(v is not None for v in reassemble[thehash].values()):
                    # All chunks received
                    reassembleddata = b"".join(reassemble[thehash][key] for key in sorted(reassemble[thehash]))
                    del reassemble[thehash]
                    hasheddata = MerkleTree.generate_hash(reassembleddata)
                    if hasheddata in overalltree.get_missing():
                        overalltree.set(hasheddata, reassembleddata, setmissing=False)
                        overalltree.reduce_tree_size()
        else:
            isunknown = True

        if not isunknown:
            logging.debug(f"{peer} wrote: {data}")
        else:
            logging.warning(f"{peer} wrote (is unknown): {data}")

class RPCHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        if self.client_address[0] != "127.0.0.1":
            logging.warning(f"Ignored request from {self.client_address[0]}, are you running the RPC server publicly?!")
            return

        data = json.loads(data.decode("ascii"))
        resp = {"success": True}
        if data["method"] == "addfile":
            resp["hash"] = add_file(data["filename"])
        elif data["method"] == "getport":
            resp["port"] = port
        elif data["method"] == "getpid":
            resp["pid"] = os.getpid()
        elif data["method"] == "addpeer":
            peer = (data["ip"], data["port"])
            if peer not in peers:
                peers[peer] = {"valid": False, "lastcontact": 0, "missing": {}}
        elif data["method"] == "addhash":
            add_hash(data["hash"])
        elif data["method"] == "gethash":
            thehash = data["hash"]
            if overalltree.key_in_tree(thehash):
                typeid, tosendhash = overalltree.get(thehash, expandtuple=True)
                if typeid != 3:
                    resp["hashed"] = tosendhash
                    resp["encoded"] = False
                else:
                    resp["hashed"] = base64.b64encode(tosendhash).decode("ascii")
                    resp["encoded"] = True
            else:
                overalltree.set(thehash, None, setmissing=False)
                resp["success"] = False
        elif data["method"] == "addurl":
            tc.add_url(data["url"])
        elif data["method"] == "getpeers":
            resp["peers"] = list(peers.keys())
        else:
            raise Exception(data)

        socket.sendto(json.dumps(resp).encode("ascii"), self.client_address)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("rpcport", type=int, nargs="?", default=7284, help="RPC port")
    parser.add_argument("rafdpport", type=int, nargs="?", default=0, help="RAFDP port")
    args = parser.parse_args()

    logname = Path(tempfile.gettempdir()) / "rafdp" / "logs" / (str(args.rpcport) + ".log")
    logname.parent.mkdir(parents=True, exist_ok=True)
    loglevel = logging.INFO

    logging.basicConfig(
        filename=logname,
        filemode="w",
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=loglevel,
        datefmt='%Y-%m-%d %H:%M:%S')

    logging.getLogger().addHandler(logging.StreamHandler())

    fix_udp_macos()

    server = socketserver.UDPServer(("0.0.0.0", args.rafdpport), RAFDPHandler)
    port = server.server_address[1]
    tc = TrackerClient(port)
    logging.info(f"RAFDP server listening on port {port}")
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    background_thread = threading.Thread(target=background, args=(server.socket,))
    background_thread.daemon = True
    background_thread.start()

    # MUST ALWAYS RUN ON 127.0.0.1 OTHERWISE SECURITY RISK
    rpcserver = socketserver.UDPServer(("127.0.0.1", args.rpcport), RPCHandler)
    logging.info(f"RAFDP RPC server listening on port {rpcserver.server_address[1]}")
    rpcserver_thread = threading.Thread(target=rpcserver.serve_forever)
    rpcserver_thread.daemon = True
    rpcserver_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Halting RAFDP server...")
        server.shutdown()
        server_thread.join()
        stopnow = True
        background_thread.join()
        rpcserver.shutdown()
        rpcserver_thread.join()

logging.info("RAFDP server has successfully been shut down.")