from checkers.server import Server

Server().run()

# board = checkers.Board()

# board.push_from_str("24-19")
# board.push_from_str("12-16")
# board.push_from_str("23-18")
# board.push_from_str("16-23")
# board.push_from_str("26-19")
# print(board)
# >>> ---------------------------------
# >>> |   | x |   | x |   | x |   | x |
# >>> ---------------------------------
# >>> | x |   | x |   | x |   | x |   |
# >>> ---------------------------------
# >>> |   | x |   | x |   | x |   |   |
# >>> ---------------------------------
# >>> |   |   |   |   |   |   |   |   |
# >>> ---------------------------------
# >>> |   |   |   | o |   | o |   |   |
# >>> ---------------------------------
# >>> | o |   | o |   |   |   |   |   |
# >>> ---------------------------------
# >>> |   | o |   |   |   | o |   | o |
# >>> ---------------------------------
# >>> | o |   | o |   | o |   | o |   |
# board.pop()
# print(board)
# >>> ---------------------------------
# >>> |   | x |   | x |   | x |   | x |
# >>> ---------------------------------
# >>> | x |   | x |   | x |   | x |   |
# >>> ---------------------------------
# >>> |   | x |   | x |   | x |   |   |
# >>> ---------------------------------
# >>> |   |   |   |   |   |   |   |   |
# >>> ---------------------------------
# >>> |   |   |   | o |   |   |   |   |
# >>> ---------------------------------
# >>> | o |   | o |   | x |   |   |   |
# >>> ---------------------------------
# >>> |   | o |   | o |   | o |   | o |
# >>> ---------------------------------
# >>> | o |   | o |   | o |   | o |   |
# print(list(board.legal_moves))
# >>> [Move through squares: [8, 12], Move through squares: [9, 13],
# >>>  Move through squares: [9, 14], Move through squares: [10, 14],
# >>>  Move through squares: [10, 15], Move through squares: [11, 15],
# >>>  Move through squares: [11, 16]]
# import checkers.base as checkers
# import numpy as np
# CUSTOM_POSITION = np.array([1] * 20 + [-1] * 12, dtype=np.int8)
# board = checkers.BaseBoard(starting_position=CUSTOM_POSITION)
# board.legal_moves = ... # create your own custom legal_moves method (property)
# print(board)
# print(board.legal_moves)
