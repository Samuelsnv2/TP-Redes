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
    
    def send(self, message, n=1):
        # send a requisition and wait for response
        resp = []
        json_message = json.dumps(message)
        self.socket.sendto(json_message.encode(), (self.host, self.port))
        while len(resp) < n:
            # wait for response
            try:
                data, _ = self.socket.recvfrom(1024)
                data = json.loads(data.decode())
                if data['type'] == 'gameover':
                    raise GameOver()
                resp.append(data)

            except socket.timeout:
                if not len(resp):
                    return self.send(message)
                break
            except json.decoder.JSONDecodeError as e:
                if 'gameover' in str(data):
                    raise GameOver()
        if len(resp) == 1:
            return resp[0]
        return resp

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