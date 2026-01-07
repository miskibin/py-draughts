"""
Hub protocol implementation for external draughts engines (e.g., Scan).

The Hub protocol is a text-based protocol similar to UCI (from chess),
used by engines like Scan 3.1. See protocol.txt for full specification.

Example usage:
    >>> from draughts import StandardBoard
    >>> from draughts.hub import HubEngine
    >>> 
    >>> engine = HubEngine("path/to/scan.exe")
    >>> engine.start()
    >>> 
    >>> board = StandardBoard()
    >>> move = engine.get_best_move(board)
    >>> board.push(move)
    >>> 
    >>> engine.quit()

Or using context manager:
    >>> with HubEngine("path/to/scan.exe") as engine:
    ...     move = engine.get_best_move(board)
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Generator, Iterable

from loguru import logger

from draughts.boards.base import BaseBoard
from draughts.engines.engine import Engine
from draughts.models import Color, Figure
from draughts.move import Move


# Hub protocol variant names mapping from py-draughts board classes
VARIANT_MAP = {
    "Standard (international) checkers": "normal",
    "Frisian draughts": "frisian",
    # American checkers is 8x8, not supported by Scan (which is 10x10 only)
}


@dataclass
class EngineInfo:
    """Engine identification info from Hub protocol."""
    name: str = ""
    version: str = ""
    author: str = ""
    country: str = ""


@dataclass
class EngineParam:
    """Engine parameter declaration from Hub protocol."""
    name: str
    value: str
    param_type: str  # "bool", "int", "real", "string", "enum"
    min_val: Optional[str] = None
    max_val: Optional[str] = None
    values: Optional[list[str]] = None  # For enum type


@dataclass
class SearchInfo:
    """Search information from 'info' lines during search."""
    depth: Optional[int] = None
    mean_depth: Optional[float] = None
    score: Optional[float] = None
    nodes: Optional[int] = None
    time: Optional[float] = None
    nps: Optional[float] = None
    pv: Optional[str] = None


@dataclass
class SearchResult:
    """Result from engine search ('done' line)."""
    move: str
    ponder: Optional[str] = None
    info: SearchInfo = field(default_factory=SearchInfo)


def board_to_hub_position(board: BaseBoard) -> str:
    """
    Convert a py-draughts board to Hub protocol position string.
    
    Hub format: 51 characters total
    - 1 char for side to move: 'W' or 'B'
    - 50 chars for squares in standard order: 'w', 'b', 'W', 'B', 'e'
    
    Args:
        board: The board to convert (must be 10x10 = 50 squares)
    
    Returns:
        Hub position string like "Wbbbbbbbbbbbbbbbbbbbbeeeeeeeeeewwwwwwwwwwwwwwwwwwww"
    
    Raises:
        ValueError: If board is not 50 squares (10x10)
    """
    if len(board.position) != 50:
        raise ValueError(
            f"Hub protocol only supports 10x10 boards (50 squares), "
            f"got {len(board.position)} squares"
        )
    
    # Side to move
    side = "W" if board.turn == Color.WHITE else "B"
    
    # Square mapping: py-draughts Figure values -> Hub chars
    # py-draughts: -1=white man, -2=white king, 1=black man, 2=black king, 0=empty
    piece_map = {
        Figure.WHITE_MAN.value: "w",   # -1
        Figure.WHITE_KING.value: "W",  # -2
        Figure.BLACK_MAN.value: "b",   # 1
        Figure.BLACK_KING.value: "B",  # 2
        Figure.EMPTY.value: "e",       # 0
    }
    
    squares = "".join(piece_map[int(sq)] for sq in board.position)
    
    return side + squares


def hub_position_to_board(
    position: str, board_class: type[BaseBoard]
) -> BaseBoard:
    """
    Parse a Hub protocol position string into a py-draughts board.
    
    Args:
        position: Hub position string (51 chars)
        board_class: The Board class to instantiate
    
    Returns:
        Board instance with the parsed position
    
    Raises:
        ValueError: If position string is invalid
    """
    import numpy as np
    
    if len(position) != 51:
        raise ValueError(f"Hub position must be 51 chars, got {len(position)}")
    
    side_char = position[0].upper()
    if side_char not in ("W", "B"):
        raise ValueError(f"Invalid side to move: {side_char}")
    
    turn = Color.WHITE if side_char == "W" else Color.BLACK
    
    # Parse squares
    piece_map = {
        "w": Figure.WHITE_MAN.value,
        "W": Figure.WHITE_KING.value,
        "b": Figure.BLACK_MAN.value,
        "B": Figure.BLACK_KING.value,
        "e": Figure.EMPTY.value,
    }
    
    squares = position[1:]
    pos_array = np.array([piece_map[c] for c in squares], dtype=np.int8)
    
    return board_class(starting_position=pos_array, turn=turn)


def move_to_hub_notation(move: Move) -> str:
    """
    Convert a py-draughts Move to Hub protocol notation.
    
    Hub format:
    - Quiet moves: "32-28"
    - Captures: "28x19x23" (from x to x captured x captured...)
    
    Note: Hub uses 1-indexed squares.
    
    Args:
        move: The Move object to convert
    
    Returns:
        Hub move string
    """
    if not move.captured_list:
        # Simple move: from-to
        return f"{move.square_list[0] + 1}-{move.square_list[-1] + 1}"
    else:
        # Capture: from x to x captured1 x captured2 ...
        # Format: start x end x cap1 x cap2 ...
        parts = [str(move.square_list[0] + 1), str(move.square_list[-1] + 1)]
        parts.extend(str(sq + 1) for sq in move.captured_list)
        return "x".join(parts)


def parse_hub_move(
    move_str: str,
    legal_moves: Iterable[Move],
    board: Optional[BaseBoard] = None,
) -> Move:
    """
    Parse a Hub protocol move string and match against legal moves.
    
    Args:
        move_str: Hub move string like "32-28" or "28x19x23"
        legal_moves: Generator of legal moves to match against
        board: Optional board for diagnostic info on error
    
    Returns:
        Matching Move object from legal_moves
    
    Raises:
        ValueError: If move doesn't match any legal move
    """
    # Parse the move string
    if "-" in move_str:
        parts = move_str.split("-")
        is_capture = False
    elif "x" in move_str:
        parts = move_str.split("x")
        is_capture = True
    else:
        raise ValueError(f"Invalid Hub move format: {move_str}")
    
    # Convert to 0-indexed
    squares = [int(p) - 1 for p in parts]
    start_sq = squares[0]
    end_sq = squares[1]  # Second element is always destination in Hub format
    captured_squares = set(squares[2:]) if is_capture and len(squares) > 2 else None
    
    # Collect legal moves for potential error reporting
    legal_moves_list = list(legal_moves)
    
    # Find matching legal move
    for legal_move in legal_moves_list:
        if legal_move.square_list[0] != start_sq:
            continue
        if legal_move.square_list[-1] != end_sq:
            continue
        
        # For captures, also verify captured squares match
        if is_capture:
            if not legal_move.captured_list:
                continue
            if captured_squares and set(legal_move.captured_list) != captured_squares:
                continue
        
        return legal_move
    
    # Build detailed error message
    legal_moves_str = ", ".join(str(m) for m in legal_moves_list[:20])
    if len(legal_moves_list) > 20:
        legal_moves_str += f"... ({len(legal_moves_list)} total)"
    
    error_msg = f"No legal move matches Hub move: {move_str}\n"
    error_msg += f"  Parsed as: start={start_sq + 1}, end={end_sq + 1}"
    if captured_squares:
        error_msg += f", captures={[s + 1 for s in captured_squares]}"
    error_msg += f"\n  Legal moves: [{legal_moves_str}]"
    
    if board is not None:
        error_msg += f"\n  Position FEN: {board.fen}"
        error_msg += f"\n  Hub position: {board_to_hub_position(board)}"
        error_msg += f"\n  Turn: {'White' if board.turn == Color.WHITE else 'Black'}"
    
    raise ValueError(error_msg)


def parse_hub_line(line: str) -> tuple[str, dict[str, str]]:
    """
    Parse a Hub protocol line into command and arguments.
    
    Hub syntax: <command> <arg>=<val> <arg>=<val> ...
    Values can be quoted with double quotes.
    
    Args:
        line: Raw line from engine
    
    Returns:
        Tuple of (command, {arg: value, ...})
    """
    line = line.strip()
    if not line:
        return "", {}
    
    # Split into tokens, respecting quoted values
    tokens = []
    current = ""
    in_quotes = False
    
    for char in line:
        if char == '"':
            in_quotes = not in_quotes
        elif char == " " and not in_quotes:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += char
    
    if current:
        tokens.append(current)
    
    if not tokens:
        return "", {}
    
    command = tokens[0]
    args = {}
    
    for token in tokens[1:]:
        if "=" in token:
            key, _, value = token.partition("=")
            args[key] = value
        else:
            # Flag argument (no value)
            args[token] = ""
    
    return command, args


class HubEngine(Engine):
    """
    Engine wrapper for Hub protocol (used by Scan and similar engines).
    
    This class manages subprocess communication with an external draughts
    engine using the Hub protocol (version 2).
    
    Attributes:
        path: Path to the engine executable
        time_limit: Default time per move in seconds
        depth_limit: Maximum search depth (None for no limit)
        
    Example:
        >>> engine = HubEngine("scan.exe", time_limit=1.0)
        >>> engine.start()
        >>> move = engine.get_best_move(board)
        >>> engine.quit()
        
        # Or with context manager:
        >>> with HubEngine("scan.exe") as engine:
        ...     move = engine.get_best_move(board)
    """
    
    def __init__(
        self,
        path: str | Path,
        time_limit: float = 1.0,
        depth_limit: Optional[int] = None,
        init_timeout: float = 10.0,
    ):
        """
        Initialize Hub engine wrapper.
        
        Args:
            path: Path to the engine executable
            time_limit: Time limit per move in seconds (default 1.0)
            depth_limit: Maximum search depth (None for no limit)
            init_timeout: Timeout for engine initialization in seconds
        """
        self.path = Path(path)
        self.time_limit = time_limit
        self.depth_limit = depth_limit
        self.init_timeout = init_timeout
        
        self.process: Optional[subprocess.Popen] = None
        self.info: EngineInfo = EngineInfo()
        self.params: dict[str, EngineParam] = {}
        self._variant: Optional[str] = None
        self._started = False
    
    def __enter__(self) -> "HubEngine":
        """Context manager entry - starts the engine."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - quits the engine."""
        self.quit()
    
    def start(self) -> None:
        """
        Start the engine subprocess and complete initialization handshake.
        
        The Hub protocol initialization:
        1. GUI sends "hub"
        2. Engine responds with id, param declarations, then "wait"
        3. GUI optionally sends set-param commands
        4. GUI sends "init"
        5. Engine responds with "ready"
        
        Raises:
            FileNotFoundError: If engine executable not found
            TimeoutError: If engine doesn't respond in time
            RuntimeError: If initialization fails
        """
        if self._started:
            logger.warning("Engine already started")
            return
        
        if not self.path.exists():
            raise FileNotFoundError(f"Engine not found: {self.path}")
        
        logger.info(f"Starting Hub engine: {self.path}")
        
        # Run from the engine's directory so it can find its data files
        engine_dir = self.path.parent.resolve()
        
        self.process = subprocess.Popen(
            [str(self.path.resolve()), "hub"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            cwd=str(engine_dir),  # Run from engine's directory
        )
        
        # Send hub command to start initialization
        self._send("hub")
        
        # Read engine responses until "wait"
        start_time = time.time()
        while True:
            if time.time() - start_time > self.init_timeout:
                self.quit()
                raise TimeoutError("Engine initialization timed out")
            
            line = self._read_line(timeout=1.0)
            if line is None:
                continue
            
            cmd, args = parse_hub_line(line)
            
            if cmd == "id":
                self.info.name = args.get("name", "")
                self.info.version = args.get("version", "")
                self.info.author = args.get("author", "")
                self.info.country = args.get("country", "")
                logger.info(f"Engine: {self.info.name} {self.info.version}")
            
            elif cmd == "param":
                param = EngineParam(
                    name=args.get("name", ""),
                    value=args.get("value", ""),
                    param_type=args.get("type", "string"),
                    min_val=args.get("min"),
                    max_val=args.get("max"),
                )
                if "values" in args:
                    param.values = args["values"].split()
                self.params[param.name] = param
                logger.debug(f"Engine param: {param.name}={param.value}")
            
            elif cmd == "wait":
                break
        
        # Send init command
        self._send("init")
        
        # Wait for ready
        while True:
            if time.time() - start_time > self.init_timeout:
                self.quit()
                raise TimeoutError("Engine initialization timed out waiting for ready")
            
            line = self._read_line(timeout=1.0)
            if line is None:
                continue
            
            cmd, _ = parse_hub_line(line)
            if cmd == "ready":
                break
        
        self._started = True
        logger.info("Engine ready")
    
    def quit(self) -> None:
        """Send quit command and terminate the engine subprocess."""
        if self.process is None:
            return
        
        try:
            self._send("quit")
            self.process.wait(timeout=2.0)
        except Exception:
            self.process.kill()
        finally:
            self.process = None
            self._started = False
            logger.info("Engine terminated")
    
    def set_variant(self, variant: str) -> None:
        """
        Set the engine variant.
        
        Args:
            variant: Hub variant name ("normal", "frisian", "killer", "bt", "losing")
        
        Note: Must be called before start() to take effect.
        """
        self._variant = variant
    
    def new_game(self) -> None:
        """
        Signal the start of a new game (clears transposition table).
        """
        self._send("new-game")
    
    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        """
        Get the best move for the given board position.
        
        Implements the Engine interface. Sends the position to the engine,
        starts a search, and returns the best move.
        
        Args:
            board: The current board state
            with_evaluation: If True, return (move, score) tuple
        
        Returns:
            Move object, or (Move, score) if with_evaluation=True
        
        Raises:
            RuntimeError: If engine not started or search fails
            ValueError: If board variant not supported
        """
        if not self._started or self.process is None:
            raise RuntimeError("Engine not started. Call start() first.")
        
        # Verify board is 10x10
        if len(board.position) != 50:
            raise ValueError(
                f"Hub protocol only supports 10x10 boards, got {len(board.position)} squares"
            )
        
        # Convert position to Hub format
        hub_pos = board_to_hub_position(board)
        logger.debug(f"Sending position: {hub_pos}")
        logger.debug(f"Board FEN: {board.fen}")
        logger.debug(f"Turn: {'White' if board.turn == Color.WHITE else 'Black'}")
        
        # Build position command
        # Note: We currently don't send move history for repetition detection
        # because it requires sending moves that lead FROM a starting position
        # TO the current position, not the other way around.
        # TODO: Implement proper move history for repetition detection
        self._send(f"pos pos={hub_pos}")
        
        # Set search limits
        if self.depth_limit is not None:
            self._send(f"level depth={self.depth_limit}")
        else:
            self._send(f"level move-time={self.time_limit}")
        
        # Start search
        self._send("go think")
        
        # Read search output until done
        result = self._read_search_result()
        
        # Parse the move and match against legal moves
        move = parse_hub_move(result.move, board.legal_moves, board=board)
        
        if with_evaluation:
            score = result.info.score if result.info.score is not None else 0.0
            return move, score
        
        return move
    
    def ping(self) -> bool:
        """
        Send ping and wait for pong response.
        
        Returns:
            True if engine responded, False on timeout
        """
        self._send("ping")
        line = self._read_line(timeout=5.0)
        if line:
            cmd, _ = parse_hub_line(line)
            return cmd == "pong"
        return False
    
    def _send(self, command: str) -> None:
        """Send a command to the engine."""
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Engine process not running")
        
        logger.debug(f">> {command}")
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
    
    def _read_line(self, timeout: float = 1.0) -> Optional[str]:
        """
        Read a line from engine stdout with timeout.
        
        Returns:
            Line string (stripped) or None on timeout
        """
        if self.process is None or self.process.stdout is None:
            return None
        
        # Simple blocking read (for now, no async)
        # In production, consider using select() or threading for proper timeout
        import select
        import sys
        
        if sys.platform == "win32":
            # Windows doesn't support select on pipes, use blocking read
            # The engine should respond quickly enough
            try:
                line = self.process.stdout.readline()
                if line:
                    line = line.strip()
                    logger.debug(f"<< {line}")
                    return line
            except Exception:
                pass
            return None
        else:
            # Unix: use select for timeout
            ready, _, _ = select.select([self.process.stdout], [], [], timeout)
            if ready:
                line = self.process.stdout.readline().strip()
                logger.debug(f"<< {line}")
                return line
            return None
    
    def _read_search_result(self) -> SearchResult:
        """
        Read search output until 'done' line is received.
        
        Returns:
            SearchResult with move and search info
        """
        result = SearchResult(move="", info=SearchInfo())
        
        while True:
            timeout_val = self.time_limit * 2 if self.time_limit else 30.0
            line = self._read_line(timeout=max(timeout_val, 30.0))
            if line is None:
                continue
            
            cmd, args = parse_hub_line(line)
            
            if cmd == "info":
                # Update search info
                if "depth" in args:
                    result.info.depth = int(args["depth"])
                if "mean-depth" in args:
                    result.info.mean_depth = float(args["mean-depth"])
                if "score" in args:
                    result.info.score = float(args["score"])
                if "nodes" in args:
                    result.info.nodes = int(args["nodes"])
                if "time" in args:
                    result.info.time = float(args["time"])
                if "nps" in args:
                    result.info.nps = float(args["nps"])
                if "pv" in args:
                    result.info.pv = args["pv"]
            
            elif cmd == "done":
                result.move = args.get("move", "")
                result.ponder = args.get("ponder")
                if not result.move:
                    raise RuntimeError("Engine returned 'done' without move")
                break
            
            elif cmd == "error":
                msg = args.get("message", "Unknown error")
                raise RuntimeError(f"Engine error: {msg}")
        
        return result
    
    def _get_king_move_history(self, board: BaseBoard) -> list[Move]:
        """
        Get king moves from move history for repetition detection.
        
        Hub protocol only needs king moves (reversible moves) for
        detecting draw by repetition.
        
        Returns:
            List of king moves from the move stack
        """
        king_moves = []
        
        for move in board._moves_stack:
            # A move is a king move if:
            # - No captures (non-reversible)
            # - The piece at destination is a king (was a king before moving)
            if not move.captured_list:
                # Check if it was a king move by looking at current position
                # (the king is now at the last square of the move)
                end_sq = move.square_list[-1]
                piece = board.position[end_sq]
                if abs(piece) == Figure.KING.value:
                    king_moves.append(move)
        
        return king_moves
