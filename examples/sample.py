from draughts import StandardBoard
from draughts.svg import board, Arrow

b = StandardBoard.from_fen("W:W25,38,39,46,47,49:B14,24,26,31,42,28")
# arrow from 39 to 33
a = Arrow(38, 32)
svg_code = board(b, arrows=[a])
with open("board.svg", "w") as f:
    f.write(svg_code)
    