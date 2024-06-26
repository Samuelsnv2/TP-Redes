import unittest
import socket
import struct
from unittest.mock import patch, MagicMock
import time
from dccnet import DCCNETFrame, DCCNETConnection, encode_frame, decode_frame, internet_checksum

class TestDCCNET(unittest.TestCase):

    def test_encode_decode(self):
        frame = DCCNETFrame(10, 0x80, b"test data")
        encoded = encode_frame(frame)
        decoded = decode_frame(encoded)

        self.assertEqual(decoded.id, frame.id)
        self.assertEqual(decoded.flags, frame.flags)
        self.assertEqual(decoded.payload, frame.payload)

    def test_checksum(self):
        """
        Tests the Internet checksum calculation.
        """
        data = struct.pack('>IIHHBB', 0xDCC023C2, 0xDCC023C2, 0, 4, 0, 1)
        checksum = internet_checksum(data)
        self.assertEqual(checksum, 65268)

    @patch('socket.socket')
    def test_connection_send_receive(self, mock_socket):
        mock_sock = MagicMock()
        mock_socket.return_value = mock_sock
        mock_sock.recv.side_effect = [
            encode_frame(DCCNETFrame(0, 0, b"data1")),
            encode_frame(DCCNETFrame(0, 0x80)),  # ACK
            encode_frame(DCCNETFrame(1, 0, b"data2")),
            encode_frame(DCCNETFrame(1, 0x80)),  # ACK
            b""
        ]

        conn = DCCNETConnection("rubick.snes.2advanced.dev", 51001)
        conn.send_data(b"test")
        data1 = conn.receive_data()
        conn.send_data(b"test2")
        data2 = conn.receive_data()

        self.assertEqual(data1, b"data1")
        self.assertEqual(data2, b"data2")

        # Verify that the connection is closed after receiving the end of transmission
        self.assertTrue(mock_sock.close.called)

    @patch('socket.socket')
    def test_invalid_sync(self, mock_socket):
        mock_socket.return_value.recv.return_value = b"\x00\x00\x23\xc2\xdc\xc0\x23\xc2" + encode_frame(DCCNETFrame(0, 0x80))

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        with self.assertRaises(ValueError) as cm:
            conn.receive_data()

        self.assertEqual(str(cm.exception), "Invalid SYNC pattern")

    @patch('socket.socket')
    def test_checksum_mismatch(self, mock_socket):
        frame = DCCNETFrame(0, 0, b"data")
        encoded_frame = encode_frame(frame)
        invalid_checksum_frame = encoded_frame[:-2] + b"\x11\x01"  # Modify checksum
        mock_socket.return_value.recv.return_value = invalid_checksum_frame

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        with self.assertRaises(ValueError) as cm:
            conn.receive_data()

        self.assertEqual(str(cm.exception), "Checksum mismatch")

    @patch('socket.socket')
    @patch('time.time')
    def test_retransmission(self, mock_time, mock_socket):
        mock_time.side_effect = [0, 1.5, 2.5]
        mock_socket.return_value.recv.side_effect = [
            encode_frame(DCCNETFrame(0, 0x80))  # Simulate ACK arrival
        ]

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        # Allow time for potential retransmissions
        time.sleep(0.1) 

        # Verify that send_data was called multiple times due to retransmissions
        self.assertGreater(mock_socket.return_value.sendall.call_count, 1)

        # Simulate the eventual arrival of the ACK
        conn.receive_data()

    @patch('socket.socket')
    def test_rst_handling(self, mock_socket):
        print("Entering test_rst_handling...") 
        mock_socket.return_value.recv.return_value = encode_frame(DCCNETFrame(0, 0x20))

        conn = DCCNETConnection("localhost", 12345)
        print("Connection created, about to call receive_data()")
        with self.assertRaises(ConnectionResetError) as cm:
            conn.receive_data()
        print("receive_data() completed") 

        self.assertTrue(mock_socket.return_value.close.called)

    @patch('socket.socket')
    def test_data_ack_handling(self, mock_socket):
        mock_socket.return_value.recv.side_effect = [
            encode_frame(DCCNETFrame(0, 0, b"data")),
            encode_frame(DCCNETFrame(0, 0x80)),
            b""
        ]

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        data = conn.receive_data()
        self.assertEqual(data, b"data")

        # Verify that the connection is closed after receiving the end of transmission
        self.assertTrue(mock_socket.return_value.close.called)

    @patch('socket.socket')
    def test_send_rst(self, mock_socket):
        mock_socket.return_value.recv.return_value = b""

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        conn.handle_timeout()

        # Calculate the correct checksum for the RST frame
        rst_frame = DCCNETFrame(0, 0x20)
        expected_rst_frame = encode_frame(rst_frame)

        # Verify that sendall was called with the correct RST frame
        mock_socket.return_value.sendall.assert_called_with(expected_rst_frame) 

        self.assertTrue(mock_socket.return_value.close.called)

if __name__ == "__main__":
    unittest.main()