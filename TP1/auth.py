from auth.client import *
from game import *

#host = 'pugna.snes.dcc.ufmg.br'
host = 'pugna.snes.dcc.ufmg.br'
port = 51111

command1 = ['itr', '2021078455', 20]
token1 = auth(host, port, command1)

command2 = ['itr', '2022061084', 20]
token2 = auth(host, port, command2)

command3 = ['gtr', '2', token1, token2]
token = auth(host, port, command3)

game = Game(host, port, token=token)
game.authreq()
game.getCannons()

while game.getTurn():
    game.shot()
    game.turn += 1

game.quit()