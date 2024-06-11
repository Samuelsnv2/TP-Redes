import struct
import socket
import hashlib
import time
import sys

SYNC = 0xDCC023C2
SYNC_BYTES = struct.pack('!I', SYNC)
CHECKSUM_SIZE = 2

def internet_checksum(data):
    if len(data) % 2:
        data += b'\x00'
    checksum = sum(struct.unpack('!%dH' % (len(data) // 2), data))
    checksum = (checksum >> 16) + (checksum & 0xffff)
    checksum += (checksum >> 16)
    return ~checksum & 0xffff

def create_frame(data, seq_id, ack=False, end=False):
    length = len(data)
    flags = (ack << 7) | (end << 6)
    header = struct.pack('!IIHHHB', SYNC, SYNC, 0, length, seq_id, flags)
    checksum = internet_checksum(header + data)
    header = struct.pack('!IIHHHB', SYNC, SYNC, checksum, length, seq_id, flags)
    return header + data

def parse_frame(frame):
    sync1, sync2, checksum, length, seq_id, flags = struct.unpack('!IIHHHB', frame[:13])
    if sync1 != SYNC or sync2 != SYNC:
        return None, None, None, None
    data = frame[13:13 + length]
    if internet_checksum(frame[:4] + b'\x00\x00' + frame[6:]) != 0:
        return None, None, None, None
    return seq_id, flags, data, checksum

class DCCNet:
    def __init__(self, conn):
        self.conn = conn
        self.seq_id = 0
        self.ack_id = 1
        self.last_frame = None

    def send(self, data, end=False):
        while True:
            frame = create_frame(data, self.seq_id, end=end)
            self.conn.sendall(frame)
            try:
                self.conn.settimeout(1)
                ack_frame = self.conn.recv(1024)
                ack_id, flags, _, _ = parse_frame(ack_frame)
                if ack_id == self.seq_id and flags & 0x80:
                    self.seq_id = 1 - self.seq_id
                    break
            except socket.timeout:
                continue

    def receive(self):
        while True:
            frame = self.conn.recv(1024)
            seq_id, flags, data, _ = parse_frame(frame)
            if seq_id is None or seq_id == self.ack_id:
                continue
            self.ack_id = seq_id
            ack_frame = create_frame(b'', self.ack_id, ack=True)
            self.conn.sendall(ack_frame)
            return data, flags

def transfer_file(server, port, input_file, output_file, is_server):
    if is_server:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('', port))
        sock.listen(1)
        conn, _ = sock.accept()
    else:
        sock = socket.create_connection((server, port))
        conn = sock

    dccnet = DCCNet(conn)

    if input_file:
        with open(input_file, 'rb') as f:
            while True:
                data = f.read(1024)
                if not data:
                    break
                dccnet.send(data)
        dccnet.send(b'', end=True)

    if output_file:
        with open(output_file, 'wb') as f:
            while True:
                data, flags = dccnet.receive()
                if flags & 0x40:
                    break
                f.write(data)

    conn.close()

def md5_client(server, port):
    sock = socket.create_connection((server, port))
    dccnet = DCCNet(sock)

    while True:
        data, flags = dccnet.receive()
        if not data:
            break
        md5 = hashlib.md5(data).hexdigest()
        dccnet.send(md5.encode('ascii') + b'\n')

    sock.close()

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == '-s':
        port = int(sys.argv[2])
        input_file = sys.argv[3] if len(sys.argv) > 3 else None
        output_file = sys.argv[4] if len(sys.argv) > 4 else None
        transfer_file(None, port, input_file, output_file, is_server=True)
    elif mode == '-c':
        server, port = sys.argv[2].split(':')
        port = int(port)
        input_file = sys.argv[3] if len(sys.argv) > 3 else None
        output_file = sys.argv[4] if len(sys.argv) > 4 else None
        transfer_file(server, port, input_file, output_file, is_server=False)
    elif mode == '-md5':
        server, port = sys.argv[2].split(':')
        port = int(port)
        md5_client(server, port)
