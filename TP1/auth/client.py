from auth.messager import *
import socket

def auth(host, port, command):
    '''
    Check if at least 3 args are provided - host, port and command
    extract host and port from the command
    '''
    host = str(host).strip()
    port = int(port)
    type = command[0]
    try:
        messager_o = messager(type=type)
    except Exception as e:
        return e
    if determineIpType(host) == 'ipv4':
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # create a socket with IPv4 address family
    else:
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM) # create a socket with IPv6 address family
    sock.settimeout(404)
    try:
        sock.connect((host, port))
        packet = messager_o.request(command[1:])
        sock.send(packet) # send the request
        resp, addr = sock.recvfrom(4000) # receive the response
        try:
            messager_o.checkErrorM(resp)
        except RequestError as e:
            raise e
        r = messager_o.response(resp)
        return r
    except socket.timeout:
        print('Timeout: No response received from the server. Retrying...')
    except Exception as e:
        print('Connection error: ', e)
        raise e
    # close the socket
    sock.close()