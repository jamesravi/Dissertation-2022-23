from rafdplib import RAFDPProcess
import subprocess
import signal
import os
from pathlib import Path

if os.name == "nt":
    pythonexe = "python"
else:
    pythonexe = "python3"

filename = "videotest.webm"

vfsprocess = subprocess.Popen([pythonexe, "virtfilesystem.py"])
input("8.1. Started virtual filesystem daemon (press enter to continue)")

rafdpprocess = RAFDPProcess(7284)
input("8.2. Started a RAFDP process (press enter to continue)")

thehash = rafdpprocess.addfile(filename)
input("8.3. Added the test file to the RAFDP process (press enter to continue)")

subprocess.Popen([pythonexe, "virtfilesystem-cli.py", "addrafdppeer", "127.0.0.1", str(rafdpprocess.getport())])
input("8.4. Added RAFDP peer to the virtual filesystem daemon (press enter to continue)")

subprocess.Popen([pythonexe, "virtfilesystem-cli.py", "addrafdphash", thehash])
input("8.5. Added RAFDP hash of the test file to the virtual filesystem (press enter to continue)")

subprocess.Popen([pythonexe, "virtfilesystem-cli.py", "mounthash", thehash, str(Path.home() / "Documents" / filename)])
print("8.6. Mount RAFDP hash of the test file in the Documents folder")

input("Exit?")

pid = int(subprocess.check_output([pythonexe, "rafdp-cli.py", "--rpcport", "7275", "getpid"]).decode("ascii"))
os.kill(pid, signal.SIGTERM)

rafdpprocess.close()
vfsprocess.terminate()
