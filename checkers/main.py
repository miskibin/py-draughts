import numpy as np
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from checkers.american import Board

templates = Jinja2Templates(directory="checkers/templates/")

app = FastAPI()
# STARTING_POSITION = np.array([0] * 8 + [10] * 8 + [-10] * 8 + [0] * 8, dtype=np.int8)

# board = Board(STARTING_POSITION)
board = Board()
app.mount("/static", StaticFiles(directory="checkers/static"), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "board": board.friendly_form.reshape(8, 8).tolist()},
    )


@app.get("/random_move")
def random_move(request: Request):
    moves = list(board.legal_moves)
    # get move wiht longest capture chain
    if not moves:
        print("No legal moves")
        return {"position": board.friendly_form.reshape(8, 8).tolist()}
    if np.random.random() < 0.7:
        move = max(moves, key=lambda x: len(x.captured_list))
    else:
        move = np.random.choice(moves)
    print(move)
    board.push(move)
    print(board)
    return {"position": board.friendly_form.reshape(8, 8).tolist()}


@app.get("/board")
def get_board(request: Request):
    return {"position": board.friendly_form.reshape(8, 8).tolist()}


if __name__ == "__main__":
    uvicorn.run(app)
