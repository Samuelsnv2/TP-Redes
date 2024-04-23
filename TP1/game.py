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
    
    def authreq(self):
        # auth req to the server passing in the GAS
        data = {}
        for s in self.sockets:
            # send a req to every server
            try:
                message = {'auth': self.token, 'type': 'authreq'}
                data = s.send(message)
                self.auth_token = data['auth']
            except KeyboardInterrupt:
                print('Exiting...')
            except GameOver as e:
                print('A error occurs...', e.message)
                self.quit()
                return self.authreq()
        return data
    
    def getCannons(self):
        # cannon placement to all server
        data = {}
        try:
            message = {'auth': self.auth_token, 'type': 'getcannons'}
            data = self.sockets[0].send(message)
            self.cannons = data['cannons']
        except ServerError as e:
            print('A error occurs...', e.message)
        return data
    
    def getTurn(self):
        # advance the state
        for i, s in enumerate(self.sockets):
            try:
                message = {'auth': self.auth_token, 'type': 'getturn', 'turn': self.turn}
                states = s.send(message, 8)
                for state in states:
                    for ship in state['ships']:
                        ship['river'] = i
                    self.rivers[i].ships[state['bridge']-1] += state['ships']
            except GameOver as e:
                return False
        return states

    def getTargets(self):
        # potential targets for each cannon
        poss_targets = {}
        for cannon in self.cannons:
            x, y = cannon
            positions = set()
            if y==0:
                positions.add((x, 1)) # river 1
            elif y==4:
                positions.add((x, 4)) # river 4
            else:
                positions.add((x, y-1)) # river above
                positions.add((x, y+1)) # river below
            for p_x, p_y in positions:
                river = self.rivers[p_y-1]
                ships = river.ships[p_x-1]
                if ships:
                    if x not in poss_targets:
                        poss_targets[x] = {}
                    if y not in poss_targets[x]:
                        poss_targets[x][y] = []
                    poss_targets[x][y] += ships
        return poss_targets

    def getWeakBoat(self, boats):
        # get the weakest boat
        life = {
            'frigate': 1,
            'destroyer': 2,
            'battleship': 3
            }
        weakest = boats[0]
        weakest['life'] = life[weakest['hull']] - weakest['hits']
        for boat in boats:
            boat['life'] = life[boat['hull']] - boat['hits']
            if boat['hits'] > weakest['hits']:
                weakest = boat
        return weakest
    
    def shotStrategy(self):
        # get the best shot strategy
        self.shot_list = []
        poss_targets = self.getTargets()
        for x, y_dict in poss_targets:
            for y, boats in y_dict.items():
                self.shot_list.append((x, y, self.getWeakBoat(boats)))
        return self.shot_list

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