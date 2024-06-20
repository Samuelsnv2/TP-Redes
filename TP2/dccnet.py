import socket
import struct
import time

# Constants
SYNC = 0xDCC023C2
HEADER_SIZE = 12  # SYNC (x2) + checksum + length + ID + flags
MAX_PAYLOAD = 4096
RETRANSMIT_TIMEOUT = 1.0  # Retransmission timeout in seconds
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

    while i < n:
        if (i + 1) < n:
            c1 = data[i] << 8
            c2 = data[i + 1]
            checksum += (c1 + c2)
        elif i == n - 1:
            checksum += data[i] << 8
        i += 2

    while checksum >> 16:
        checksum = (checksum & 0xFFFF) + (checksum >> 16)

    checksum = ~checksum & 0xFFFF
    return checksum

# Encode a DCCNET frame into a byte array
def encode_frame(frame):
    header = struct.pack('>IIHBB', SYNC, SYNC, 0, len(frame.payload), frame.id, frame.flags)
    checksum = internet_checksum(header + frame.payload)
    header = struct.pack('>IIHBB', SYNC, SYNC, checksum, len(frame.payload), frame.id, frame.flags)
    return header + frame.payload

# Decode a byte array into a DCCNET frame
def decode_frame(data):
    header = struct.unpack('>IIHBB', data[:HEADER_SIZE])
    sync1, sync2, checksum, length, id, flags = header
    if sync1 != SYNC or sync2 != SYNC:
        raise ValueError("Invalid SYNC pattern")

    payload = data[HEADER_SIZE:]
    if len(payload) != length:
        raise ValueError("Invalid payload length")

    calculated_checksum = internet_checksum(data)
    if calculated_checksum != checksum:
        raise ValueError("Checksum mismatch")

    return DCCNETFrame(id, flags, payload)

class DCCNETConnection:
    def __init__(self, host, port):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((host, port))

        self.current_id = 0  # ID of the next frame to send
        self.last_received_id = None  # ID of the last correctly received frame
        self.last_received_checksum = None  # Checksum of the last received frame
        self.send_timer = None  # Timer for retransmissions
        self.retry_count = 0

    def send_data(self, data):
        frame = DCCNETFrame(self.current_id, 0, data)
        encoded_frame = encode_frame(frame)
        self.sock.sendall(encoded_frame)

        # Start the retransmission timer if not already running
        if not self.send_timer:
            self.send_timer = time.time()
            self.retry_count = 1

    def receive_data(self):
        while True:  # Continuously attempt to receive frames
            try:
                data = self.sock.recv(HEADER_SIZE + MAX_PAYLOAD)
                if not data:  # Connection closed by the remote end
                    break

                frame = decode_frame(data)

                # Validate and process the received frame
                if self.is_valid_frame(frame):
                    self.last_received_id = frame.id
                    self.last_received_checksum = internet_checksum(data)  # Store for retransmission detection
                    self.send_ack()  # Send acknowledgement
                    if frame.flags & END_FLAG:
                        # Handle end-of-transmission
                        self.sock.close()
                        break
                    return frame.payload  # Return received data

            except (ValueError, socket.error) as e:
                # Handle framing errors, checksum mismatches, socket errors
                print(f"Error receiving frame: {e}")  # Replace with proper logging

    def is_valid_frame(self, frame):
        # Frame validation logic
        if frame.flags & ACK_FLAG:
            # Acknowledgement frame
            return frame.id == self.current_id  # Check if it acknowledges the last sent frame
        elif frame.flags & RST_FLAG:
            # Reset frame
            self.sock.close()  # Close connection
            # ... (optional: process RST payload)
            return False  # Do not process further
        else:
            # Data frame
            if frame.id == self.last_received_id and frame.payload == self.last_received_checksum:
                # Retransmission
                self.send_ack()  # Re-send acknowledgement
                return False  # Do not process as new data
            else:
                # New data frame
                return frame.id != self.current_id  # Accept if ID is different from the last sent frame

    def send_ack(self):
        ack_frame = DCCNETFrame(self.last_received_id, ACK_FLAG)
        self.sock.sendall(encode_frame(ack_frame))

    def handle_timeout(self):
        # Retransmission logic when the timer expires
        if self.retry_count < MAX_RETRIES:
            # Resend the unacknowledged frame
            # ... (retrieve and re-send the last sent frame)
            self.send_timer = time.time()  # Restart the timer
            self.retry_count += 1
        else:
            # Handle unrecoverable error (e.g., RST)
            self.send_rst()
            self.sock.close()

    def send_rst(self):
        rst_frame = DCCNETFrame(0xFFFF, RST_FLAG)  # ID set to 0xFFFF for RST
        # ... (optional: add payload to RST frame)
        self.sock.sendall(encode_frame(rst_frame))
