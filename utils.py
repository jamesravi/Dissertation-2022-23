from paramiko import SFTPAttributes
from pathlib import PurePosixPath
import time
import struct

def tovarint(integer):
    # single hex digit representing the length of the integer
    # + <variable length> byte big endian integer in hex
    # maximum possible range is 0 to 16**15 - 1 (1,152,921,504,606,846,975) inclusive
    assert integer >= 0, f"Integer must be positive, not {integer}"
    varint = hex(integer)[2:]
    if len(varint) > 15:
        raise Exception(f"{integer} is too large (more than 15 digits in hex) to be converted to varint")
    varint = hex(len(varint))[2:] + varint
    return varint.encode("ascii")
    
def fromvarint(data):
    length, data = int(chr(data[0]), 16), data[1:]
    integer, leftover = int(data[0:length].decode("ascii"), 16), data[length:]
    return integer, leftover

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def encode_peers(peerlist):
    peers = b""
    for ip, port in peerlist:
        pair = list(map(int, ip.split("."))) + [port]
        peers += struct.pack("!BBBBH", *pair)
    return peers

def decode_peers(peers):
    peerlist = []
    for chunk in chunks(peers, 6):
        ip = struct.unpack("!BBBB", chunk[:4])
        port = struct.unpack("!H", chunk[4:])
        ip, port = ".".join(map(str, ip)), port[0]
        peerlist.append((ip, port))
    return peerlist

###

def createSFTPobject(st_size, st_mode, st_atime, st_mtime, filename, flags=0, st_uid=0, st_gid=0):
    SFTPobject = SFTPAttributes()
    SFTPobject._flags = flags
    SFTPobject.st_size = st_size
    SFTPobject.st_uid = st_uid
    SFTPobject.st_gid = st_gid
    SFTPobject.st_mode = int(st_mode, 8)
    SFTPobject.st_atime = st_atime
    SFTPobject.st_mtime = st_mtime
    SFTPobject.filename = filename
    return SFTPobject

class MemFS:
    def __init__(self):
        self.files = {}
        self.addfile(8192, "40444", "/")

    def addfile(self, filesize, mode, path):
        if type(path) is str:
            path = PurePosixPath(path)
        path = "/" / path
        SFTPobject = createSFTPobject(filesize, mode, time.time(), time.time(), path.name)
        self.files[str(path)] = (path, SFTPobject)

    def listdir(self, pathtolist):
        if type(pathtolist) is str:
            pathtolist = PurePosixPath(pathtolist)
        # Check if folder exists
        attrs = self.getattrs(pathtolist)
        if attrs is None or oct(attrs.st_mode)[2] != "4":
            return None
        # Find items in folder
        returnthese = []
        for filepath, SFTPobject in self.files.values():
            if pathtolist in filepath.parents:
                returnthese.append(SFTPobject)
        return returnthese

    def getattrs(self, pathtoget):
        if type(pathtoget) is str:
            pathtoget = PurePosixPath(pathtoget)
        if str(pathtoget) in self.files:
            return self.files[str(pathtoget)][1]
        return None
