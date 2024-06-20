import hashlib
import socket

from dccnet import DCCNETConnection  # Import your DCCNET implementation

SERVER_HOST = "rubick.snes.2advanced.dev"  # Replace with the actual server
SERVER_PORT = 51001  # Replace with the actual port

def md5_app(host, port):
    with DCCNETConnection(host, port) as conn:
        while True:
            data = conn.receive_data()
            if not data:  # End of transmission
                break

            line = data.decode('utf-8').strip()  # Assuming lines are UTF-8 encoded
            md5_digest = hashlib.md5(line.encode('utf-8')).hexdigest()
            conn.send_data(md5_digest.encode('utf-8') + b'\n')  # Send MD5 as hex string with newline

if __name__ == "__main__":
    md5_app(SERVER_HOST, SERVER_PORT)