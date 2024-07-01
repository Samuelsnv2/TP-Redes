import argparse
import socket
import os

from dccnet import DCCNETConnection  # Import your DCCNET implementation

BUFFER_SIZE = 4096  # Size of data chunks for transfer

def xfer_client(host_port, input_file, output_file):
    """
    Implements the client-side functionality for file transfer.

    Args:
        host_port: IP address and port number of the server in format <IP>:<PORT>.
        input_file: Path to the file to be sent.
        output_file: Path to the file where received data will be stored.
    """
    host, port = host_port.split(':')
    with DCCNETConnection(host, int(port)) as conn:
        # Send file data
        with open(input_file, 'rb') as f:
            while True:
                data = f.read(BUFFER_SIZE)
                if not data:
                    conn.send_data(b'')  # Send empty frame with END flag to signal end of file
                    break
                conn.send_data(data)

        # Receive file data
        with open(output_file, 'wb') as f:
            while True:
                data = conn.receive_data()
                if not data:
                    break
                f.write(data)

def xfer_server(port, input_file, output_file):
    """
    Implements the server-side functionality for file transfer.

    Args:
        port: Port number to listen on.
        input_file: Path to the file to be sent.
        output_file: Path to the file where received data will be stored.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('', port))  # Bind to all interfaces on the specified port
        sock.listen(1)
        print(f"Server listening on port {port}")

        with sock.accept()[0] as conn:  # Accept a single connection
            dccnet_conn = DCCNETConnection(conn.getsockname()[0], conn.getsockname()[1])

            # Receive file data
            with open(output_file, 'wb') as f:
                while True:
                    data = dccnet_conn.receive_data()
                    if not data:
                        break
                    f.write(data)

            # Send file data
            with open(input_file, 'rb') as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        dccnet_conn.send_data(b'')  # Send empty frame with END flag to signal end of file
                        break
                    dccnet_conn.send_data(data)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DCCNET File Transfer Application")
    parser.add_argument("-s", "--server", type=int, help="Run as server (specify port)")
    parser.add_argument("-c", "--client", type=str,
                        help="Run as client (specify host and port in format <IP>:<PORT>)")
    parser.add_argument("input", type=str, help="Input file path")
    parser.add_argument("output", type=str, help="Output file path")
    args = parser.parse_args()

    if args.server:
        xfer_server(args.server, args.input, args.output)
    elif args.client:
        xfer_client(args.client, args.input, args.output)
    else:
        parser.print_help()