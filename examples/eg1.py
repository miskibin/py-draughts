import checkers
from checkers import AmericanBoard, Move 
board = AmericanBoard()
move = Move([checkers.A3, checkers.B4])
board.push(move)
print(board)