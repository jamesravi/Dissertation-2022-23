import itertools
from multiformats import multibase, multihash
import random
import psutil
import utils


class MerkleTree:
    magic_header = "RAFDP"
    version_number = utils.tovarint(0)
    chunk_size = 16384  # 16 KiB
    hash_algorithm = "sha2-256"
    base_encoding = "base58btc"

    @classmethod
    def generate_hash(cls, data):
        # magic header + version number + multibase + multihash
        hashed = multihash.digest(data, cls.hash_algorithm)
        encoded = multibase.encode(hashed, cls.base_encoding)
        result = cls.magic_header + cls.version_number.decode("ascii") + encoded
        return result

    def __init__(self):
        self.tree = {}
        self.roothashes = {}

    def generate_tree(self, filename):
        chunkhashes = []
        tree = {}

        with open(filename, "rb") as file:
            while True:
                chunk = file.read(self.chunk_size)
                if not chunk:
                    break
                chunk = utils.tovarint(len(chunkhashes)) + chunk
                chunkhash = self.generate_hash(chunk)
                # pointer to offset in file stored in tree
                tree[chunkhash] = (filename, len(chunkhashes), self.chunk_size)
                chunkhashes.append(chunkhash)

        # generate merkle tree and determine root hash
        while len(chunkhashes) > 1:
            newchunkhashes = []
            for pair in itertools.zip_longest(*[iter(chunkhashes)] * 2):
                first, second = pair
                if second is None:
                    pair = first
                else:
                    pair = first + "," + second
                chunkhash = self.generate_hash(pair.encode("ASCII"))
                if chunkhash in tree:
                    raise Exception("Hash detected twice in tree?")
                tree[chunkhash] = pair
                newchunkhashes.append(chunkhash)
            chunkhashes = newchunkhashes

        self.tree.update(tree)

        roothash = chunkhashes[0]
        self.addroothash(roothash)

        return roothash

    def addroothash(self, roothash, filesize=75856):
        self.roothashes[roothash] = filesize

    def set(self, key, value=None, setmissing=True):
        if setmissing:
            if type(value) is str:
                if "," in value:
                    # pair of hashes
                    first, second = value.split(",")
                    self.tree[first] = None
                    self.tree[second] = None
                else:
                    # single hash
                    self.tree[value] = None
            elif type(value) is tuple or type(value) is bytes or value is None:
                pass
            else:
                raise Exception(value)
        self.tree[key] = value

    def key_in_tree(self, key):
        return key in self.tree

    def get(self, key, expandtuple=False):
        value = self.tree[key]
        typeid = None
        if type(value) is str:
            if value.startswith("RAFDP"):
                if ",RAFDP" in value:
                    # pair of hashes
                    typeid = 1
                else:
                    # single hash
                    typeid = 0
        elif type(value) is tuple:
            if expandtuple:
                # binary chunk data
                typeid = 3
                with open(value[0], "rb") as file:
                    file.seek(value[1]*value[2])
                    filepart = file.read(value[2])
                filepart = utils.tovarint(value[1]) + filepart
                value = filepart
            else:
                typeid = 2
        elif value is None:
            typeid = 5
        elif type(value) is bytes:
            # binary chunk data
            typeid = 3
        else:
            raise Exception(value)

        if typeid is None:
            raise Exception(value)
        return typeid, value

    def get_missing(self):
        return [key for key in self.tree if self.tree[key] is None]

    def is_complete(self):
        return len(self.get_missing()) == 0

    def reduce_tree_size(self):
        # When running out of RAM
        if psutil.virtual_memory().percent >= 95:
            choices = list(set(self.tree.keys()) - set(self.roothashes))
            if len(choices) > 0:
                del self.tree[random.choice(choices)]
