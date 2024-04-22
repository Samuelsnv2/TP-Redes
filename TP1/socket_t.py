import socket
import json

class Socket:
    # implementation of socket stop-and-wait
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.socket = self.newSocket()
    
    def newSocket(self):
        # TCP socket
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0.1)
        return self.socket

    def close(self):
        if self.socket:
            self.socket.close()

    def __del__(self):
        return self.close()


class ServerError(Exception):
    # authentication failed exception
    def __init__(self, message='Auth Failed'):
        super().__init__(self.message)

class GameOver(ServerError):
    # Game Over exception
    def __init__(self, message='GameOver'):
        self.message = message
        super().__init__(self.message)