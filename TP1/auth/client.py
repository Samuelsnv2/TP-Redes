import socket
import sys
import struct

def auth(host, port, command):
    host = str(host).strip()
    port = int(port)
    program = command[0]