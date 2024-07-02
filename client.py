import sys
import socket
import struct

# Constants for message types
INDIVIDUAL_TOKEN_REQUEST = 1
INDIVIDUAL_TOKEN_RESPONSE = 2
INDIVIDUAL_TOKEN_VALIDATION = 3
INDIVIDUAL_TOKEN_STATUS = 4
GROUP_TOKEN_REQUEST = 5
GROUP_TOKEN_RESPONSE = 6
GROUP_TOKEN_VALIDATION = 7
GROUP_TOKEN_STATUS = 8

# Error codes
INVALID_MESSAGE_CODE = 1
INCORRECT_MESSAGE_LENGTH = 2
INVALID_PARAMETER = 3
INVALID_SINGLE_TOKEN = 4
ASCII_DECODE_ERROR = 5

def send_message(host, port, message):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.sendto(message, (host, port))
        response, _ = s.recvfrom(1024)
    return response

def individual_token_request(id, nonce):
    message = struct.pack("!H12sI", INDIVIDUAL_TOKEN_REQUEST, id.encode("ascii"), nonce)
    return send_message(sys.argv[1], int(sys.argv[2]), message)

def individual_token_validation(sas):
    id, nonce, token = sas.split(":")
    message = struct.pack("!H12sI64s", INDIVIDUAL_TOKEN_VALIDATION, id.encode("ascii"), int(nonce), bytes.fromhex(token))
    return send_message(sys.argv[1], int(sys.argv[2]), message)

def group_token_request(n, *sas_list):
    sas_bytes = b"".join(struct.pack("!12sI64s", id.encode("ascii"), int(nonce), bytes.fromhex(token)) for sas in sas_list)
    message = struct.pack("!H2s", GROUP_TOKEN_REQUEST, struct.pack("!H", n)) + sas_bytes
    return send_message(sys.argv[1], int(sys.argv[2]), message)

def group_token_validation(gas):
    sas_tokens = gas.split("+")
    n = len(sas_tokens)
    sas_bytes = b"".join(struct.pack("!12sI64s", *sas.split(":")) for sas in sas_tokens)
    message = struct.pack("!H2s", GROUP_TOKEN_VALIDATION, struct.pack("!H", n)) + sas_bytes
    return send_message(sys.argv[1], int(sys.argv[2]), message)

def parse_response(response):
    message_type, = struct.unpack("!H", response[:2])
    if message_type == INDIVIDUAL_TOKEN_RESPONSE:
        id, nonce, token = struct.unpack("!12sI64s", response[2:])
        return f"{id.decode('ascii')}:{nonce}:{token.hex()}"
    elif message_type == INDIVIDUAL_TOKEN_STATUS or message_type == GROUP_TOKEN_STATUS:
        id, nonce, token, status = struct.unpack("!12sI64sB", response[2:])
        return status
    else:
        return None  # Handle other response types as needed

def main():
    if len(sys.argv) < 4:
        print("Usage: ./client <host> <port> <command>")
        sys.exit(1)

    command = sys.argv[3]

    if command == "itr" and len(sys.argv) == 6:
        response = individual_token_request(sys.argv[4], int(sys.argv[5]))
        print(parse_response(response))
    elif command == "itv" and len(sys.argv) == 5:
        response = individual_token_validation(sys.argv[4])
        print(parse_response(response))
    elif command == "gtr" and len(sys.argv) >= 5:
        response = group_token_request(int(sys.argv[4]), *sys.argv[5:])
        print(parse_response(response))
    elif command == "gtv" and len(sys.argv) == 5:
        response = group_token_validation(sys.argv[4])
        print(parse_response(response))
    else:
        print("Invalid command or incorrect number of arguments")
        sys.exit(1)

if __name__ == "__main__":
    main()
