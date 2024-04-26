from socket_t import *
import threading
from concurrent.futures import *

class Game:
    # implementation of the game -> send requests to the server and control the board
    def __init__(self, host, port, token=None):
        self.auth_token = None
        self.token = token
        self.host = host
        self.port = port
        
        # start the game logic:
        self.turn = 0
        self.cannons = []
        self.state = []
        self.rivers = [River(i) for i in range(1,5)]

        # sockets implementation for the game
        self.sockets = [Socket(host, port+i) for i in range(4)]
        self.shot_list = []

        self.condition = threading.Condition()
    
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
                running = 'running game'
                if running in e.data["description"]:
                    self.quit()
                    for s in self.sockets:
                        s.close()
                    self.sockets = [Socket(self.host, self.port+i) for i in range(4)]
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
            print('An error occurs', e.message)
        return data
    
    def getTurnServer(self):
        # advance the state
        for i, s in enumerate(self.sockets):
            try:
                message = {'auth': self.auth_token, 'type': 'getturn', 'turn': self.turn}
                self.rivers[i].ships = [[] for i in range(8)]
                states = s.send(message, 8)
                for state in states:
                    for ship in state['ships']:
                        ship['river'] = i
                    self.rivers[i].ships[state['bridge']-1] += state['ships']
            except GameOver as e:
                print(e.data)
                print(s.turn)
                return False
        return True
    
    def getTurn(self):
        # advance the state
        with ThreadPoolExecutor(max_workers=4) as executor:
            p = []
            for i in range(len(self.sockets)):
                p.append(executor.submit(self.getTurnServer))
            turn = True
            for f in as_completed(p):
                turn = turn and f.result()
                if not turn:
                    break
        return turn

    def shot(self):
        self.shot_list = self.shotStrategy()
        threads = []
        for i in range(4):
            c_thread = threading.Thread(target=self.shotServer, args=(i,))
            c_thread.start()
            threads.append(c_thread)
        while self.shot_list:
            with ThreadPoolExecutor(max_workers=5) as executor:
                p = []
                with self.condition:
                    for target in self.shot_list:
                        p.append(executor.submit(self.shotMessage, target))
                for t in p:
                    t.result()
            with self.condition:
                self.condition.modify_all()
        with self.condition:
            self.condition.notify_all()
        for t in threads:
            t.join()
    
    def shotMessage(self, target):
        x, y, id, river = target
        try:
            message = {'auth': self.auth_token, 'type': 'shot', 'x': x, 'y': y, 'id': id}
            self.sockets[river].send(message)
            with self.condition:
                self.condition.notify_all()
        except:
            pass

    def receiveShot(self, river):
        while(self.shot_list):
            with self.condition:
                self.condition.wait()
                if not self.shot_list:
                    break
                r = self.sockets[river].receive()
                if r and r['type'] == 'shot':
                    if r['status'] != 0:
                        raise ServerError(message = 'Shot gone wrong'+str(r))
                    x,y = r['cannon']
                    id = r['id']
                    target = (x, y, id, river)
                    with self.condition:
                        if target in self.shot_list:
                            self.shot_list.remove(target)
                            self.condition.notify_all()            
        while self.sockets[river].listen() != None:
            continue

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
        poss_shot = []
        poss_targets = self.getTargets()
        for x, y_dict in poss_targets:
            for y, boats in y_dict.items():
                poss_shot.append((x, y, 
                                  self.getWeakBoat(boats)['id'], 
                                  self.getWeakBoat(boats)['river']))
        return set(poss_shot)

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