import socket
import struct
import time

# Constants
SYNC = 0xDCC023C2
HEADER_SIZE = 14  # SYNC (x2) + checksum + length + ID + flags  
MAX_PAYLOAD = 4096
RETRANSMIT_TIMEOUT = 1.0 
MAX_RETRIES = 16

# Flags
ACK_FLAG = 0x80
END_FLAG = 0x40
RST_FLAG = 0x20

# Frame structure (simplified for example)
class DCCNETFrame:
    def __init__(self, id, flags, payload=b''):
        self.id = id
        self.flags = flags
        self.payload = payload

# Internet Checksum calculation (reference: https://tools.ietf.org/html/rfc1071)
def internet_checksum(data):
    checksum = 0
    n = len(data)
    i = 0

    # Handle data in 16-bit chunks
    while i < n - 1:
        w = (data[i] << 8) | data[i + 1]  # Combine bytes into a 16-bit word
        checksum += w
        i += 2

    # Handle the last byte if the data length is odd
    if n % 2:
        checksum += data[i] << 8  # Left-shift the last byte

    # Fold 32-bit checksum to 16 bits
    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum += (checksum >> 16)  # Add carry if any

    return ~checksum & 0xFFFF  # One's complement and mask to 16 bits

# Encode a DCCNET frame
def encode_frame(frame):
    # 1. Pack the header with a placeholder checksum of 0
    header_without_checksum = struct.pack('!IIHHBB', SYNC, SYNC, 0, len(frame.payload), frame.id, frame.flags)

    # 2. Calculate checksum over header (with 0 checksum) and payload
    data_to_checksum = header_without_checksum + frame.payload
    checksum = internet_checksum(data_to_checksum)

    # 3. Repack the header with the correct checksum
    header = struct.pack('!IIHHBB', SYNC, SYNC, checksum, len(frame.payload), frame.id, frame.flags)

    print(f"Header before checksum: {header_without_checksum!r}")
    print(f"Payload: {frame.payload!r}")
    print(f"Data to checksum: {data_to_checksum!r}")
    print(f"Encoded Checksum: {checksum:04X}")

    return header + frame.payload

# Decode a DCCNET frame
def decode_frame(data):
    if len(data) < HEADER_SIZE:
        return None

    # Unpack header, but exclude the checksum field for now
    sync1, sync2, _, length, id, flags = struct.unpack('!IIHHBB', data[:HEADER_SIZE])

    if sync1 != SYNC or sync2 != SYNC:
        raise ValueError("Invalid SYNC pattern")

    if len(data) < HEADER_SIZE + length:
        return None

    payload = data[HEADER_SIZE:HEADER_SIZE + length]

    # Now, extract the received checksum from the header
    received_checksum = struct.unpack('!H', data[8:10])[0]

    # Calculate checksum on header (with 0 checksum) and payload
    data_to_checksum = bytearray(data)  # Create a mutable copy
    data_to_checksum[8:10] = b'\x00\x00'  # Zero out the checksum field
    calculated_checksum = internet_checksum(data_to_checksum)

    print(f"Received header: {(sync1, sync2, received_checksum, length, id, flags)!r}")
    print(f"Received payload: {payload!r}")
    print(f"Decoded Checksum: {received_checksum:04X}, Calculated: {calculated_checksum:04X}")

    if calculated_checksum != received_checksum:
        print(f"Checksum mismatch: Expected {received_checksum:04X}, Calculated {calculated_checksum:04X}")
        raise ValueError("Checksum mismatch")

    return DCCNETFrame(id, flags, payload)

class DCCNETConnection:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.current_id = 0  # ID of the next frame to send
        self.last_received_id = None  # ID of the last correctly received frame
        self.send_buffer = b''  # Buffer for incomplete messages
        self.send_timer = None  # Timer for retransmissions
        self.retry_count = 0
        self.last_sent_frame = None
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sock.close()

    def send_data(self, data):
        frame = DCCNETFrame(self.current_id, 0, data)
        self.last_sent_frame = encode_frame(frame)  # Store the last sent frame
        self.sock.sendall(self.last_sent_frame)

        # Start the retransmission timer if not already running
        if not self.send_timer:
            self.send_timer = time.time()
            self.retry_count = 1

    def receive_data(self):
        while True:
            if len(self.send_buffer) < HEADER_SIZE:
                break  # Incomplete frame, wait for more data
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.send_buffer += data
            except socket.error as e:
                print(f"Error receiving data: {e}")
                break

            while True:
                print(f"Received raw data: {self.send_buffer!r}")

                if len(self.send_buffer) < HEADER_SIZE:
                    break  # Incomplete frame, wait for more data

                frame = decode_frame(self.send_buffer)
                if frame is None:
                    break  # Incomplete frame, wait for more data

                self.send_buffer = self.send_buffer[HEADER_SIZE + len(frame.payload):]

                if self.is_valid_frame(frame):
                    self.last_received_id = frame.id
                    self.send_ack()
                    if frame.flags & ACK_FLAG:
                        self.current_id += 1
                        if self.send_timer:
                            self.send_timer = None
                            self.retry_count = 0
                    else:
                        return frame.payload

            # Handle timeout only after processing received data
            self.handle_timeout() 

    def is_valid_frame(self, frame):
        # Frame validation logic
        if frame.flags & ACK_FLAG:
            # Acknowledgement frame
            return frame.id == self.current_id - 1  # ACK should match the previous frame ID
        elif frame.flags & RST_FLAG:
            # Reset frame
            self.sock.close()
            return False
        else:
            # Data frame
            if self.last_received_id is not None and frame.id <= self.last_received_id:
                # Ignore duplicate or out-of-order frames
                return False
            return True 

    def send_ack(self):
        ack_frame = DCCNETFrame(self.last_received_id, ACK_FLAG)
        self.sock.sendall(encode_frame(ack_frame))

    def handle_timeout(self):
        if self.send_timer and time.time() - self.send_timer > RETRANSMIT_TIMEOUT:
            if self.retry_count < MAX_RETRIES:
                # Resend the unacknowledged frame
                self.sock.sendall(self.last_sent_frame)
                self.send_timer = time.time()
                self.retry_count += 1
            else:
                # Handle unrecoverable error
                self.send_rst()
                self.sock.close()

    def send_rst(self):
        rst_frame = DCCNETFrame(0, RST_FLAG)  # Use ID 0 for RST  
        self.sock.sendall(encode_frame(rst_frame))