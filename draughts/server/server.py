import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, Callable
import threading

import numpy as np
import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from draughts.boards.base import BaseBoard, Color


class PositionResponse(BaseModel):
    position: list = Field(description="Current board position")
    history: list = Field(description="History of moves")
    turn: Literal["white", "black"] = Field(description="Current turn")
    game_over: bool = Field(description="Whether the game is over")
    result: str = Field(description="Game result string")


class Server:
    APP = FastAPI(title="py-draughts")
    static_dir = Path(__file__).parent / "static"
    APP.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=templates_dir)

    def __init__(
        self,
        board: BaseBoard,
        get_best_move_method: Callable = lambda board: np.random.choice(
            list(board.legal_moves)
        ),
        engine=None,
    ):
        self.get_best_move_method = get_best_move_method
        self.engine = engine
        self.board = board
        self._lock = threading.RLock()
        self.engine_depth = 6
        self.play_with_computer = False
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
        self.router.add_api_route("/goto/{ply}", self.goto_ply, methods=["GET"])
        self.router.add_api_route(
            "/move/{source}/{target}", self.move, methods=["POST"]
        )
        self.router.add_api_route("/pop", self.pop, methods=["GET"])
        self.router.add_api_route("/pdn", self.get_pdn, methods=["GET"])
        self.router.add_api_route("/load_pdn", self.load_pdn, methods=["POST"])
        self.router.add_api_route("/load_fen", self.load_fen, methods=["POST"])
        self.router.add_api_route("/set_depth/{depth}", self.set_depth, methods=["GET"])
        self.router.add_api_route("/set_play_mode/{mode}", self.set_play_mode, methods=["GET"])
        self.APP.include_router(self.router)

    def get_fen(self):
        return {"fen": self.board.fen}

    def get_pdn(self):
        return {"pdn": self.board.pdn}

    async def load_pdn(self, request: Request) -> PositionResponse:
        data = await request.json()
        with self._lock:
            self.board = type(self.board).from_pdn(data["pdn"])
            return self.position_json

    async def load_fen(self, request: Request) -> PositionResponse:
        data = await request.json()
        with self._lock:
            self.board = type(self.board).from_fen(data["fen"])
            return self.position_json

    def set_depth(self, depth: int) -> dict:
        depth = max(1, min(10, int(depth)))
        with self._lock:
            self.engine_depth = depth
            if self.engine is not None and hasattr(self.engine, 'depth'):
                self.engine.depth = depth
            return {"depth": self.engine_depth}

    def set_play_mode(self, mode: str) -> dict:
        with self._lock:
            self.play_with_computer = mode.lower() == "on"
            return {"play_with_computer": self.play_with_computer}

    def set_board(self, request: Request, board_type: Literal["standard", "american"]):
        with self._lock:
            if board_type == "standard":
                from draughts import StandardBoard

                self.board = StandardBoard()
            elif board_type == "american":
                from draughts import AmericanBoard

                self.board = AmericanBoard()

            return RedirectResponse(url="/")

    def get_legal_moves(self):
        with self._lock:
            moves_dict = defaultdict(list)
            for move in list(self.board.legal_moves):
                moves_dict[int(move.square_list[0])].extend(map(int, move.square_list[1:]))
            return {
                "legal_moves": json.dumps(moves_dict),
            }

    @property
    def position_json(self) -> PositionResponse:
        # Note: callers should hold self._lock if they need a consistent snapshot.
        history = []  # (number, white, black)
        stack = self.board._moves_stack
        for idx in range(len(stack)):
            if idx % 2 == 0:
                history.append([(idx // 2) + 1, str(stack[idx])])
            else:
                history[-1].append(str(stack[idx]))
        return PositionResponse(
            position=self.board.friendly_form.tolist(),
            history=history,
            turn="white" if self.board.turn == Color.WHITE else "black",
            game_over=bool(self.board.game_over),
            result=str(getattr(self.board, "result", "-")),
        )

    def get_position(self, request: Request) -> PositionResponse:
        with self._lock:
            return self.position_json

    def set_random_position(self, request: Request) -> PositionResponse:
        with self._lock:
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
        # IMPORTANT: /best_move can be called concurrently (autoplay + long searches).
        # Serialize access to the shared board and reject stale/illegal moves.
        with self._lock:
            if self.board.game_over:
                return self.position_json

            move = self.get_best_move_method(self.board)

            legal_moves = list(self.board.legal_moves)
            if not legal_moves:
                return self.position_json

            if move not in legal_moves:
                # Stale/illegal engine result (e.g., TT corruption or overlapping requests).
                # Fall back to a legal move so the UI always progresses.
                move = legal_moves[0]

            self.board.push(move)
            return self.position_json

    def goto_ply(self, request: Request, ply: int) -> PositionResponse:
        """Jump to a historical position by ply count.

        ply=0 is the starting position (no moves applied).
        ply=N is the position after N half-moves have been applied.

        If ply is less than current history length, this will pop moves until
        the requested ply is reached.
        """
        with self._lock:
            ply = int(ply)
            if ply < 0:
                ply = 0
            current = len(self.board._moves_stack)
            if ply > current:
                ply = current
            while len(self.board._moves_stack) > ply:
                self.board.pop()
            return self.position_json

    def move(self, request: Request, source: str, target: str) -> PositionResponse:
        with self._lock:
            move_str = f"{source}-{target}"
            self.board.push_uci(move_str)
            return self.position_json

    def pop(self, request: Request) -> PositionResponse:
        with self._lock:
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
    from loguru import logger
    import sys

    logger.add(sys.stderr, level="DEBUG")
    
    from draughts.engine import AlphaBetaEngine
    from draughts import get_board

    engine = AlphaBetaEngine(depth=6)
    board = get_board("standard")
    server = Server(board=board, get_best_move_method=engine.get_best_move, engine=engine)
    server.run()
