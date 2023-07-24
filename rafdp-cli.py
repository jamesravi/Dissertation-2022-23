import argparse
from rafdplib import RAFDPProcess

rpcport = 7284

rafdpprocess = None

def addfile(args):
    filename = args.filename
    print(rafdpprocess.addfile(filename))

def getport(args):
    print(rafdpprocess.getport())

def getpid(args):
    print(rafdpprocess.getpid())

def addpeer(args):
    ip, port = args.ip, args.port
    if rafdpprocess.addpeer(ip, port):
        print(f"Added {ip}:{port} as peer")
    else:
        raise Exception(f"Failed adding {ip}:{port} as peer")

def addhash(args):
    rafdphash = args.hash
    if rafdpprocess.addhash(rafdphash):
        print(f"Added hash {rafdphash}")
    else:
        raise Exception(f"Failed adding hash {rafdphash}")

def gethash(args):
    rafdphash = args.hash
    print(rafdpprocess.gethash(rafdphash))

def addurl(args):
    url = args.url
    print(rafdpprocess.addurl(url))

def getpeers(args):
    for peer in rafdpprocess.getpeers():
        print(*peer)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpcport", nargs="?", default=rpcport, type=int)

    subparsers = parser.add_subparsers()

    addfileparser = subparsers.add_parser("addfile", help="Add a file to be shared")
    addfileparser.add_argument("filename", type=str)
    addfileparser.set_defaults(func=addfile)

    getportparser = subparsers.add_parser("getport", help="Gets the port number of the server")
    getportparser.set_defaults(func=getport)

    getportparser = subparsers.add_parser("getpid", help="Gets the process number of the server")
    getportparser.set_defaults(func=getpid)

    addpeerparser = subparsers.add_parser("addpeer", help="Add a file to be shared")
    addpeerparser.add_argument("ip", type=str)
    addpeerparser.add_argument("port", type=int)
    addpeerparser.set_defaults(func=addpeer)

    addhashparser = subparsers.add_parser("addhash", help="Add hash to be downloaded")
    addhashparser.add_argument("hash", type=str)
    addhashparser.set_defaults(func=addhash)

    gethashparser = subparsers.add_parser("gethash", help="Attempt to get content of hash (if it has been downloaded)")
    gethashparser.add_argument("hash", type=str)
    gethashparser.set_defaults(func=gethash)

    addurlparser = subparsers.add_parser("addtrackerurl", help="Add BitTorrent tracker url for peer discovery")
    addurlparser.add_argument("url", type=str)
    addurlparser.set_defaults(func=addurl)

    getpeersparser = subparsers.add_parser("getpeers", help="Get list of peers currently added")
    getpeersparser.set_defaults(func=getpeers)

    args = parser.parse_args()
    rpcport = args.rpcport
    rafdpprocess = RAFDPProcess(rpcport, openprocess=False)
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()