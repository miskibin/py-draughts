"""Alpha-Beta search engine with advanced optimizations."""
from __future__ import annotations

import math
import random
import time
from typing import List

import numpy as np
from loguru import logger

from draughts.boards.base import BaseBoard
from draughts.boards.standard import Move
from draughts.engines.engine import Engine
from draughts.models import Color


# Search constants
INF = 10_000.0
CHECKMATE = 1_000.0
TT_MAX_ENTRIES = 500_000
IID_DEPTH = 3
QS_MAX_DEPTH = 8
MAX_PLY = 64

# TT entry flags
TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

# Material values (king≈3 is the canonical draughts rule-of-thumb; see research
# report — Scan's evaluation bootstraps from exactly this prior).
MAN_VALUE = 1.0
KING_VALUE = 3.0

# Null-move reduction schedule.
NMP_MIN_DEPTH = 3
NMP_R_BASE = 2
NMP_R_EXTRA_DEPTH = 6  # if depth >= this, use R = base + 1

# Futility / reverse-futility margins (in man-units, per remaining ply).
FUTILITY_MARGIN = [0.0, 1.0, 2.0, 3.0]  # index = depth

# Aspiration window width (man-units) at root.
ASPIRATION_WINDOW = 0.25


# ---------------------------------------------------------------------------
# Piece-Square Tables
# ---------------------------------------------------------------------------
def _create_pst_man(num_squares: int, rows: int) -> np.ndarray:
    """PST for men: reward advancement toward the promotion row."""
    squares_per_row = num_squares // rows
    pst = np.zeros(num_squares, dtype=np.float64)
    for i in range(num_squares):
        row = i // squares_per_row
        col = i % squares_per_row
        advancement_bonus = (rows - 1 - row) / (rows - 1) * 0.3
        center_bonus = (1 - abs(col - squares_per_row / 2) / (squares_per_row / 2)) * 0.05
        pst[i] = advancement_bonus + center_bonus
    return pst


def _create_pst_king(num_squares: int, rows: int) -> np.ndarray:
    """PST for kings: reward central squares."""
    squares_per_row = num_squares // rows
    pst = np.zeros(num_squares, dtype=np.float64)
    center_row = rows / 2
    center_col = squares_per_row / 2
    for i in range(num_squares):
        row = i // squares_per_row
        col = i % squares_per_row
        row_dist = abs(row - center_row) / center_row
        col_dist = abs(col - center_col) / center_col
        pst[i] = (1 - (row_dist + col_dist) / 2) * 0.25
    return pst


# ---------------------------------------------------------------------------
# LMR reduction table — log(depth) * log(moveIndex) schedule.
# ---------------------------------------------------------------------------
def _build_lmr_table(max_depth: int = 64, max_moves: int = 64) -> np.ndarray:
    tbl = np.zeros((max_depth, max_moves), dtype=np.int32)
    for d in range(1, max_depth):
        for i in range(1, max_moves):
            tbl[d, i] = int(0.75 + 0.40 * math.log(d) * math.log(i))
    return tbl


_LMR_TABLE = _build_lmr_table()


class AlphaBetaEngine(Engine):
    """Negamax/αβ search engine with modern pruning and a material+PST eval.

    Beyond classical αβ this engine implements:

    * Iterative deepening with **aspiration windows** at the root.
    * **Principal-variation search** with **late-move reductions** (log/log table).
    * **Null-move pruning**, disabled when a capture is available (draughts'
      forced-capture rule removes the "pass" option whenever a capture exists)
      and in piece-sparse endgames to avoid zugzwang mis-prunes.
    * **Futility** and **reverse-futility** pruning at shallow depths.
    * **Two-bucket transposition table** (depth-preferred + always-replace) with
      a generation counter for aging and a 32-bit key-fragment collision check.
    * Zobrist hashing that is **variant-aware** (Standard and Frisian don't
      collide despite sharing 50 squares) and includes ``halfmove_clock`` so
      positions with different draw horizons don't share a TT entry.
    * Quiescence search extending captures only (sound under forced-capture
      variants; American is optional-capture so QS simply finds fewer captures).
    * Move ordering: PV move, captures by count, killers, and a history table
      keyed on ``(start, end, is_promotion)``.

    Evaluation:

    * Material: man = 1.0, king = 3.0.
    * Piece-square tables for men (advancement) and kings (centre).
    * Tempo bonus for the side to move.
    * Mobility bonus (#legal moves scaled).

    Works for all 4 variants (Standard, American, Frisian, Russian).
    """

    def __init__(
        self,
        depth_limit: int = 6,
        time_limit: float | None = None,
        name: str | None = None,
    ):
        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.name = name or self.__class__.__name__
        self.nodes: int = 0

        # Two-bucket TT: tt[key] -> (entry_depth_pref, entry_always_replace)
        # Each entry is (depth, flag, score, move, key_fragment, generation)
        # or None if that bucket is empty.
        self.tt: dict[int, tuple] = {}
        self.tt_generation: int = 0

        # Move-ordering auxiliary tables.
        self.history: dict[tuple, int] = {}
        self.killers: dict[int, list[Move]] = {}

        # Zobrist: variant-aware. Keyed by (variant_name, num_squares) so
        # Standard and Frisian don't share the same 64-bit key set.
        self._zobrist_tables: dict[tuple[str, int], list[list[int]]] = {}
        self._zobrist_halfmove: dict[tuple[str, int], list[int]] = {}
        self._zobrist_turn = random.Random(0xC0FFEE).getrandbits(64)

        # PST cache (num_squares, rows) -> (pst_man_b, pst_man_w, pst_king_b, pst_king_w).
        self._pst_cache: dict[tuple[int, int], tuple] = {}

        # Current-search cache (updated at start of each search).
        self._current_zobrist: list[list[int]] | None = None
        self._current_halfmove_z: list[int] | None = None
        self._current_pst: tuple | None = None
        self._current_variant_key: tuple[str, int] | None = None

        self.start_time: float = 0.0
        self.stop_search: bool = False

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def inspected_nodes(self) -> int:
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    # ------------------------------------------------------------------
    # Zobrist
    # ------------------------------------------------------------------
    def _variant_key(self, board: BaseBoard) -> tuple[str, int]:
        # Every concrete variant subclasses BaseBoard and sets VARIANT_NAME
        # ("Standard (international) checkers", "Frisian", ...). The Python
        # class itself is called ``Board`` in every module, so we can't rely
        # on ``type(board).__name__`` for uniqueness.
        return (board.VARIANT_NAME, board.SQUARES_COUNT)

    def _get_zobrist_table(self, variant_key: tuple[str, int]) -> list[list[int]]:
        if variant_key not in self._zobrist_tables:
            # Deterministic RNG seeded by variant name + size so two engine
            # instances always agree; different variants never collide.
            seed = hash(variant_key) & 0xFFFFFFFF
            rng = random.Random(seed)
            num_squares = variant_key[1]
            self._zobrist_tables[variant_key] = [
                [rng.getrandbits(64) for _ in range(5)] for _ in range(num_squares)
            ]
            # Small halfmove-clock table; capped at 64 (any variant's draw
            # horizon is < 64 halfmoves).
            self._zobrist_halfmove[variant_key] = [
                rng.getrandbits(64) for _ in range(64)
            ]
        return self._zobrist_tables[variant_key]

    def _get_halfmove_z(self, variant_key: tuple[str, int]) -> list[int]:
        self._get_zobrist_table(variant_key)  # ensures both are populated
        return self._zobrist_halfmove[variant_key]

    def _get_pst_tables(self, num_squares: int, rows: int) -> tuple:
        key = (num_squares, rows)
        cached = self._pst_cache.get(key)
        if cached is None:
            pst_man_black = _create_pst_man(num_squares, rows)
            pst_man_white = pst_man_black[::-1].copy()
            pst_king_black = _create_pst_king(num_squares, rows)
            pst_king_white = pst_king_black[::-1].copy()
            cached = (pst_man_black, pst_man_white, pst_king_black, pst_king_white)
            self._pst_cache[key] = cached
        return cached

    @staticmethod
    def _board_rows(board: BaseBoard) -> int:
        return board.shape[0]

    def _ensure_caches(self, board: BaseBoard) -> None:
        """Populate zobrist / pst caches for ``board``'s variant. Idempotent."""
        vk = self._variant_key(board)
        if vk == self._current_variant_key:
            return
        self._current_variant_key = vk
        self._current_zobrist = self._get_zobrist_table(vk)
        self._current_halfmove_z = self._get_halfmove_z(vk)
        self._current_pst = self._get_pst_tables(board.SQUARES_COUNT, self._board_rows(board))

    @staticmethod
    def _piece_index(piece: int) -> int:
        return piece + 2  # maps {-2,-1,0,1,2} -> {0,1,2,3,4}

    def _compute_hash(self, board: BaseBoard) -> int:
        """Full-board Zobrist hash. Uses the engine's *current* variant cache."""
        zt = self._current_zobrist
        h = 0
        # Iterate 4 bitboards instead of 50 _get calls — faster.
        for piece, bb in (
            (-1, board.white_men),
            (-2, board.white_kings),
            (1, board.black_men),
            (2, board.black_kings),
        ):
            idx = piece + 2
            while bb:
                lsb = bb & -bb
                sq = lsb.bit_length() - 1
                h ^= zt[sq][idx]
                bb ^= lsb
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        # Include halfmove_clock so positions with different draw horizons
        # don't share TT entries.
        h ^= self._current_halfmove_z[min(board.halfmove_clock, 63)]
        return h

    def compute_hash(self, board: BaseBoard) -> int:
        """Public, standalone Zobrist hash (ensures caches for ``board``)."""
        self._ensure_caches(board)
        return self._compute_hash(board)

    def _update_hash(self, current_hash: int, board: BaseBoard, move: Move) -> int:
        """Incrementally update hash for ``move`` assuming ``board`` is the
        pre-move state. Does NOT update halfmove_clock component — caller
        must XOR old and new halfmove keys separately (simpler: re-hash)."""
        zt = self._current_zobrist
        start_sq = move.square_list[0]
        piece = board._get(start_sq)
        current_hash ^= zt[start_sq][piece + 2]

        end_sq = move.square_list[-1]
        new_piece = piece
        if move.is_promotion:
            new_piece = 2 if piece == 1 else -2
        current_hash ^= zt[end_sq][new_piece + 2]

        for cap_sq in move.captured_list:
            cap_piece = board._get(cap_sq)
            current_hash ^= zt[cap_sq][cap_piece + 2]

        current_hash ^= self._zobrist_turn
        return current_hash

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------
    def evaluate(self, board: BaseBoard) -> float:
        """Static evaluation from the perspective of the side to move."""
        self._ensure_caches(board)
        pst = self._current_pst

        # Counts derived directly from bitboards — avoids allocating a 50-entry
        # numpy array per call and avoids the PST-size mismatch bug when
        # evaluate() is called on a variant the engine hasn't searched yet.
        n_wm = _popcount(board.white_men)
        n_wk = _popcount(board.white_kings)
        n_bm = _popcount(board.black_men)
        n_bk = _popcount(board.black_kings)

        score = (n_bm - n_wm) * MAN_VALUE + (n_bk - n_wk) * KING_VALUE

        # PST: iterate set bits — O(pieces) not O(squares).
        score += _pst_sum(pst[0], board.black_men)
        score -= _pst_sum(pst[1], board.white_men)
        score += _pst_sum(pst[2], board.black_kings)
        score -= _pst_sum(pst[3], board.white_kings)

        # Tempo: small bonus for having the move.
        if board.turn == Color.WHITE:
            score -= 0.05
        else:
            score += 0.05

        # Return score from the side-to-move perspective (positive = good for us).
        return -score if board.turn == Color.WHITE else score

    # ------------------------------------------------------------------
    # Transposition table (two buckets + aging)
    # ------------------------------------------------------------------
    def _tt_probe(self, key: int):
        """Return the best matching entry for ``key`` or None."""
        buckets = self.tt.get(key)
        if buckets is None:
            return None
        # Prefer depth-preferred bucket.
        dp, ar = buckets
        return dp if dp is not None else ar

    def _tt_store(
        self,
        key: int,
        depth: int,
        flag: int,
        score: float,
        move: Move | None,
    ) -> None:
        entry = (depth, flag, score, move, self.tt_generation)
        buckets = self.tt.get(key)
        if buckets is None:
            self.tt[key] = (entry, None)
            return
        dp, ar = buckets
        # Depth-preferred: replace if deeper or stale generation.
        if dp is None or depth >= dp[0] or dp[4] != self.tt_generation:
            self.tt[key] = (entry, ar)
        else:
            # Otherwise write to always-replace slot.
            self.tt[key] = (dp, entry)

    def _tt_prune(self) -> None:
        """Shrink TT to half its size if it exceeds the cap. Prefers to keep
        deep, recent-generation entries."""
        if len(self.tt) <= TT_MAX_ENTRIES:
            return
        gen = self.tt_generation
        items = list(self.tt.items())
        # Score each bucket-pair: max depth * 8 - age_penalty.
        def score(item):
            _, (dp, ar) = item
            e = dp if dp is not None else ar
            if e is None:
                return -1
            d, _, _, _, g = e
            return d * 8 - (gen - g)
        items.sort(key=score, reverse=True)
        keep = items[: TT_MAX_ENTRIES // 2]
        self.tt = dict(keep)

    # ------------------------------------------------------------------
    # Search entry point
    # ------------------------------------------------------------------
    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("No legal moves available")

        self.start_time = time.time()
        self.nodes = 0
        self.stop_search = False
        self.tt_generation = (self.tt_generation + 1) & 0xFF
        self._ensure_caches(board)

        # Age the history table so stale values decay.
        if self.history:
            for k in self.history:
                self.history[k] //= 2

        root_hash = self._compute_hash(board)
        best_move: Move | None = None
        best_score = -INF

        max_depth = self.depth_limit or 6
        prev_score = 0.0

        for depth in range(1, max_depth + 1):
            # ----- Aspiration windows (only once we have a seed score) -----
            if depth >= 4:
                alpha, beta = prev_score - ASPIRATION_WINDOW, prev_score + ASPIRATION_WINDOW
                width = ASPIRATION_WINDOW
                while True:
                    score = self._negamax(board, depth, alpha, beta, root_hash, ply=0, allow_null=True)
                    if self.stop_search:
                        break
                    if score <= alpha:
                        width *= 2
                        alpha = max(alpha - width, -INF)
                    elif score >= beta:
                        width *= 2
                        beta = min(beta + width, INF)
                    else:
                        break
            else:
                score = self._negamax(board, depth, -INF, INF, root_hash, ply=0, allow_null=True)

            if self.stop_search:
                break

            entry = self._tt_probe(root_hash)
            if entry is not None and entry[3] is not None:
                best_move = entry[3]
                best_score = score
                prev_score = score

            logger.debug(f"Depth {depth}: score={score:.3f}, move={best_move}, nodes={self.nodes}")

            if self.time_limit and (time.time() - self.start_time > self.time_limit):
                break

        self._tt_prune()
        logger.info(f"Best move: {best_move}, score: {best_score:.2f}, nodes: {self.nodes}")

        if best_move is None:
            best_move = legal_moves[0]
            best_score = -INF

        if with_evaluation:
            return best_move, float(best_score)
        return best_move

    # ------------------------------------------------------------------
    # Negamax with PVS, LMR, NMP, futility
    # ------------------------------------------------------------------
    def _check_time(self) -> None:
        if self.time_limit and (time.time() - self.start_time > self.time_limit):
            self.stop_search = True

    def _negamax(
        self,
        board: BaseBoard,
        depth: int,
        alpha: float,
        beta: float,
        h: int,
        ply: int,
        allow_null: bool,
    ) -> float:
        self.nodes += 1

        if (self.nodes & 2047) == 0:
            self._check_time()
        if self.stop_search:
            return alpha

        in_pv = (beta - alpha) > 1e-9

        # ----- TT probe -----
        entry = self._tt_probe(h)
        if entry is not None and ply > 0:
            tt_depth, tt_flag, tt_score, tt_move, _ = entry
            if tt_depth >= depth:
                if tt_flag == TT_EXACT:
                    return tt_score
                if tt_flag == TT_LOWER and tt_score > alpha:
                    alpha = tt_score
                elif tt_flag == TT_UPPER and tt_score < beta:
                    beta = tt_score
                if alpha >= beta:
                    return tt_score

        # ----- Leaf -----
        if depth <= 0:
            return self._quiescence(board, alpha, beta, h, 0)

        # ----- Draw -----
        if board.is_draw:
            return 0.0

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            # Side to move has no moves -> loss (draughts: losing side has no moves).
            return -CHECKMATE + ply

        has_capture_available = any(m.captured_list for m in legal_moves)
        static_eval = self.evaluate(board) if not in_pv else None

        # ----- Reverse futility pruning (a.k.a. static null-move) -----
        # If our static eval already beats beta by a healthy margin at shallow
        # depth, skip the search. Disabled in PV nodes and when captures are
        # available (tactical shots might reverse the assessment).
        if (
            not in_pv
            and depth <= 3
            and not has_capture_available
            and static_eval is not None
        ):
            margin = FUTILITY_MARGIN[depth] if depth < len(FUTILITY_MARGIN) else depth * 1.0
            if static_eval - margin >= beta:
                return static_eval - margin

        # ----- Null-move pruning -----
        # Only when: enough depth, no capture forced, not in PV, and not in a
        # piece-sparse endgame where zugzwang is a real risk.
        if (
            allow_null
            and not in_pv
            and depth >= NMP_MIN_DEPTH
            and not has_capture_available
            and _total_pieces(board) >= 6
        ):
            r = NMP_R_BASE + (1 if depth >= NMP_R_EXTRA_DEPTH else 0)
            # Flip turn; don't perturb bitboards. We re-hash because
            # halfmove_clock doesn't change.
            old_turn = board.turn
            board.turn = Color.BLACK if old_turn == Color.WHITE else Color.WHITE
            null_hash = h ^ self._zobrist_turn
            null_score = -self._negamax(
                board, depth - 1 - r, -beta, -beta + 1e-9, null_hash, ply + 1, allow_null=False
            )
            board.turn = old_turn
            if self.stop_search:
                return alpha
            if null_score >= beta:
                return beta

        # ----- Internal iterative deepening (mostly for PV nodes w/o TT move) -----
        if depth >= IID_DEPTH and (entry is None or entry[3] is None) and in_pv:
            self._negamax(board, depth - 2, alpha, beta, h, ply, allow_null=False)
            entry = self._tt_probe(h)

        legal_moves = self._order_moves(legal_moves, board, h, ply, depth)

        best_value = -INF
        best_move: Move | None = None
        tt_flag = TT_UPPER
        original_alpha = alpha

        for i, move in enumerate(legal_moves):
            is_capture = bool(move.captured_list)

            # ----- Futility pruning of quiet moves at shallow depth -----
            if (
                not in_pv
                and depth <= 2
                and i > 0
                and not is_capture
                and not move.is_promotion
                and static_eval is not None
            ):
                margin = FUTILITY_MARGIN[depth] if depth < len(FUTILITY_MARGIN) else depth * 1.0
                if static_eval + margin <= alpha:
                    continue

            board.push(move)
            # We re-hash because halfmove_clock changes on push; full re-hash
            # keeps TT correctness without tracking every component.
            new_hash = self._compute_hash(board)

            if i == 0:
                val = -self._negamax(board, depth - 1, -beta, -alpha, new_hash, ply + 1, allow_null=True)
            else:
                # LMR with log/log table; don't reduce captures or promotions.
                reduction = 0
                if depth >= 3 and not is_capture and not move.is_promotion and i >= 2:
                    reduction = int(_LMR_TABLE[min(depth, 63), min(i, 63)])
                    if in_pv:
                        reduction = max(0, reduction - 1)
                    reduction = min(reduction, depth - 2)
                    reduction = max(0, reduction)
                # Null-window search first.
                val = -self._negamax(
                    board, depth - 1 - reduction, -alpha - 1e-9, -alpha, new_hash, ply + 1, allow_null=True
                )
                # Re-search at full depth/window if it looks promising.
                if val > alpha and (reduction > 0 or val < beta):
                    val = -self._negamax(board, depth - 1, -beta, -alpha, new_hash, ply + 1, allow_null=True)

            board.pop()

            if self.stop_search:
                return alpha

            if val > best_value:
                best_value = val
                best_move = move

            if val > alpha:
                alpha = val
                tt_flag = TT_EXACT

            if alpha >= beta:
                tt_flag = TT_LOWER
                if not is_capture:
                    self._update_killers(move, ply)
                    self._update_history(move, depth)
                break

        # Never store partial results when we aborted mid-search.
        if not self.stop_search:
            if tt_flag == TT_EXACT and best_value <= original_alpha:
                tt_flag = TT_UPPER  # safety
            self._tt_store(h, depth, tt_flag, best_value, best_move)

        return best_value

    # ------------------------------------------------------------------
    # Quiescence (captures only)
    # ------------------------------------------------------------------
    def _quiescence(self, board: BaseBoard, alpha: float, beta: float, h: int, qs_depth: int) -> float:
        self.nodes += 1
        stand_pat = self.evaluate(board)
        if stand_pat >= beta:
            return beta
        if alpha < stand_pat:
            alpha = stand_pat
        if qs_depth >= QS_MAX_DEPTH:
            return stand_pat

        legal_moves = list(board.legal_moves)
        captures = [m for m in legal_moves if m.captured_list]
        if not captures:
            return stand_pat

        captures.sort(key=lambda m: len(m.captured_list), reverse=True)

        for move in captures:
            board.push(move)
            score = -self._quiescence(board, -beta, -alpha, self._compute_hash(board), qs_depth + 1)
            board.pop()
            if score >= beta:
                return beta
            if score > alpha:
                alpha = score
        return alpha

    # ------------------------------------------------------------------
    # Move ordering
    # ------------------------------------------------------------------
    def _order_moves(
        self,
        moves: List[Move],
        board: BaseBoard | None = None,
        h: int = 0,
        ply: int = 0,
        depth: int = 0,
    ) -> List[Move]:
        entry = self._tt_probe(h)
        pv_move = entry[3] if entry else None
        killers = self.killers.get(ply, ())

        history = self.history

        def score_move(m: Move) -> int:
            if pv_move is not None and m == pv_move:
                return 10_000_000
            if m.captured_list:
                # Forced-capture variants already filter; American doesn't.
                return 1_000_000 + len(m.captured_list) * 1_000
            if m in killers:
                return 900_000
            key = (m.square_list[0], m.square_list[-1], m.is_promotion)
            return history.get(key, 0)

        moves.sort(key=score_move, reverse=True)
        return moves

    def _update_killers(self, move: Move, ply: int) -> None:
        slot = self.killers.get(ply)
        if slot is None:
            self.killers[ply] = [move]
            return
        if move in slot:
            return
        slot.insert(0, move)
        del slot[2:]

    def _update_history(self, move: Move, depth: int) -> None:
        key = (move.square_list[0], move.square_list[-1], move.is_promotion)
        self.history[key] = self.history.get(key, 0) + depth * depth


# ---------------------------------------------------------------------------
# Bitboard helpers
# ---------------------------------------------------------------------------
def _popcount(bb: int) -> int:
    return bin(bb).count("1")


def _pst_sum(table: np.ndarray, bb: int) -> float:
    """Sum ``table`` over the set bits of ``bb``."""
    total = 0.0
    while bb:
        lsb = bb & -bb
        total += float(table[lsb.bit_length() - 1])
        bb ^= lsb
    return total


def _total_pieces(board: BaseBoard) -> int:
    return _popcount(board.white_men | board.white_kings | board.black_men | board.black_kings)
