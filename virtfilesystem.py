"""
Some code from https://github.com/rspivak/sftpserver is used here
Ruslan Spivak (MIT license)
Paramiko (LGPL 2.1 or later)
"""

import paramiko
from paramiko import ServerInterface, SFTPServerInterface, SFTPServer, SFTPHandle
from paramiko import AUTH_SUCCESSFUL, OPEN_SUCCEEDED, SFTP_NO_SUCH_FILE
from paramiko.sftp import SFTP_OP_UNSUPPORTED

from pathlib import PurePosixPath, Path
import socket
import time
import os
import platform
import subprocess
import logging
import argparse
import socketserver
import tempfile
import threading
import json
import ctypes

from rafdplib import RAFDPProcess
from utils import MemFS

def findrafdpfilesize(thehash):
    vfs.addfile(rafdpdaemon.gethashstats(thehash)[-1], "0100444", thehash)

class RPCHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0].strip()
        socket = self.request[1]
        if self.client_address[0] != "127.0.0.1":
            logging.warning(f"WARNING: Ignored request from {self.client_address[0]}, are you running the RPC server publicly?!")
            return

        data = json.loads(data.decode("ascii"))
        resp = {"success": True}
        if data["method"] == "addrafdphash":
            vfs.addfile(0, "0100444", data["hash"])
            announce_thread = threading.Thread(target=findrafdpfilesize, args=(data["hash"],))
            announce_thread.start()
        elif data["method"] == "addipfshash":
            result = subprocess.run(["ipfs", "files", "stat", "--size", f"/ipfs/{data['hash']}"], stdout=subprocess.PIPE)
            vfs.addfile(int(result.stdout), "0100444", data["hash"])
        elif data["method"] == "addrafdppeer":
            rafdpdaemon.addpeer(data["ip"], data["port"])
        elif data["method"] == "getpid":
            resp["pid"] = os.getpid()
        elif data["method"] == "addurl":
            rafdpdaemon.addurl(data["url"])
        elif data["method"] == "getrafdppeers":
            resp["peers"] = rafdpdaemon.getpeers()
        elif data["method"] == "symlink":
            if os.name == "nt":
                if ctypes.windll.shell32.IsUserAnAdmin():
                    os.symlink(r"\\sshfs\127.0.0.1!6050" + "\\" + data["hash"], data["path"])
                else:
                    resp["success"] = False
                    resp["message"] = "Admin privileges required, please re-run the virtual filesystem daemon as root."
            elif os.name == "posix":
                try:
                    os.symlink(os.path.expanduser("~/rafdpvs") + "/" + data["hash"], data["path"])
                except FileExistsError as e:
                    resp["success"] = False
                    resp["message"] = str(e)
        else:
            raise Exception(data)

        socket.sendto(json.dumps(resp).encode("ascii"), self.client_address)

class VFSServer(ServerInterface):
    def check_auth_password(self, username, password):
        # all are allowed
        return AUTH_SUCCESSFUL

    def check_auth_publickey(self, username, key):
        # all are allowed
        return AUTH_SUCCESSFUL

    def check_channel_request(self, kind, chanid):
        return OPEN_SUCCEEDED

    def get_allowed_auths(self, username):
        return "password,publickey"

class StubSFTPHandle(SFTPHandle):
    def __init__(self, filehash):
        self.filehash = filehash

    def read(self, offset, length):
        filehash = self.filehash
        if filehash.startswith("RAFDP"):
            result = rafdpdaemon.getsizeoffsetfromhash(filehash, length, offset)
            while result is None:
                time.sleep(0.01)
                result = rafdpdaemon.getsizeoffsetfromhash(filehash, length, offset)
            return result
        else:
            result = subprocess.run(["ipfs", "cat", filehash, "-o", str(offset), "-l", str(length)], stdout=subprocess.PIPE)
            if result.returncode != 0:
                raise Exception(result)
            return result.stdout

class VFSSFTPServer(SFTPServerInterface):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _realpath(self, path):
        return self.canonicalize(path)

    def list_folder(self, path):
        path = self._realpath(path)
        result = vfs.listdir(path)
        if result is not None:
            return result
        else:
            return SFTP_NO_SUCH_FILE

    def open(self, path, flags, attr):
        path = self._realpath(path)
        try:
            binary_flag = getattr(os, "O_BINARY",  0)
            flags |= binary_flag
            mode = getattr(attr, "st_mode", None)
            if mode is None:
                mode = 0o666
        except OSError as e:
            return SFTPServer.convert_errno(e.errno)
        if (flags & os.O_CREAT) and (attr is not None):
            return SFTP_OP_UNSUPPORTED
        if flags & os.O_WRONLY:
            if flags & os.O_APPEND:
                fstr = "ab"
            else:
                fstr = "wb"
        elif flags & os.O_RDWR:
            if flags & os.O_APPEND:
                fstr = "a+b"
            else:
                fstr = "r+b"
        else:
            fstr = "rb"
        if "r" not in fstr:
            return SFTP_OP_UNSUPPORTED
        fobj = StubSFTPHandle(PurePosixPath(path).name)
        return fobj

    def lstat(self, path):
        path = self._realpath(path)
        result = vfs.getattrs(path)
        if result is not None:
            return result
        else:
            return SFTP_NO_SUCH_FILE

def ssh_server_listen():
    while True:
        try:
            conn, addr = server_socket.accept()

            host_key = paramiko.RSAKey.from_private_key_file("id_rsa")
            transport = paramiko.Transport(conn)
            transport.add_server_key(host_key)
            transport.set_subsystem_handler("sftp", paramiko.SFTPServer, VFSSFTPServer)

            server = VFSServer()
            transport.start_server(server=server)

            channel = transport.accept()
        except socket.timeout:
            pass

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("rpcport", type=int, nargs="?", default=7274, help="RPC port")
    parser.add_argument("rafdpport", type=int, nargs="?", default=7275, help="RAFDP port")
    parser.add_argument("path", type=str, nargs="?", default="./test", help="Path to place virtual filesystem")
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

    vfs = MemFS()

    rafdpdaemon = RAFDPProcess(args.rafdpport)

    # MUST ALWAYS RUN ON 127.0.0.1 OTHERWISE SECURITY RISK
    rpcserver = socketserver.UDPServer(("127.0.0.1", args.rpcport), RPCHandler)
    logging.info(f"Virtual filesystem RPC server listening on port {rpcserver.server_address[1]}")
    rpcserver_thread = threading.Thread(target=rpcserver.serve_forever)
    rpcserver_thread.daemon = True
    rpcserver_thread.start()

    paramiko.common.logging.basicConfig(level=paramiko.common.DEBUG)  # WARNING, INFO, DEBUG etc.

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    server_socket.settimeout(0.5)
    server_socket.bind(("127.0.0.1", 6050))
    server_socket.listen(1)

    sshserver_thread = threading.Thread(target=ssh_server_listen)
    sshserver_thread.daemon = True
    sshserver_thread.start()

    if os.name == "posix":
        logging.info("Mounting drive in a few seconds, please wait...")
        time.sleep(2)
        macfolder = Path("~/rafdpvs")
        if macfolder.is_dir():
            os.system("umount ~/rafdpvs")
        else:
            macfolder.expanduser().mkdir(exist_ok=True)
        if platform.system() == "Darwin":
            os.system("sshfs -p 6050 anything@localhost:/ ~/rafdpvs -o password_stdin <<< 'anything'")
        else:
            os.system("echo 'anything' | sshfs -p 6050 anything@localhost:/ ~/rafdpvs -o password_stdin")
        logging.info("Mounted drive.")

    while True:
        time.sleep(1)
