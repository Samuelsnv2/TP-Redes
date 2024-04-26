import socket
import struct
import sys

def auth(host, port, command):
    host = str(host).strip()
    port = int(port)
    program = command[0]