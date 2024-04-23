from socket_t import *

class Game:
    # implementation of the game -> send requests to the server and control the board
    def __init__(self, host, port, token=None):
        self.auth_token = None
        self.token = token
        
        # start the game logic:
        self.turn = 0
        self.cannons = []
        self.state = []
        self.rivers = [River(i) for i in range(1,5)]

        # sockets implementation for the game
        self.sockets = [Socket(host, port+i) for i in range(4)]
        self.shot_list = []
    

    def quit(self):
        # send quit message to all sockets
        try:
            message = {'auth': self.auth_token, 'type': 'quit'}
            for s in self.sockets:
                s.send(message)
        except KeyboardInterrupt:
            print('Exiting...')
        except GameOver as e:
            pass
    def __del__(self):
        # close all sockets
        return self.quit()
    
class River:
    def __init__(self, river_id):
        self.river_id = river_id
        self.ships = [[] for i in range(8)]