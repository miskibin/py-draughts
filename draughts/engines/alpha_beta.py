"""Alpha-beta search engine for draughts."""
from __future__ import annotations

import random
import time
from typing import Optional

import numpy as np
from loguru import logger

from draughts.boards.base import BaseBoard
from draughts.engines.engine import Engine
from draughts.models import Color
from draughts.move import Move


INF = 10000.0
CHECKMATE = 1000.0

TT_BUCKETS = 1 << 18  # power of two; two entries per bucket -> 524 288 slots
HALFMOVE_CAP = 64     # halfmove clock keys collapse here; > all variant draw thresholds
QS_MAX_DEPTH = 8
IID_DEPTH = 3

EXACT, LOWER, UPPER = 0, 1, 2

# Search-stability constants. Conservative values that survived the
# Frisian ablation that found NMP × LMR × RFP losing 90% of games at
# depth 5 in narrow endgames. LMR was dropped entirely.
NMP_MIN_DEPTH = 3
NMP_REDUCTION = 2
NMP_MIN_OWN_PIECES = 6
RFUT_MARGIN = 0.9


def _build_zobrist(game_type: int, num_squares: int) -> tuple[list, list]:
    """Variant-keyed Zobrist tables.

    Standard and Frisian both have 50 squares, but different ``GAME_TYPE``s
    so they get distinct random tables (avoiding TT cross-contamination).
    """
    rng = random.Random(f"draughts:{game_type}:{num_squares}")
    pieces = [[rng.getrandbits(64) for _ in range(5)] for _ in range(num_squares)]
    halfmove = [rng.getrandbits(64) for _ in range(HALFMOVE_CAP)]
    return pieces, halfmove


def _build_pst(num_squares: int, rows: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Piece-square tables: ``(man_black, man_white, king_black, king_white)``."""
    cols = num_squares // rows
    man = np.zeros(num_squares)
    king = np.zeros(num_squares)
    for i in range(num_squares):
        row, col = divmod(i, cols)
        # Men: reward advancement (toward row 0 = promotion for black) + slight center pull.
        man[i] = (rows - 1 - row) / (rows - 1) * 0.3 + (1 - abs(col - cols / 2) / (cols / 2)) * 0.05
        # Kings: prefer the centre.
        king[i] = (1 - (abs(row - rows / 2) / (rows / 2) + abs(col - cols / 2) / (cols / 2)) / 2) * 0.25
    return man, man[::-1].copy(), king, king[::-1].copy()


class AlphaBetaEngine(Engine):
    """
    Negamax + alpha-beta with iterative deepening, aspiration windows,
    null-move pruning, reverse futility, two-bucket TT, killers / history,
    and quiescence on captures.

    Example:
        >>> from draughts import Board, AlphaBetaEngine
        >>> engine = AlphaBetaEngine(depth_limit=6)
        >>> move = engine.get_best_move(Board())
    """

    DEFAULT_EVAL_PARAMS: dict = {
        "man_value": 1.0,
        "king_value": 3.0,
        "tempo": 0.05,
        "back_rank_bonus": 0.10,
    }

    def __init__(
        self,
        depth_limit: int = 6,
        time_limit: Optional[float] = None,
        name: Optional[str] = None,
        eval_params: Optional[dict] = None,
    ):
        super().__init__(depth_limit=depth_limit, time_limit=time_limit, name=name)
        self.eval_params = {**self.DEFAULT_EVAL_PARAMS, **(eval_params or {})}

        self.nodes = 0
        self.start_time = 0.0
        self.stop_search = False

        # Two-bucket transposition table: entry = (key, depth, flag, score, move, gen)
        self._tt_dp: list = [None] * TT_BUCKETS
        self._tt_ar: list = [None] * TT_BUCKETS
        self._tt_gen = 0

        self.history: dict[tuple, int] = {}
        self.killers: dict[int, list[Move]] = {}

        self._zobrist_cache: dict = {}
        self._zobrist_turn = random.Random("draughts:turn").getrandbits(64)
        self._pst_cache: dict = {}

        # Lazily bound to the board's variant on first hash/eval/search call.
        self._bound_variant: int = -1
        self._zob: tuple[list, list] = ([], [])
        self._pst: tuple = ()

    # Existing tests reference inspected_nodes; keep the alias.
    @property
    def inspected_nodes(self) -> int:
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    # ---- Variant binding (lazy) ------------------------------------------

    def _bind(self, board: BaseBoard) -> None:
        """Bind Zobrist & PST tables to the board's variant on first use."""
        if self._bound_variant == board.GAME_TYPE:
            return
        zk = (board.GAME_TYPE, board.SQUARES_COUNT)
        self._zob = self._zobrist_cache.setdefault(zk, _build_zobrist(*zk))
        pk = (board.SQUARES_COUNT, board.shape[0])
        self._pst = self._pst_cache.setdefault(pk, _build_pst(*pk))
        self._bound_variant = board.GAME_TYPE

    def compute_hash(self, board: BaseBoard) -> int:
        """Standalone Zobrist hash for ``board``."""
        self._bind(board)
        return self._hash(board)

    def _hash(self, board: BaseBoard) -> int:
        pt, ht = self._zob
        h = ht[min(board.halfmove_clock, HALFMOVE_CAP - 1)]
        for i, piece in enumerate(board._pos):
            if piece != 0:
                h ^= pt[i][piece + 2]
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        return h

    def _update_hash(self, h: int, board: BaseBoard, move: Move) -> int:
        """Incremental hash update; called pre-push so we read the board before the move."""
        pt, ht = self._zob

        h ^= ht[min(board.halfmove_clock, HALFMOVE_CAP - 1)]

        start_sq, end_sq = move.square_list[0], move.square_list[-1]
        piece = board._pos[start_sq]
        h ^= pt[start_sq][piece + 2]

        # Detect promotion from board state (move.is_promotion is set during push).
        end_bit = 1 << end_sq
        if (piece == -1 and (board.PROMO_WHITE & end_bit)) or (piece == 1 and (board.PROMO_BLACK & end_bit)):
            new_piece = 2 if piece == 1 else -2
        else:
            new_piece = piece
        h ^= pt[end_sq][new_piece + 2]

        for cap_sq in move.captured_list:
            h ^= pt[cap_sq][board._pos[cap_sq] + 2]

        # Halfmove clock advances only for non-capturing king moves.
        new_hm = board.halfmove_clock + 1 if abs(piece) == 2 and not move.captured_list else 0
        h ^= ht[min(new_hm, HALFMOVE_CAP - 1)]

        return h ^ self._zobrist_turn

    # ---- Evaluation -------------------------------------------------------

    def evaluate(self, board: BaseBoard) -> float:
        """Static eval from the side-to-move's perspective.

        Material (king = 3.0) + piece-square tables + back-rank guard
        (opening/midgame only) + tempo. Parameters live in
        ``self.eval_params`` for the Texel tuner in ``tools/tune_eval.py``.
        """
        self._bind(board)
        pos = board._pos
        pmb, pmw, pkb, pkw = self._pst
        p = self.eval_params

        wm, wk = (pos == -1), (pos == -2)
        bm, bk = (pos == 1), (pos == 2)
        n_wm, n_wk, n_bm, n_bk = int(wm.sum()), int(wk.sum()), int(bm.sum()), int(bk.sum())

        score = (n_bm - n_wm) * p["man_value"] + (n_bk - n_wk) * p["king_value"]
        score += pmb[bm].sum() - pmw[wm].sum() + pkb[bk].sum() - pkw[wk].sum()

        # Back-rank guard bonus while pieces are still developing.
        if n_wm + n_wk + n_bm + n_bk >= 14:
            cols = board.SQUARES_COUNT // board.shape[0]
            score += (int(bm[:cols].sum()) - int(wm[-cols:].sum())) * p["back_rank_bonus"]

        if board.turn == Color.WHITE:
            score = -score
        return float(score + p["tempo"])

    # ---- Top-level search -------------------------------------------------

    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        """Iterative deepening with aspiration windows."""
        self.start_time = time.time()
        self.nodes = 0
        self.stop_search = False
        self._tt_gen = (self._tt_gen + 1) & 0xFF
        self._bind(board)

        # Decay history; killers only live for one search.
        for k in self.history:
            self.history[k] //= 2
        self.killers.clear()

        root_hash = self._hash(board)
        max_depth = self.depth_limit or 6

        best_move: Optional[Move] = None
        best_score = -INF
        prev_score = 0.0

        for d in range(1, max_depth + 1):
            score = self._aspiration(board, d, prev_score, root_hash)
            if self.stop_search:
                break
            entry = self._tt_probe(root_hash)
            if entry is not None and entry[4] is not None:
                best_move = entry[4]
                best_score = score
                prev_score = score
            if self.time_limit and time.time() - self.start_time > self.time_limit:
                break

        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves available")
        if best_move is None:
            best_move = legal[0]
            best_score = self.evaluate(board)

        logger.debug(f"best={best_move} score={best_score:.2f} nodes={self.nodes}")
        return (best_move, float(best_score)) if with_evaluation else best_move

    def _aspiration(self, board: BaseBoard, depth: int, prev: float, root_hash: int) -> float:
        if depth < 3:
            return self.negamax(board, depth, -INF, INF, root_hash, 0)
        delta = 0.5
        alpha, beta = prev - delta, prev + delta
        while True:
            score = self.negamax(board, depth, alpha, beta, root_hash, 0)
            if self.stop_search:
                return score
            if score <= alpha:
                alpha -= delta
            elif score >= beta:
                beta += delta
            else:
                return score
            delta *= 2
            if delta > INF / 4:  # safety: full re-search
                return self.negamax(board, depth, -INF, INF, root_hash, 0)

    # ---- Negamax ----------------------------------------------------------

    def _time_up(self) -> bool:
        if self.time_limit and time.time() - self.start_time > self.time_limit:
            self.stop_search = True
        return self.stop_search

    def negamax(
        self, board: BaseBoard, depth: int, alpha: float, beta: float, h: int, ply: int
    ) -> float:
        self.nodes += 1
        if self.nodes & 2047 == 0 and self._time_up():
            return alpha
        if self.stop_search:
            return alpha

        in_pv = (beta - alpha) > 1.0001

        # ---- TT probe ----
        tt_entry = self._tt_probe(h)
        tt_move: Optional[Move] = None
        if tt_entry is not None:
            _, tt_depth, tt_flag, tt_score, tt_move, _ = tt_entry
            if tt_depth >= depth and not in_pv:
                if tt_flag == EXACT:
                    return tt_score
                if tt_flag == LOWER and tt_score >= beta:
                    return tt_score
                if tt_flag == UPPER and tt_score <= alpha:
                    return tt_score

        if depth <= 0:
            return self.quiescence(board, alpha, beta, h)

        legal = list(board.legal_moves)
        if not legal:
            return -CHECKMATE + ply  # loss; prefer faster mates
        if board.is_draw:
            return 0.0

        has_capture = any(m.captured_list for m in legal)
        static_eval: Optional[float] = None  # computed lazily, reused by RFP/NMP

        # ---- Reverse futility ----
        if depth <= 3 and not in_pv and not has_capture and abs(beta) < CHECKMATE - 100:
            static_eval = self.evaluate(board)
            margin = depth * RFUT_MARGIN
            if static_eval - margin >= beta:
                return static_eval - margin

        # ---- Null-move pruning (gated to avoid zugzwang) ----
        if (
            depth >= NMP_MIN_DEPTH
            and ply > 0
            and not in_pv
            and not has_capture
            and self._own_pieces(board) >= NMP_MIN_OWN_PIECES
        ):
            if static_eval is None:
                static_eval = self.evaluate(board)
            if static_eval >= beta:
                board.turn = Color.BLACK if board.turn == Color.WHITE else Color.WHITE
                null_score = -self.negamax(
                    board, depth - 1 - NMP_REDUCTION, -beta, -beta + 1,
                    h ^ self._zobrist_turn, ply + 1,
                )
                board.turn = Color.BLACK if board.turn == Color.WHITE else Color.WHITE
                if self.stop_search:
                    return alpha
                if null_score >= beta:
                    return null_score

        # ---- Internal Iterative Deepening (cheap PV-move discovery) ----
        if depth >= IID_DEPTH and tt_move is None:
            self.negamax(board, depth - 2, alpha, beta, h, ply + 1)
            if self.stop_search:
                return alpha
            iid = self._tt_probe(h)
            if iid is not None:
                tt_move = iid[4]

        legal = self._order_moves(legal, tt_move, depth)

        best_value = -INF
        best_move: Optional[Move] = None
        flag = UPPER

        for i, move in enumerate(legal):
            new_hash = self._update_hash(h, board, move)
            board.push(move)
            if i == 0:
                val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash, ply + 1)
            else:
                val = -self.negamax(board, depth - 1, -alpha - 1, -alpha, new_hash, ply + 1)
                if alpha < val < beta:
                    val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash, ply + 1)
            board.pop()

            if self.stop_search:
                return alpha
            if val > best_value:
                best_value = val
                best_move = move
            if val > alpha:
                alpha = val
                flag = EXACT
            if alpha >= beta:
                flag = LOWER
                if not move.captured_list:
                    self._record_killer(move, depth)
                self._record_history(move, depth)
                break

        if not self.stop_search:
            self._tt_store(h, depth, flag, best_value, best_move)
        return best_value

    def quiescence(
        self, board: BaseBoard, alpha: float, beta: float, h: int, qs_depth: int = 0
    ) -> float:
        self.nodes += 1
        if self.nodes & 2047 == 0 and self._time_up():
            return alpha
        if self.stop_search:
            return alpha

        stand_pat = self.evaluate(board)
        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat
        if qs_depth >= QS_MAX_DEPTH:
            return stand_pat

        captures = [m for m in board.legal_moves if m.captured_list]
        if not captures:
            return stand_pat

        captures.sort(key=lambda m: (m.capture_value, len(m.captured_list)), reverse=True)
        for move in captures:
            new_hash = self._update_hash(h, board, move)
            board.push(move)
            score = -self.quiescence(board, -beta, -alpha, new_hash, qs_depth + 1)
            board.pop()
            if self.stop_search:
                return alpha
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # ---- Move ordering ----------------------------------------------------

    def _order_moves(
        self, moves: list[Move], tt_move: Optional[Move] = None, depth: int = 0
    ) -> list[Move]:
        killers = self.killers.get(depth, ())
        history = self.history

        def score(m: Move) -> float:
            if tt_move is not None and m == tt_move:
                return 1e9
            if m.captured_list:
                # MVV: total captured material ranks highest, length as tiebreak.
                return 1e5 + m.capture_value * 1e4 + len(m.captured_list)
            if m in killers:
                return 9e4
            return history.get(
                (m.square_list[0], m.square_list[-1], 1 if m.is_promotion else 0), 0
            )

        moves.sort(key=score, reverse=True)
        return moves

    def _record_killer(self, move: Move, depth: int) -> None:
        bucket = self.killers.setdefault(depth, [])
        if move in bucket:
            return
        bucket.insert(0, move)
        del bucket[2:]

    def _record_history(self, move: Move, depth: int) -> None:
        key = (move.square_list[0], move.square_list[-1], 1 if move.is_promotion else 0)
        self.history[key] = self.history.get(key, 0) + depth * depth

    @staticmethod
    def _own_pieces(board: BaseBoard) -> int:
        if board.turn == Color.WHITE:
            return board._popcount(board.white_men) + board._popcount(board.white_kings)
        return board._popcount(board.black_men) + board._popcount(board.black_kings)

    # ---- Transposition table ---------------------------------------------

    def _tt_probe(self, key: int) -> Optional[tuple]:
        idx = key & (TT_BUCKETS - 1)
        e = self._tt_dp[idx]
        if e is not None and e[0] == key:
            return e
        e = self._tt_ar[idx]
        if e is not None and e[0] == key:
            return e
        return None

    def _tt_store(
        self, key: int, depth: int, flag: int, score: float, move: Optional[Move]
    ) -> None:
        idx = key & (TT_BUCKETS - 1)
        entry = (key, depth, flag, score, move, self._tt_gen)
        dp = self._tt_dp[idx]
        # Depth-preferred bucket: replace when empty / same key / aged-out / not deeper.
        if dp is None or dp[0] == key or dp[5] != self._tt_gen or dp[1] <= depth:
            self._tt_dp[idx] = entry
        else:
            self._tt_ar[idx] = entry
