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
    while n > 1:
        checksum += (data[i] << 8) + data[i + 1]  # Combine bytes into words
        i += 2
        n -= 2
        checksum = (checksum & 0xFFFF) + (checksum >> 16)  # 16-bit carry handling
    if n == 1:  # Handle odd-length case
        checksum += data[i] << 8
        checksum = (checksum & 0xFFFF) + (checksum >> 16)
    checksum = ~checksum & 0xFFFF
    return checksum

# Encode a DCCNET frame
def encode_frame(frame):
    # 1. Pack the header with a placeholder checksum of 0
    header = struct.pack('!IIHHBB', SYNC, SYNC, 0, len(frame.payload), frame.id, frame.flags) 
    
    print(f"Header before checksum: {header!r}")  # Print header bytes
    print(f"Payload: {frame.payload!r}")  # Print payload bytes

    data_to_checksum = header + frame.payload
    print(f"Data to checksum: {data_to_checksum!r}")  # Print combined data

    checksum = internet_checksum(data_to_checksum)
    print(f"Encoded Checksum: {checksum:04X}")  # Debugging: Print calculated checksum
    
    # 3. Repack the header with the correct checksum
    header = struct.pack('>IIHHBB', SYNC, SYNC, checksum, len(frame.payload), frame.id, frame.flags) 
    
    return header + frame.payload

# Decode a DCCNET frame
def decode_frame(data):
    if len(data) < HEADER_SIZE:
        return None  # Not enough data for a header

    header = struct.unpack('!IIHHBB', data[:HEADER_SIZE])
    sync1, sync2, checksum, length, id, flags = header

    if sync1 != SYNC or sync2 != SYNC:
        raise ValueError("Invalid SYNC pattern")

    # Ensure we have the complete frame before checksum verification
    if len(data) < HEADER_SIZE + length:
        return None  

    payload = data[HEADER_SIZE:HEADER_SIZE + length]

    print(f"Received header: {header!r}")  # Print received header
    print(f"Received payload: {payload!r}")  # Print received payload

    # Calculate checksum on the complete header
    calculated_checksum = internet_checksum(data[:HEADER_SIZE])
    print(f"Decoded Checksum: {checksum:04X}, Calculated: {calculated_checksum:04X}")  # Debugging
    if calculated_checksum != checksum:
        print(f"Checksum mismatch: Expected {checksum:04X}, Calculated {calculated_checksum:04X}")
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
            try:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.send_buffer += data
            except socket.error as e:
                print(f"Error receiving data: {e}")
                break

            while True:
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