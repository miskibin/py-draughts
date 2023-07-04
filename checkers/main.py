import numpy as np
from fastapi import FastAPI, Request
import uvicorn
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from checkers.base_board import Board

templates = Jinja2Templates(directory="fast_checkers/templates/")

app = FastAPI()
board = Board()
app.mount("/static", StaticFiles(directory="fast_checkers/static"), name="static")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "board": board.friendly_form.tolist()}
    )


@app.get("/random_move")
def random_move(request: Request):
    moves = list(board.legal_moves)
    move = moves[np.random.randint(0, len(moves))]
    board.move(move)
    print(board)
    return {"position": board.friendly_form.tolist()}


@app.get("/board")
def get_board(request: Request):
    return {"position": board.friendly_form.tolist()}


if __name__ == "__main__":
    uvicorn.run(app)
