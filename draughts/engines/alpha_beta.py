"""Alpha-Beta search engine with advanced optimizations."""
from __future__ import annotations

import math
import random
import time
from typing import List, Optional, Tuple

import numpy as np
from loguru import logger

from draughts.boards.base import BaseBoard
from draughts.engines.engine import Engine
from draughts.models import Color
from draughts.move import Move


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INF = 10000.0
CHECKMATE = 1000.0

# Two-bucket transposition table size (must be a power of two for masking).
TT_BUCKETS = 1 << 18  # 262 144 buckets × 2 entries = 524 288 slots

IID_DEPTH = 3
QS_MAX_DEPTH = 8

# Halfmove clock keys are capped: any value >= 64 collapses onto the same
# key. All variant draw thresholds are <= 50, so distinct draw-relevant
# values still hash differently.
HALFMOVE_CAP = 64

# TT bound flags
EXACT = 0
LOWER = 1  # value is a lower bound (caused beta cutoff)
UPPER = 2  # value is an upper bound (no move improved alpha)

# Piece values (Tier 2.1: kings raised from 2.5 → 3.0 per Scan/Kingsrow norms)
MAN_VALUE = 1.0
KING_VALUE = 3.0

# Eval feature weights
TEMPO = 0.05
BACK_RANK_BONUS = 0.10

# Null-move pruning. Conservative parameters that survive ablation across
# all four variants (Frisian in particular). NMP × LMR × RFP combined was
# too aggressive in narrow endgames at depths 4-5.
NMP_MIN_DEPTH = 3
NMP_REDUCTION = 2
NMP_MIN_OWN_PIECES = 6  # below this we're in zugzwang territory
NMP_VERIFY_DEPTH = 8     # above this, verify the cutoff with a smaller search

# Reverse-futility margin per ply
RFUT_MARGIN = 0.9


# ---------------------------------------------------------------------------
# PST helpers
# ---------------------------------------------------------------------------

def _create_pst_man(num_squares: int, rows: int) -> np.ndarray:
    """Piece-square table for men (rewards advancement)."""
    cols = num_squares // rows
    pst = np.zeros(num_squares)
    for i in range(num_squares):
        row = i // cols
        col = i % cols
        advancement = (rows - 1 - row) / (rows - 1) * 0.3
        center = (1 - abs(col - cols / 2) / (cols / 2)) * 0.05
        pst[i] = advancement + center
    return pst


def _create_pst_king(num_squares: int, rows: int) -> np.ndarray:
    """Piece-square table for kings (prefers center)."""
    cols = num_squares // rows
    pst = np.zeros(num_squares)
    cr, cc = rows / 2, cols / 2
    for i in range(num_squares):
        row, col = i // cols, i % cols
        rd = abs(row - cr) / cr
        cdv = abs(col - cc) / cc
        pst[i] = (1 - (rd + cdv) / 2) * 0.25
    return pst


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class AlphaBetaEngine(Engine):
    """
    AI engine using Negamax with alpha-beta pruning and a battery of
    standard search optimisations.

    **Search**
        - Iterative deepening with aspiration windows
        - Principal-variation search (PVS)
        - Two-bucket transposition table (depth-preferred + always-replace)
          with generation-based aging
        - Variant-aware Zobrist hashing including the halfmove clock
        - Null-move pruning (disabled when captures are forced)
        - Reverse futility / razoring at shallow depths
        - Late-move reduction with a logarithmic schedule
        - Quiescence search on captures

    **Move ordering**
        - PV move from TT → captures by ``capture_value`` (MVV) →
          killers → history heuristic

    **Evaluation**
        - Material with king = 3.0 (Scan/Kingsrow convention)
        - Piece-square tables
        - Side-to-move tempo bonus
        - Back-rank guard bonus (opening / midgame only)

    Example:
        >>> from draughts import Board, AlphaBetaEngine
        >>> board = Board()
        >>> engine = AlphaBetaEngine(depth_limit=6)
        >>> move = engine.get_best_move(board)
    """

    DEFAULT_EVAL_PARAMS: dict = {
        "man_value": MAN_VALUE,
        "king_value": KING_VALUE,
        "tempo": TEMPO,
        "back_rank_bonus": BACK_RANK_BONUS,
    }

    # Feature toggles (used by ablation tooling).
    # Recognised flags: ``nmp``, ``aspiration``, ``rfutility``, ``lmr``.
    #
    # Default is **{nmp, aspiration, rfutility}** — LMR is opt-in.
    # Frisian ablation showed LMR × NMP losing 6/12 → 9/12 with NMP alone
    # at depth 5. The chess-style logarithmic LMR table is too aggressive
    # at the depths we run (4-6) in pure Python; keeping it off by default
    # avoids catastrophic interactions in narrow draughts endgames.
    # Add it back per-engine via ``features={'nmp', 'aspiration', 'rfutility', 'lmr'}``.
    DEFAULT_FEATURES: frozenset = frozenset(
        {"nmp", "aspiration", "rfutility"}
    )

    def __init__(
        self,
        depth_limit: int = 6,
        time_limit: Optional[float] = None,
        name: Optional[str] = None,
        eval_params: Optional[dict] = None,
        features: Optional[set] = None,
    ):
        self.depth_limit = depth_limit
        self.time_limit = time_limit
        self.name = name or self.__class__.__name__

        # Eval parameters (Tier 2.2: tunable via Texel-style fitting)
        self.eval_params: dict = {**self.DEFAULT_EVAL_PARAMS, **(eval_params or {})}
        self.features: frozenset = frozenset(
            self.DEFAULT_FEATURES if features is None else features
        )

        self.nodes: int = 0

        # Two-bucket TT
        self._tt_size = TT_BUCKETS
        self._tt_mask = TT_BUCKETS - 1
        self._tt_dp: list[Optional[tuple]] = [None] * TT_BUCKETS
        self._tt_ar: list[Optional[tuple]] = [None] * TT_BUCKETS
        self._tt_gen = 0  # incremented at the start of each search

        # History / killers
        self.history: dict[tuple, int] = {}
        self.killers: dict[int, list[Move]] = {}

        # Zobrist tables — keyed by ``(GAME_TYPE, num_squares)``
        # so that 50-square Standard and Frisian get different keys.
        self._zobrist_tables: dict[tuple, tuple[list, list]] = {}
        self._zobrist_turn = random.Random("draughts:turn").getrandbits(64)

        # PST cache
        self._pst_cache: dict[tuple[int, int], tuple] = {}

        # Per-search bound state
        self._current_zobrist: tuple[list, list] = self._make_zobrist(20, 50)
        self._current_pst = self._get_pst_tables(50, 10)

        self.start_time: float = 0.0
        self.stop_search: bool = False

        # LMR table (depth × move_index)
        self._lmr_table = self._build_lmr_table(64, 64)

    # ------------------------------------------------------------------
    # Public API expected by older tests
    # ------------------------------------------------------------------

    @property
    def inspected_nodes(self) -> int:
        return self.nodes

    @inspected_nodes.setter
    def inspected_nodes(self, value: int) -> None:
        self.nodes = value

    @property
    def tt(self) -> dict:
        """
        Dict-like view of the transposition table for backwards compatibility.

        Each accessible key returns a ``(depth, flag, score, move)`` tuple
        (the legacy 4-tuple); the new entries also carry ``key`` and
        ``generation`` fields internally.
        """
        return _TTView(self)

    # ------------------------------------------------------------------
    # Zobrist
    # ------------------------------------------------------------------

    @staticmethod
    def _make_zobrist(game_type: int, num_squares: int) -> tuple[list, list]:
        """
        Build a Zobrist table for a ``(GAME_TYPE, num_squares)`` pair.

        Two variants with the same square count (e.g. Standard and Frisian)
        get distinct tables because the seed depends on ``GAME_TYPE``.
        """
        seed = f"draughts:{game_type}:{num_squares}"
        rng = random.Random(seed)
        piece = [[rng.getrandbits(64) for _ in range(5)] for _ in range(num_squares)]
        halfmove = [rng.getrandbits(64) for _ in range(HALFMOVE_CAP)]
        return piece, halfmove

    def _get_zobrist_table(self, board: BaseBoard) -> tuple[list, list]:
        key = (board.GAME_TYPE, board.SQUARES_COUNT)
        table = self._zobrist_tables.get(key)
        if table is None:
            table = self._make_zobrist(board.GAME_TYPE, board.SQUARES_COUNT)
            self._zobrist_tables[key] = table
        return table

    def _get_pst_tables(self, num_squares: int, rows: int) -> tuple:
        key = (num_squares, rows)
        cache = self._pst_cache.get(key)
        if cache is None:
            pmb = _create_pst_man(num_squares, rows)
            pmw = pmb[::-1].copy()
            pkb = _create_pst_king(num_squares, rows)
            pkw = pkb[::-1].copy()
            cache = (pmb, pmw, pkb, pkw)
            self._pst_cache[key] = cache
        return cache

    @staticmethod
    def _piece_idx(piece: int) -> int:
        return piece + 2

    def _compute_hash_fast(self, board: BaseBoard) -> int:
        """Compute Zobrist hash using cached current zobrist tables."""
        pt, ht = self._current_zobrist
        h = 0
        pos = board._pos
        for i, piece in enumerate(pos):
            if piece != 0:
                h ^= pt[i][piece + 2]
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        h ^= ht[min(board.halfmove_clock, HALFMOVE_CAP - 1)]
        return h

    def compute_hash(self, board: BaseBoard) -> int:
        """Standalone Zobrist hash for a position."""
        pt, ht = self._get_zobrist_table(board)
        h = 0
        pos = board._pos
        for i, piece in enumerate(pos):
            if piece != 0:
                h ^= pt[i][piece + 2]
        if board.turn == Color.BLACK:
            h ^= self._zobrist_turn
        h ^= ht[min(board.halfmove_clock, HALFMOVE_CAP - 1)]
        return h

    def _update_hash(self, h: int, board: BaseBoard, move: Move) -> int:
        """Incrementally update Zobrist hash for a single move (pre-push)."""
        pt, ht = self._current_zobrist

        # Out: old halfmove
        h ^= ht[min(board.halfmove_clock, HALFMOVE_CAP - 1)]

        start_sq = move.square_list[0]
        end_sq = move.square_list[-1]
        piece = board._pos[start_sq]

        # Out: source piece
        h ^= pt[start_sq][piece + 2]

        # Detect promotion robustly from board state (not relying on
        # ``move.is_promotion``, which is only set during ``board.push``).
        end_bit = 1 << end_sq
        is_promo = False
        if piece == -1 and (board.PROMO_WHITE & end_bit):
            is_promo = True
        elif piece == 1 and (board.PROMO_BLACK & end_bit):
            is_promo = True

        new_piece = piece if not is_promo else (2 if piece == 1 else -2)
        h ^= pt[end_sq][new_piece + 2]

        # Captures
        for cap_sq in move.captured_list:
            cap_piece = board._pos[cap_sq]
            h ^= pt[cap_sq][cap_piece + 2]

        # In: new halfmove (kings not capturing increments; everything else resets)
        if abs(piece) == 2 and not move.captured_list:
            new_hm = board.halfmove_clock + 1
        else:
            new_hm = 0
        h ^= ht[min(new_hm, HALFMOVE_CAP - 1)]

        # Switch turn
        h ^= self._zobrist_turn
        return h

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, board: BaseBoard) -> float:
        """
        Static evaluation from the side-to-move's perspective.

        Material (king=3.0) + piece-square tables + tempo + back-rank.
        Parameters are pulled from ``self.eval_params`` so they can be
        Texel-tuned (see ``tools/tune_eval.py``).
        """
        pos = board._pos
        pmb, pmw, pkb, pkw = self._current_pst
        p = self.eval_params

        white_men = (pos == -1)
        white_kings = (pos == -2)
        black_men = (pos == 1)
        black_kings = (pos == 2)

        n_wm = int(white_men.sum())
        n_wk = int(white_kings.sum())
        n_bm = int(black_men.sum())
        n_bk = int(black_kings.sum())

        # Material from black's perspective (will flip below).
        score = (n_bm - n_wm) * p["man_value"]
        score += (n_bk - n_wk) * p["king_value"]

        # PST
        score += pmb[black_men].sum()
        score -= pmw[white_men].sum()
        score += pkb[black_kings].sum()
        score -= pkw[white_kings].sum()

        # Back-rank bonus — only meaningful while pieces are still developing.
        total = n_wm + n_wk + n_bm + n_bk
        if total >= 14:
            n_squares = board.SQUARES_COUNT
            rows = board.shape[0]
            cols = n_squares // rows
            bbr = int(black_men[:cols].sum())
            wbr = int(white_men[n_squares - cols:].sum())
            score += bbr * p["back_rank_bonus"]
            score -= wbr * p["back_rank_bonus"]

        # Flip to side-to-move
        score = -score if board.turn == Color.WHITE else score
        # Tempo
        score += p["tempo"]
        return float(score)

    # ------------------------------------------------------------------
    # Search entry point
    # ------------------------------------------------------------------

    def get_best_move(
        self, board: BaseBoard, with_evaluation: bool = False
    ) -> Move | tuple[Move, float]:
        """
        Find the best move. Uses iterative deepening with aspiration windows.
        """
        self.start_time = time.time()
        self.nodes = 0
        self.stop_search = False
        self._tt_gen = (self._tt_gen + 1) & 0xFF

        num_squares = len(board._pos)
        self._current_zobrist = self._get_zobrist_table(board)
        rows = board.shape[0]
        self._current_pst = self._get_pst_tables(num_squares, rows)

        # Decay history each search
        for k in self.history:
            self.history[k] //= 2

        # Reset killers per search to avoid stale entries influencing ordering
        self.killers.clear()

        root_hash = self._compute_hash_fast(board)
        max_depth = self.depth_limit or 6

        best_move: Optional[Move] = None
        best_score = -INF
        prev_score = 0.0

        for d in range(1, max_depth + 1):
            score = self._aspiration_search(board, d, prev_score, root_hash)
            # Don't trust results from a search that was cut off mid-flight.
            if self.stop_search:
                break

            entry = self._tt_probe(root_hash)
            if entry is not None:
                tt_move = entry[4]
                if tt_move is not None:
                    best_move = tt_move
                    best_score = score
                    prev_score = score

            if self.time_limit and (time.time() - self.start_time > self.time_limit):
                break

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("No legal moves available")
        if best_move is None:
            best_move = legal_moves[0]
            best_score = self.evaluate(board)

        logger.info(f"Best move: {best_move}, Score: {best_score:.2f}, Nodes: {self.nodes}")

        if with_evaluation:
            return best_move, float(best_score)
        return best_move

    def _aspiration_search(
        self, board: BaseBoard, depth: int, prev_score: float, root_hash: int
    ) -> float:
        """Aspiration-window iterative deepening. Falls back to full window."""
        if depth < 3 or "aspiration" not in self.features:
            return self.negamax(board, depth, -INF, INF, root_hash, 0)

        delta = 0.5  # half a man
        alpha = prev_score - delta
        beta = prev_score + delta
        while True:
            score = self.negamax(board, depth, alpha, beta, root_hash, 0)
            if self.stop_search:
                return score
            if score <= alpha:
                alpha -= delta
                delta *= 2
            elif score >= beta:
                beta += delta
                delta *= 2
            else:
                return score
            if delta > INF / 4:
                # Safety: fall back to full window once
                return self.negamax(board, depth, -INF, INF, root_hash, 0)

    # ------------------------------------------------------------------
    # Negamax
    # ------------------------------------------------------------------

    def negamax(
        self,
        board: BaseBoard,
        depth: int,
        alpha: float,
        beta: float,
        h: int,
        ply: int = 0,
    ) -> float:
        """Negamax search with alpha-beta pruning and friends."""
        self.nodes += 1

        # Time check (cheap)
        if self.nodes & 2047 == 0:
            if self.time_limit and (time.time() - self.start_time > self.time_limit):
                self.stop_search = True
        if self.stop_search:
            return alpha

        # In a PV node, beta - alpha > 1 (full window). Used to gate NMP/futility.
        in_pv = (beta - alpha) > 1.0001

        # ---- TT probe ----
        tt_entry = self._tt_probe(h)
        tt_move: Optional[Move] = None
        if tt_entry is not None:
            _key, tt_depth, tt_flag, tt_score, tt_move, _gen = tt_entry
            if tt_depth >= depth and not in_pv:
                if tt_flag == EXACT:
                    return tt_score
                if tt_flag == LOWER and tt_score >= beta:
                    return tt_score
                if tt_flag == UPPER and tt_score <= alpha:
                    return tt_score

        # ---- Leaf ----
        if depth <= 0:
            return self.quiescence_search(board, alpha, beta, h)

        # ---- Generate legal moves once ----
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            # No legal moves = loss. Prefer faster mates.
            return -CHECKMATE + ply

        if board.is_draw:
            return 0.0

        has_capture = any(m.captured_list for m in legal_moves)

        # Static eval used by RFP/NMP. Compute lazily.
        static_eval: Optional[float] = None

        # ---- Reverse futility (static null move) ----
        # If our static eval is so high above beta that even a big drop
        # still beats beta, return the optimistic score.
        if (
            "rfutility" in self.features
            and depth <= 3
            and not in_pv
            and not has_capture
            and abs(beta) < CHECKMATE - 100
        ):
            static_eval = self.evaluate(board)
            margin = depth * RFUT_MARGIN * MAN_VALUE
            if static_eval - margin >= beta:
                return static_eval - margin

        # ---- Null-move pruning ----
        # Disabled when a capture is forced (analogous to "in check" in chess),
        # in PV nodes, near the leaves, or when the side-to-move has very
        # few pieces (zugzwang risk).
        own_pieces = self._side_piece_count(board)
        if (
            "nmp" in self.features
            and depth >= NMP_MIN_DEPTH
            and not in_pv
            and not has_capture
            and own_pieces >= NMP_MIN_OWN_PIECES
            and ply > 0
        ):
            if static_eval is None:
                static_eval = self.evaluate(board)
            if static_eval >= beta:
                # Make null move (just flip turn; halfmove clock unchanged)
                original_turn = board.turn
                board.turn = Color.BLACK if original_turn == Color.WHITE else Color.WHITE
                null_hash = h ^ self._zobrist_turn
                null_score = -self.negamax(
                    board,
                    depth - 1 - NMP_REDUCTION,
                    -beta,
                    -beta + 1,
                    null_hash,
                    ply + 1,
                )
                board.turn = original_turn
                if self.stop_search:
                    return alpha
                if null_score >= beta:
                    # Verification search at higher depths to avoid zugzwang
                    # blunders (no piece can pass without changing the eval).
                    if depth >= NMP_VERIFY_DEPTH:
                        verify = self.negamax(
                            board,
                            depth - NMP_REDUCTION,
                            beta - 1,
                            beta,
                            h,
                            ply + 1,
                        )
                        if self.stop_search:
                            return alpha
                        if verify < beta:
                            null_score = verify  # don't trust the cutoff
                    if null_score >= beta:
                        return null_score

        # ---- Internal Iterative Deepening ----
        if depth >= IID_DEPTH and tt_move is None:
            self.negamax(board, depth - 2, alpha, beta, h, ply + 1)
            if self.stop_search:
                return alpha
            iid_entry = self._tt_probe(h)
            if iid_entry is not None:
                tt_move = iid_entry[4]

        # ---- Move ordering ----
        legal_moves = self._order_moves(legal_moves, tt_move, depth)

        best_value = -INF
        best_move: Optional[Move] = None
        flag = UPPER
        original_alpha = alpha

        for i, move in enumerate(legal_moves):
            new_hash = self._update_hash(h, board, move)
            board.push(move)

            if i == 0:
                val = -self.negamax(board, depth - 1, -beta, -alpha, new_hash, ply + 1)
            else:
                # LMR
                reduction = 0
                if (
                    "lmr" in self.features
                    and depth >= 3
                    and i >= 2
                    and not move.captured_list
                    and not in_pv
                ):
                    reduction = self._lmr(depth, i)
                # Null-window search
                val = -self.negamax(
                    board, depth - 1 - reduction, -alpha - 1, -alpha, new_hash, ply + 1
                )
                # Re-search if surprise
                if val > alpha and (reduction > 0 or val < beta):
                    val = -self.negamax(
                        board, depth - 1, -beta, -alpha, new_hash, ply + 1
                    )

            board.pop()

            # Cut off mid-search? Don't trust val.
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
                    self._update_killers(move, depth)
                self._update_history(move, depth)
                break

        # ---- TT store (only when search is intact) ----
        if not self.stop_search:
            self._tt_store(h, depth, flag, best_value, best_move)

        return best_value

    # ------------------------------------------------------------------
    # Quiescence
    # ------------------------------------------------------------------

    def quiescence_search(
        self,
        board: BaseBoard,
        alpha: float,
        beta: float,
        h: int,
        qs_depth: int = 0,
    ) -> float:
        """Capture-only search to dampen the horizon effect."""
        self.nodes += 1
        if self.nodes & 2047 == 0:
            if self.time_limit and (time.time() - self.start_time > self.time_limit):
                self.stop_search = True
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

        captures = self._order_captures(captures)
        for move in captures:
            new_hash = self._update_hash(h, board, move)
            board.push(move)
            score = -self.quiescence_search(board, -beta, -alpha, new_hash, qs_depth + 1)
            board.pop()
            if self.stop_search:
                return alpha
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
        tt_move: Optional[Move] = None,
        depth: int = 0,
    ) -> List[Move]:
        killers = self.killers.get(depth, ())

        def score_move(m: Move) -> float:
            if tt_move is not None and m == tt_move:
                return 1e9
            if m.captured_list:
                # MVV-style: total captured material × 1e4 + count
                return 1e5 + m.capture_value * 1e4 + len(m.captured_list)
            if m in killers:
                return 9e4
            start = m.square_list[0]
            end = m.square_list[-1]
            promo = 1 if m.is_promotion else 0
            return self.history.get((start, end, promo), 0)

        moves.sort(key=score_move, reverse=True)
        return moves

    @staticmethod
    def _order_captures(moves: List[Move]) -> List[Move]:
        """Sort captures by material value first, count as tiebreak."""
        moves.sort(
            key=lambda m: (m.capture_value, len(m.captured_list)),
            reverse=True,
        )
        return moves

    def _update_killers(self, move: Move, depth: int) -> None:
        bucket = self.killers.setdefault(depth, [])
        if move in bucket:
            return
        bucket.insert(0, move)
        del bucket[2:]

    def _update_history(self, move: Move, depth: int) -> None:
        key = (move.square_list[0], move.square_list[-1], 1 if move.is_promotion else 0)
        self.history[key] = self.history.get(key, 0) + depth * depth

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _side_piece_count(board: BaseBoard) -> int:
        """Pieces of the side to move (used to gate NMP for zugzwang risk)."""
        if board.turn == Color.WHITE:
            return board._popcount(board.white_men) + board._popcount(board.white_kings)
        return board._popcount(board.black_men) + board._popcount(board.black_kings)

    @staticmethod
    def _build_lmr_table(max_depth: int, max_moves: int) -> list[list[int]]:
        """
        Tuned LMR reductions, capped at 1 ply.

        The classic chess formula ``0.75 + ln(d)·ln(i)/2.25`` reduces by 2-3
        plies in the late move list. In draughts at the depths we typically
        run (4-6) that compounds with NMP's R=2 and creates blind spots —
        ablation on Frisian showed NMP × deep-LMR loses 90% of games. We
        cap at 1 to keep search stable; deeper engines can raise the cap.
        """
        table = [[0] * max_moves for _ in range(max_depth)]
        for d in range(1, max_depth):
            for i in range(1, max_moves):
                r = 0.75 + math.log(d) * math.log(i) / 2.25
                table[d][i] = min(1, max(0, int(r)))
        return table

    def _lmr(self, depth: int, move_index: int) -> int:
        d = min(depth, len(self._lmr_table) - 1)
        i = min(move_index, len(self._lmr_table[0]) - 1)
        return self._lmr_table[d][i]

    # ------------------------------------------------------------------
    # Transposition table
    # ------------------------------------------------------------------

    def _tt_probe(self, key: int) -> Optional[tuple]:
        idx = key & self._tt_mask
        e = self._tt_dp[idx]
        if e is not None and e[0] == key:
            return e
        e = self._tt_ar[idx]
        if e is not None and e[0] == key:
            return e
        return None

    def _tt_store(
        self,
        key: int,
        depth: int,
        flag: int,
        score: float,
        move: Optional[Move],
    ) -> None:
        idx = key & self._tt_mask
        new_entry = (key, depth, flag, score, move, self._tt_gen)
        dp = self._tt_dp[idx]
        # Depth-preferred: replace if empty, same key, deeper, or aged out.
        if (
            dp is None
            or dp[0] == key
            or dp[5] != self._tt_gen
            or dp[1] <= depth
        ):
            self._tt_dp[idx] = new_entry
        else:
            self._tt_ar[idx] = new_entry


# ---------------------------------------------------------------------------
# Backwards-compatible TT view
# ---------------------------------------------------------------------------


class _TTView:
    """
    Minimal dict-like view exposing the modern TT through the legacy
    ``engine.tt[hash] -> (depth, flag, score, move)`` API.
    """

    __slots__ = ("_engine",)

    def __init__(self, engine: AlphaBetaEngine):
        self._engine = engine

    def get(self, key: int, default=None):
        e = self._engine._tt_probe(key)
        if e is None:
            return default
        return (e[1], e[2], e[3], e[4])

    def __getitem__(self, key: int):
        v = self.get(key)
        if v is None:
            raise KeyError(key)
        return v

    def __contains__(self, key: int) -> bool:
        return self._engine._tt_probe(key) is not None

    def __len__(self) -> int:
        n = 0
        for arr in (self._engine._tt_dp, self._engine._tt_ar):
            for e in arr:
                if e is not None:
                    n += 1
        return n
