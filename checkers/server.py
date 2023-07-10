import numpy as np
import uvicorn
from fastapi import FastAPI, Request, APIRouter
import json
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pprint import pprint
from checkers import __version__
from checkers.american import Board


class Server:
    def __init__(
        self,
        board=Board(),
        draw_board=True,
        populate_board=True,
        show_pseudo_legal_moves=True,
    ):
        self.app = FastAPI(title="fast-checkers", version=__version__)
        self.app.mount(
            "/static", StaticFiles(directory="checkers/static"), name="static"
        )
        self.templates = Jinja2Templates(directory="checkers/templates/")
        self.board = board
        self.router = APIRouter()
        self.router.add_api_route("/", self.index)
        self.app.include_router(self.router)
        self.draw_board = draw_board
        self.populate_board = populate_board
        self.show_pseudo_legal_moves = show_pseudo_legal_moves

    def index(self, request: Request):
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "board": json.dumps(board.friendly_form.tolist()),
                "pseudo_legal_king_moves": json.dumps(board.PSEUDO_LEGAL_KING_MOVES),
                "pseudo_legal_man_moves": json.dumps(board.PSEUDO_LEGAL_MAN_MOVES),
                "draw_board": json.dumps(self.draw_board),
                "populate_board": json.dumps(self.populate_board),
                "show_pseudo_legal_moves": json.dumps(self.show_pseudo_legal_moves),
                "size": self.board.shape[0] ** 2,
            },
        )

    def run(self, **kwargs):
        uvicorn.run(self.app, **kwargs)


# STARTING_POSITION = np.array([10] * 15 + [0] * 20 + [-10] * 15, dtype=np.int8)
# # random starting position from 10, 0, -10,1,-1
STARTING_POSITION = np.random.choice(
    [10, 0, -10, 1, -1],
    size=len(Board.STARTING_POSITION),
    replace=True,
    p=[0.1, 0.4, 0.1, 0.2, 0.2],
)
board = Board(STARTING_POSITION)
# board = Board()


# @app.get("/")
# def index(request: Request):
#     pprint(board.PSEUDO_LEGAL_KING_MOVES)
#     return templates.TemplateResponse(
#         "index.html",
#         {
#             "request": request,
#             "board": board.friendly_form.reshape(10, 10).tolist(),
#             "debug": json.dumps(board.PSEUDO_LEGAL_KING_MOVES),
#         },
#     )


# @app.get("/random_move")
# def random_move(request: Request):
#     moves = list(board.legal_moves)
#     # get move wiht longest capture chain
#     if not moves:
#         print("No legal moves")
#         return {"position": board.friendly_form.reshape(10, 10).tolist()}
#     if np.random.random() < 0.7:
#         move = max(moves, key=lambda x: len(x.captured_list))
#     else:
#         move = np.random.choice(moves)

#     pprint(list(board.legal_moves))
#     print(move)
#     board.push(move)
#     return {"position": board.friendly_form.reshape(10, 10).tolist()}


# @app.get("/board")
# def get_board(request: Request):
#     return {"position": board.friendly_form.reshape(10, 10).tolist()}


if __name__ == "__main__":
    Server().run()
