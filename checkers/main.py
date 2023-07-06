import numpy as np
from fastapi import FastAPI, Request
import uvicorn
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from checkers.american import Board as Board

templates = Jinja2Templates(directory="checkers/templates/")

app = FastAPI()
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
    move = max(moves, key=lambda x: len(x.captured_list))
    print(move)
    board.push(move)
    return {"position": board.friendly_form.reshape(8, 8).tolist()}


@app.get("/board")
def get_board(request: Request):
    return {"position": board.friendly_form.reshape(8, 8).tolist()}


if __name__ == "__main__":
    uvicorn.run(app)
