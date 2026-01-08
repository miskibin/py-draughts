"""
py-draughts Game Server

A FastAPI-based web server for playing draughts games with optional engine support.
Supports human vs engine, or engine vs engine play modes.
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, Optional
import threading

import uvicorn
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from draughts.boards.base import BaseBoard, Color
from draughts.engines import Engine
from draughts.engines import HubEngine


class PositionResponse(BaseModel):
    """Response model for board position state."""
    position: list = Field(description="Current board position")
    history: list = Field(description="History of moves")
    turn: Literal["white", "black"] = Field(description="Current turn")
    game_over: bool = Field(description="Whether the game is over")
    result: str = Field(description="Game result string")


class EngineInfo(BaseModel):
    """Response model for engine information."""
    white_engine: Optional[str] = Field(description="White engine name")
    black_engine: Optional[str] = Field(description="Black engine name")
    depth: int = Field(description="Current engine depth")


class Server:
    """
    Draughts game server with web UI.
    
    Supports:
    - Human play via web interface
    - Single engine for computer moves
    - Two engines playing against each other (engine vs engine mode)
    """
    
    APP = FastAPI(title="py-draughts")
    static_dir = Path(__file__).parent / "static"
    APP.mount("/static", StaticFiles(directory=static_dir), name="static")
    templates_dir = Path(__file__).parent / "templates"
    templates = Jinja2Templates(directory=templates_dir)

    def __init__(
        self,
        board: BaseBoard,
        white_engine: Optional[Engine] = None,
        black_engine: Optional[Engine] = None,
    ):
        """
        Initialize the server.
        
        Args:
            board: The initial board state
            white_engine: Engine to play as white (optional)
            black_engine: Engine to play as black (optional)
        """
        self.board = board
        self.white_engine = white_engine
        self.black_engine = black_engine
        self._lock = threading.RLock()
        self.engine_depth = 6
        
        # Start any HubEngine instances
        for engine in [self.white_engine, self.black_engine]:
            if isinstance(engine, HubEngine) and not engine._started:
                engine.start()
        
        self._setup_routes()

    def _setup_routes(self) -> None:
        """Configure all API routes."""
        self.router = APIRouter()
        
        # Page routes
        self.router.add_api_route("/", self.index)
        self.router.add_api_route("/set_board/{board_type}", self.set_board, methods=["GET"])
        
        # Game state routes
        self.router.add_api_route("/position", self.get_position, methods=["GET"])
        self.router.add_api_route("/legal_moves", self.get_legal_moves, methods=["GET"])
        self.router.add_api_route("/fen", self.get_fen, methods=["GET"])
        self.router.add_api_route("/pdn", self.get_pdn, methods=["GET"])
        self.router.add_api_route("/engine_info", self.get_engine_info, methods=["GET"])
        
        # Game action routes
        self.router.add_api_route("/move/{source}/{target}", self.move, methods=["POST"])
        self.router.add_api_route("/best_move", self.get_best_move, methods=["GET"])
        self.router.add_api_route("/pop", self.pop, methods=["GET"])
        self.router.add_api_route("/goto/{ply}", self.goto_ply, methods=["GET"])
        
        # Load/save routes
        self.router.add_api_route("/load_pdn", self.load_pdn, methods=["POST"])
        self.router.add_api_route("/load_fen", self.load_fen, methods=["POST"])
        
        # Settings routes
        self.router.add_api_route("/set_depth/{depth}", self.set_depth, methods=["GET"])
        
        self.APP.include_router(self.router)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def position_json(self) -> PositionResponse:
        """Get current position as JSON response. Caller should hold lock."""
        history = []
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

    @property
    def current_engine(self) -> Optional[Engine]:
        """Get the engine for the current turn."""
        if self.board.turn == Color.WHITE:
            return self.white_engine
        return self.black_engine

    @property
    def has_dual_engines(self) -> bool:
        """Check if both engines are configured (engine vs engine mode)."""
        return self.white_engine is not None and self.black_engine is not None

    # =========================================================================
    # Page Routes
    # =========================================================================

    def index(self, request: Request):
        """Render the main game page."""
        return self.templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "size": len(self.board.STARTING_POSITION) * 2,
                "has_dual_engines": self.has_dual_engines,
                "white_engine_name": self._get_engine_name(self.white_engine),
                "black_engine_name": self._get_engine_name(self.black_engine),
            },
        )

    def set_board(self, request: Request, board_type: Literal["standard", "american", "frisian", "russian"]):
        """Switch to a different board type."""
        with self._lock:
            if board_type == "standard":
                from draughts import StandardBoard
                self.board = StandardBoard()
            elif board_type == "american":
                from draughts import AmericanBoard
                self.board = AmericanBoard()
            elif board_type == "frisian":
                from draughts import FrisianBoard
                self.board = FrisianBoard()
            elif board_type == "russian":
                from draughts import RussianBoard
                self.board = RussianBoard()
            return RedirectResponse(url="/")

    # =========================================================================
    # Game State Routes
    # =========================================================================

    def get_position(self, request: Request) -> PositionResponse:
        """Get the current board position."""
        with self._lock:
            return self.position_json

    def get_legal_moves(self) -> dict:
        """Get all legal moves for the current position."""
        with self._lock:
            moves_dict: dict[int, list[int]] = defaultdict(list)
            for move in list(self.board.legal_moves):
                moves_dict[int(move.square_list[0])].extend(
                    map(int, move.square_list[1:])
                )
            return {"legal_moves": json.dumps(moves_dict)}

    def get_fen(self) -> dict:
        """Get the current FEN string."""
        with self._lock:
            return {"fen": self.board.fen}

    def get_pdn(self) -> dict:
        """Get the current PDN string."""
        with self._lock:
            return {"pdn": self.board.pdn}

    def get_engine_info(self) -> EngineInfo:
        """Get information about configured engines."""
        return EngineInfo(
            white_engine=self._get_engine_name(self.white_engine),
            black_engine=self._get_engine_name(self.black_engine),
            depth=self.engine_depth,
        )

    # =========================================================================
    # Game Action Routes
    # =========================================================================

    def move(self, request: Request, source: str, target: str) -> PositionResponse:
        """Make a move on the board."""
        with self._lock:
            move_str = f"{source}-{target}"
            self.board.push_uci(move_str)
            return self.position_json

    def get_best_move(self, request: Request) -> PositionResponse:
        """Get and play the best move from the current engine."""
        with self._lock:
            if self.board.game_over:
                return self.position_json

            engine = self.current_engine
            if engine is None:
                return self.position_json

            legal_moves = list(self.board.legal_moves)
            if not legal_moves:
                return self.position_json

            result = engine.get_best_move(self.board, with_evaluation=False)
            move = result if not isinstance(result, tuple) else result[0]

            # Validate move is legal (handles stale TT or overlapping requests)
            if move not in legal_moves:
                move = legal_moves[0]

            self.board.push(move)
            return self.position_json

    def pop(self, request: Request) -> PositionResponse:
        """Undo the last move."""
        with self._lock:
            self.board.pop()
            return self.position_json

    def goto_ply(self, request: Request, ply: int) -> PositionResponse:
        """Jump to a specific ply in the game history."""
        with self._lock:
            ply = max(0, int(ply))
            current = len(self.board._moves_stack)
            ply = min(ply, current)
            
            while len(self.board._moves_stack) > ply:
                self.board.pop()
            
            return self.position_json

    # =========================================================================
    # Load/Save Routes
    # =========================================================================

    async def load_pdn(self, request: Request) -> PositionResponse:
        """Load a game from PDN."""
        data = await request.json()
        with self._lock:
            self.board = type(self.board).from_pdn(data["pdn"])
            return self.position_json

    async def load_fen(self, request: Request) -> PositionResponse:
        """Load a position from FEN."""
        data = await request.json()
        with self._lock:
            self.board = type(self.board).from_fen(data["fen"])
            return self.position_json

    # =========================================================================
    # Settings Routes
    # =========================================================================

    def set_depth(self, depth: int) -> dict:
        """Set the engine search depth."""
        depth = max(1, min(10, int(depth)))
        with self._lock:
            self.engine_depth = depth
            
            # Update depth_limit on both engines if they have the attribute
            for engine in [self.white_engine, self.black_engine]:
                if engine is not None and hasattr(engine, 'depth_limit'):
                    engine.depth_limit = depth
            
            return {"depth": self.engine_depth}

    # =========================================================================
    # Helper Methods
    # =========================================================================

    @staticmethod
    def _get_engine_name(engine: Optional[Engine]) -> Optional[str]:
        """Get the display name for an engine."""
        if engine is None:
            return None
        return type(engine).__name__

    def run(self, **kwargs):
        """Start the server."""
        try:
            uvicorn.run(self.APP, **kwargs)
        finally:
            self._cleanup_engines()
    
    def _cleanup_engines(self) -> None:
        """Quit any HubEngine instances."""
        for engine in [self.white_engine, self.black_engine]:
            if isinstance(engine, HubEngine):
                try:
                    engine.quit()
                except Exception:
                    pass


if __name__ == "__main__":
    from loguru import logger
    import sys

    logger.add(sys.stderr, level="DEBUG")
    
    from draughts.engines import AlphaBetaEngine
    from draughts import get_board , HubEngine

    # Example: Two engines playing against each other
    white_engine = AlphaBetaEngine(depth_limit=9)
    black_engine = AlphaBetaEngine(depth_limit=9)
    # black_engine = HubEngine('./scan_engine/scan.exe', depth_limit=6)
    
    board = get_board("standard")
    server = Server(
        board=board,
        white_engine=white_engine,
        black_engine=black_engine,
    )
    server.run()
