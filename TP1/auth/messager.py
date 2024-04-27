import socket
import struct

ERROR_MSGS = {
    1: "INVALID_MSG_CODE - sent when the client sent a request with an unknown type",
    2: "INVALID_MSG_LENGTH - sent when the client sent a request whose size is incompatible with the request type",
    3: "INVALID_PARAMETER - sent when the server detects an error in any field of a request",
    4: "INVALID_SINGLE_TOKEN - sent when one SAS in a GAS is invalid itself",
    5: "ASCII_DECODE_ERROR - sent when a message contains a non-ASCII character"
}

class RequestError(Exception):
    def __init__(self, code):
        self.message = ERROR_MSGS[code]
        super().__init__(self.message)

class messager:
    def __init__(self, type):
        self.type = type
        ''' methods to generate the token
        Description:
            itr: send an individual token request to the server.
            itv: send an individual token validantion message to the server.
            gtr: send a goup token request to the server.
            gtv: send a group token validation message to the server. 
        '''
        methods = {
            "itr": (self.itr_request, self.itr_response),
            "itv": (self.itv_request, self.itv_response),
            "gtr": (self.gtr_request, self.gtr_response),
            "gtv": (self.gtv_request, self.gtv_response)
        }
        try:
            self.request, self.response = methods[type]
        except KeyError:
            raise ValueError("Invalid program type")
    
    def checkErrorM(self, response):
        if len(response) != 4:
            return response
        error_MSG_format = '>HH'
        error_code, error_length = struct.unpack(error_MSG_format, response)
        raise RequestError(error_code)
    
    def parseSAS(self, sas):
        # match the SAS format
        try:
            id, nonce, token = sas.split(':')
            return id, int(nonce), token
        except:
            raise ValueError("SAS format is invalid. Correct is id:nonce:token")
    
    def itr_request(self, params):
        # individual token request - Request
        type = 1
        id, nonce = params
        nonce = int(nonce)
        packet_format = '>H 12s I'
        packet = struct.pack(packet_format, type, bytes(id, encoding="ascii"), nonce)
        self.packet_format = packet_format
        return packet
    
    def itr_response(self, response):
        # individual token request - Response
        packet_format = '>2s 12s I 64s'
        vals = struct.unpack(packet_format, response)
        id, nonce, token = vals[1], vals[2], vals[3]
        response = f'{id.decode("ascii")}:{nonce}:{token.decode("ascii")}'
        return response
    
    def itv_request(self, params):
        # individual token validation - Request
        type = 3
        id, nonce, token = self.parseSAS(params[0])
        packet_format = '>H 12s I 64s'
        packet = struct.pack(packet_format, type, bytes(id, encoding="ascii"), nonce, bytes(token, encoding="ascii"))
        self.packet_format = packet_format
        return packet
    
    def itv_response(self, response):
        # individual token validation - Response
        packet_format = '>2s 12s I 64s 1s'
        vals = struct.unpack(packet_format, response)
        status = int(vals[-1].decode() == b'\x01')
        return status
    
    def gtr_request(self, params):
        # group token request - Request
        type = 5
        N = int(params[0])
        sass = [self.parseSAS(sas) for sas in params[1:]]
        packet_format_sas = '>12s I 64s'
        sas_packets = [struct.pack(packet_format_sas, bytes(id, encoding="ascii"), nonce, bytes(token, encoding="ascii")) for id, nonce, token in sass]
        sas_packets = b''.join(sas_packets)
        packet_format = '>2s 2s'
        packet = struct.pack(packet_format, type.to_bytes(2,'big'), N.to_bytes(2,'big')) + sas_packets
        self.packet_format = (packet_format_sas * N).replace('>', '')
        self.packet_format = '>H H' + self.packet_format
        return packet
    
    def gtr_response(self, response):
        # group token request - Response
        packet_format = self.packet_format + '64s'
        vals = struct.unpack(packet_format, response)
        bl = [vals[i:i+3] for i in range(2, len(vals)-2, 3)]
        sas = '+'.join([f'{id.decode("ascii")}:{nonce}:{token.decode("ascii")}' for id, nonce, token in bl])
        token = vals[-1].decode("ascii")
        return sas + '+' + token
    
    def gtv_request(self, params):
        # group token validation - Request
        type = 7
        N = int(params[0])
        params = params[1].split('+')
        sass = [self.parseSAS(sas) for sas in params[:-1]]
        tokenG = params[-1]
        packet_format_sas = '>12s I 64s'
        sas_packets = [struct.pack(packet_format_sas, bytes(id, encoding="ascii"), nonce, bytes(token, encoding="ascii")) for id, nonce, token in sass]
        sas_packets = b''.join(sas_packets)
        packet_format = '>2s 2s'
        packet = struct.pack(packet_format, type.to_bytes(2,'big'), N.to_bytes(2,'big')) + sas_packets + struct.pack('>64s', bytes(tokenG, encoding="ascii"))
        self.packet_format = (packet_format_sas * N).replace('>', '')
        self.packet_format = '>2s 2s' + self.packet_format + '64s'
        return packet
    
    def gtv_response(self, response):
        # group token validation - Response
        packet_format = self.packet_format + '1s'
        vals = struct.unpack(packet_format, response)
        status = int(vals[-1].decode() == b'\x01')
        return status
    
def determineIpType(hostname):
    ip_address = socket.getaddrinfo(hostname, None)[0][4][0]
    try:
        socket.inet_pton(socket.AF_INET, ip_address)
        return socket.AF_INET
    except socket.error:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, ip_address)
        return socket.AF_INET6
    except socket.error:
        pass
    # return None if the ip address is invalid
    return None

def getAddressFamilyStr(address_family):
    if address_family == socket.AF_INET:
        return "IPv4"
    elif address_family == socket.AF_INET6:
        return "IPv6"
    return "Unknown"