import re
import socket
import struct

ERROR_MSGS = {
    1: "INVALID_MSG_TYPE - The message type is invalid",
    2: "INVALID_MSG_LEN - The message length is invalid",
    3: "INVALID_PARAM - Error in any part of a request",
    4: "INVALID_SINGLE_TOKEN - One SAS of GAS is invalid",
    5: "ASCII_DECODE_ERROR - Error decoding ASCII"
}

class RequestError(Exception):
    def __init__(self, code):
        self.message = ERROR_MSGS[code]
        super().__init__(self.message)

class messager:
    def __init__(self, type):
        self.type = type
        methods = {
        }