import socket
import json
import argparse

rpcport = 7274

def sendjson(data):
    data = json.dumps(data).encode("ascii")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(5)
        sock.sendto(data, ("127.0.0.1", rpcport))
        result, _ = sock.recvfrom(1024)
    return json.loads(result.decode("ascii"))

def addrafdphash(args):
    thehash = args.hash
    result = sendjson({"method": "addrafdphash", "hash": thehash})
    if result["success"]:
        print(f"Added hash {thehash}")
    else:
        print("ERROR: " + result["message"])

def addipfshash(args):
    thehash = args.hash
    result = sendjson({"method": "addipfshash", "hash": thehash})
    if result["success"]:
        print(f"Added hash {thehash}")
    else:
        print("ERROR: " + result["message"])

def addpeer(args):
    ip, port = args.ip, args.port
    result = sendjson({"method": "addrafdppeer", "ip": ip, "port": port})
    if result["success"]:
        print(f"Added {ip}:{port} as peer")
    else:
        print("ERROR: " + result["message"])

def getpid(args):
    result = sendjson({"method": "getpid"})
    if result["success"]:
        print(result["pid"])
    else:
        print("ERROR: " + result["message"])

def addtrackerurl(args):
    url = args.url
    result = sendjson({"method": "addurl", "url": url})
    if result["success"]:
        print(f"Added {url}")
    else:
        print("ERROR: " + result["message"])

def getpeers(args):
    result = sendjson({"method": "getrafdppeers"})
    if result["success"]:
        for peer in result["peers"]:
            print(*peer)
    else:
        print("ERROR: " + result["message"])

def mounthash(args):
    result = sendjson({"method": "symlink", "hash": args.hash, "path": args.path})
    if result["success"]:
        print(f"Mounted {args.hash} at {args.path}")
    else:
        print("ERROR: " + result["message"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpcport", nargs="?", default=rpcport, type=int)

    subparsers = parser.add_subparsers()

    addrafdphashparser = subparsers.add_parser("addrafdphash", help="Add RAFDP hash to be downloaded")
    addrafdphashparser.add_argument("hash", type=str)
    addrafdphashparser.set_defaults(func=addrafdphash)

    addipfshashparser = subparsers.add_parser("addipfshash", help="Add IPFS hash to be downloaded")
    addipfshashparser.add_argument("hash", type=str)
    addipfshashparser.set_defaults(func=addipfshash)

    addpeerparser = subparsers.add_parser("addrafdppeer", help="Add a RAFDP peer to connect to")
    addpeerparser.add_argument("ip", type=str)
    addpeerparser.add_argument("port", type=int)
    addpeerparser.set_defaults(func=addpeer)

    addrafdphashparser = subparsers.add_parser("getpid", help="Gets the process number of the server")
    addrafdphashparser.set_defaults(func=getpid)

    addurlparser = subparsers.add_parser("addtrackerurl", help="Add BitTorrent tracker url for peer discovery")
    addurlparser.add_argument("url", type=str)
    addurlparser.set_defaults(func=addtrackerurl)

    getpeersparser = subparsers.add_parser("getrafdppeers", help="Get list of peers currently added")
    getpeersparser.set_defaults(func=getpeers)

    mounthashparser = subparsers.add_parser("mounthash", help="Make hash available at path")
    mounthashparser.add_argument("hash", type=str)
    mounthashparser.add_argument("path", type=str)
    mounthashparser.set_defaults(func=mounthash)

    args = parser.parse_args()
    rpcport = args.rpcport
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
