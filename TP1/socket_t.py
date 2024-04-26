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
    
    def sendM(self, message):
        # send a message to the server
        json_message = json.dumps(message)
        self.socket.sendto(json_message.encode(), (self.host, self.port))
        return self.socket

    def recvM(self):
        # receive a message from the server
        try:
            data, _ = self.socket.recvfrom(1024)
            data = json.loads(data.decode())
            if data['type'] == 'gameover':
                raise GameOver()
            return data
        except socket.timeout:
            return None

    def send(self, message, n=1):
        # send a requisition and wait for response
        resp_type = {'authreq': 'authresp', 'getcannons': 'cannons', 'getturn': 'state', 'shot': 'shotresp'}
        resp = []
        json_message = json.dumps(message)
        try:
            self.socket.send(json_message.encode(), (self.host, self.port))
        except Exception as e:
            print(e)
            raise GameOver()
        while len(resp) < n:
            # wait for response
            try:
                data, _ = self.socket.recvfrom(1024)
                data = json.loads(data.decode())
                if data['type'] == 'gameover':
                    raise GameOver()
                if type == 'quit':
                    return data
                if data['type'] == resp_type[message['type']]:
                    resp.append(data)
            except socket.timeout:
                if not len(resp):
                    return self.send(message, n)
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
        self.message = message
        super().__init__(self.message)

class GameOver(ServerError):
    # Game Over exception
    def __init__(self, message='GameOver', data=''):
        self.message = message
        self.data = data
        super().__init__(self.message)