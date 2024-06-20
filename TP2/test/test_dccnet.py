import unittest
import socket
from unittest.mock import patch

from dccnet import DCCNETConnection, encode_frame, decode_frame, internet_checksum

class TestDCCNET(unittest.TestCase):

    def test_encode_decode(self):
        """
        Tests the encoding and decoding of DCCNET frames.
        """
        frame = DCCNETConnection.DCCNETFrame(10, 0x80, b"test data")
        encoded = encode_frame(frame)
        decoded = decode_frame(encoded)

        self.assertEqual(decoded.id, frame.id)
        self.assertEqual(decoded.flags, frame.flags)
        self.assertEqual(decoded.payload, frame.payload)

    def test_checksum(self):
        """
        Tests the Internet checksum calculation.
        """
        data = b"\xdc\xc0\x23\xc2\xdc\xc0\x23\xc2\x00\x00\x00\x04\x00\x00\x00\x01"
        checksum = internet_checksum(data)
        self.assertEqual(checksum, 0xf8f1)

    @patch('socket.socket')
    def test_connection_send_receive(self, mock_socket):
        """
        Tests basic send and receive functionality of DCCNETConnection.
        """
        mock_socket.return_value.recv.side_effect = [
            encode_frame(DCCNETConnection.DCCNETFrame(0, 0x80)),  # ACK frame
            b"data1",
            b"data2",
            b""  # End of transmission
        ]

        conn = DCCNETConnection("rubick.snes.2advanced.dev", 51001)
        conn.send_data(b"test")

        data1 = conn.receive_data()
        data2 = conn.receive_data()

        self.assertEqual(data1, b"data1")
        self.assertEqual(data2, b"data2")

        # Verify that the connection is closed after receiving the end of transmission
        self.assertTrue(mock_socket.return_value.close.called)
    
    @patch('socket.socket')
    def test_invalid_sync(self, mock_socket):
        """
        Tests handling of frames with invalid SYNC patterns.
        """
        mock_socket.return_value.recv.return_value = b"\x00\x00\x23\xc2\xdc\xc0\x23\xc2" + encode_frame(DCCNETConnection.DCCNETFrame(0, 0x80))

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        with self.assertRaises(ValueError) as cm:
            conn.receive_data()

        self.assertEqual(str(cm.exception), "Invalid SYNC pattern")

    @patch('socket.socket')
    def test_checksum_mismatch(self, mock_socket):
        """
        Tests handling of frames with incorrect checksums.
        """
        invalid_checksum_frame = encode_frame(DCCNETConnection.DCCNETFrame(0, 0, b"data"))[:-2] + b"\x00\x00"  # Modify checksum to be invalid
        mock_socket.return_value.recv.return_value = invalid_checksum_frame

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        with self.assertRaises(ValueError) as cm:
            conn.receive_data()

        self.assertEqual(str(cm.exception), "Checksum mismatch")

    @patch('socket.socket')
    @patch('time.time')
    def test_retransmission(self, mock_time, mock_socket):
        """
        Tests the retransmission mechanism.
        """
        mock_time.side_effect = [0, 1.5, 2.5]  # Simulate time progression for retries
        mock_socket.return_value.recv.return_value = encode_frame(DCCNETConnection.DCCNETFrame(0, 0x80))

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")  # Send data, but no ACK received initially

        # Verify that send_data was called multiple times due to retransmissions
        self.assertGreater(mock_socket.return_value.sendall.call_count, 1)

        # Simulate the eventual arrival of the ACK
        conn.receive_data()

    @patch('socket.socket')
    def test_rst_handling(self, mock_socket):
        """
        Tests handling of RST frames.
        """
        mock_socket.return_value.recv.return_value = encode_frame(DCCNETConnection.DCCNETFrame(0xFFFF, 0x20))

        conn = DCCNETConnection("localhost", 12345)

        with self.assertRaises(ConnectionResetError):
            conn.receive_data()  # RST should trigger an exception

        self.assertTrue(mock_socket.return_value.close.called)  # Verify connection closure

    @patch('socket.socket')
    def test_data_ack_handling(self, mock_socket):
        """
        Tests handling of data and ACK frames.
        """
        mock_socket.return_value.recv.side_effect = [
            encode_frame(DCCNETConnection.DCCNETFrame(0, 0, b"data")),
            encode_frame(DCCNETConnection.DCCNETFrame(0, 0x80)),  # ACK frame
            b""  # End of transmission
        ]

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")

        data = conn.receive_data()
        self.assertEqual(data, b"data")

        # Verify that the connection is closed after receiving
        self.assertTrue(mock_socket.return_value.close.called)

    @patch('socket.socket')
    def test_send_rst(self, mock_socket):
        """
        Tests sending an RST frame.
        """
        mock_socket.return_value.recv.return_value = b""  # Simulate remote end closing connection

        conn = DCCNETConnection("localhost", 12345)
        conn.send_data(b"test")  # Attempt to send data

        conn.handle_timeout()  # Trigger RST due to unrecoverable error

        # Verify that sendall was called with an RST frame
        mock_socket.return_value.sendall.assert_called_with(encode_frame(DCCNETConnection.DCCNETFrame(0xFFFF, 0x20)))

        # Verify that the connection is closed
        self.assertTrue(mock_socket.return_value.close.called)

if __name__ == "__main__":
    unittest.main()