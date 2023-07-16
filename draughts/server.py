import json
from collections import defaultdict
from pathlib import Path
from typing import Literal

import numpy as np
import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from draughts import __version__
from draughts.base import BaseBoard, Color
from draughts.standard import Board


class PositionResponse(BaseModel):
    position: list = Field(description="Current board position")
    history: list = Field(description="History of moves")
    turn: Literal["white", "black"] = Field(description="Current turn")


class Server:
    APP = FastAPI(title="py-draughts", version=__version__)
    static_dir = Path(__file__).parent / "static"
    APP.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=templates_dir)

    def __init__(
        self,
        board: BaseBoard = Board(),
        get_best_move_method: callable = None,
    ):
        self.get_best_move_method = get_best_move_method
        self.board = board
        self.router = APIRouter()
        self.router.add_api_route("/", self.index)
        self.router.add_api_route(
            "/set_board/{board_type}", self.set_board, methods=["GET"]
        )
        self.router.add_api_route("/legal_moves", self.get_legal_moves, methods=["GET"])
        self.router.add_api_route("/fen", self.get_fen, methods=["GET"])
        self.router.add_api_route(
            "/set_random_position", self.set_random_position, methods=["GET"]
        )
        self.router.add_api_route("/best_move", self.get_best_move, methods=["GET"])
        self.router.add_api_route("/position", self.get_position, methods=["GET"])
        self.router.add_api_route(
            "/move/{source}/{target}", self.move, methods=["POST"]
        )
        self.router.add_api_route("/pop", self.pop, methods=["GET"])
        self.APP.include_router(self.router)
        if not get_best_move_method:
            self.get_best_move_method = lambda board: np.random.choice(
                list(board.legal_moves)
            )

    def get_fen(self):
        return {"fen": self.board.fen}

    def set_board(self, request: Request, board_type: Literal["standard", "american"]):
        if board_type == "standard":
            from draughts.standard import Board

            self.board = Board()
        elif board_type == "american":
            from draughts.american import Board

            self.board = Board()

        return RedirectResponse(url="/")

    def get_legal_moves(self):
        moves_dict = defaultdict(list)
        for move in list(self.board.legal_moves):
            moves_dict[int(move.square_list[0])].extend(map(int, move.square_list[1:]))
        return {
            "legal_moves": json.dumps(moves_dict),
        }

    @property
    def position_json(self) -> PositionResponse:
        history = []  # (numver, white, black)
        stack = self.board._moves_stack
        for idx in range(len(stack)):
            src, tg = stack[idx].square_list[0] + 1, stack[idx].square_list[-1]
            if idx % 2 == 0:
                history.append([(idx // 2) + 1, f"{src}-{tg}"])
            else:
                history[-1].append(f"{src}-{tg}")
        turn = "white" if self.board.turn == Color.WHITE else "black"
        return PositionResponse(
            position=self.board.friendly_form.tolist(),
            history=history,
            turn=turn,
        )

    def get_position(self, request: Request) -> PositionResponse:
        return self.position_json

    def set_random_position(self, request: Request) -> PositionResponse:
        STARTING_POSITION = np.random.choice(
            [2, 0, -2, 1, -1],
            size=len(self.board.STARTING_POSITION),
            replace=True,
            p=[0.1, 0.6, 0.1, 0.1, 0.1],
        )
        self.board._moves_stack = []
        self.board._pos = STARTING_POSITION
        return self.position_json

    def get_best_move(self, request: Request) -> PositionResponse:
        move = self.get_best_move_method(self.board)
        self.board.push(move)
        return self.position_json

    def move(self, request: Request, source: str, target: str) -> PositionResponse:
        move_str = f"{source}-{target}"
        self.board.push_from_str(move_str)
        return self.position_json

    def pop(self, request: Request) -> PositionResponse:
        self.board.pop()
        return self.position_json

    def index(self, request: Request):
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "size": len(self.board.STARTING_POSITION) * 2,
            },
        )

    def run(self, **kwargs):
        uvicorn.run(self.APP, **kwargs)


if __name__ == "__main__":
    from draughts.standard import Board

    server = Server(
        get_best_move_method=lambda board: np.random.choice(list(board.legal_moves)),
    )
    server.run()
