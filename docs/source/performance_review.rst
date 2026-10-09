October 2026 performance and engine review
==========================================

This review compares the repository baseline ``b8c867f6`` with the reviewed
engine in ``7e73ad7``. The shipped trained weights were not retrained or changed.
The scope is board operations, international search, draw adjudication and
benchmark correctness; this is not a claim that every possible library bug
has been eliminated.

Performance
-----------

Measured with CPython 3.12.14 on an AMD EPYC 9V74 runner. Each number is the
median of nine repetitions over eleven fixed positions, with 2,000 loops per
repetition. Imports/setup are excluded; baseline and candidate runs were
sequential, before the parallel strength tournament. These are local benchmark
results, not universal hardware-independent speed claims.

.. list-table:: Median microseconds per operation
   :header-rows: 1

   * - Operation
     - Before
     - After
     - Speedup
   * - FEN parsing
     - 25.474
     - 14.356
     - 1.77x
   * - Public legal moves
     - 9.215
     - 7.145
     - 1.29x
   * - Push + pop
     - 1.618
     - 1.256
     - 1.29x
   * - Board features
     - 11.108
     - 8.822
     - 1.26x
   * - Static evaluation
     - 4.062
     - 2.119
     - 1.92x
   * - Internal capture generation
     - 3.825
     - 1.858
     - 2.06x

The complete depth-six search workload is deliberately also reported:
**0.594 s / 74,428 nodes before**, versus **0.628 s / 91,946 nodes after**.
That is about **5.8% more elapsed time**, **23.5% more nodes**, and
**16.7% higher node throughput** (125,369 to 146,348 nodes/s).
The search semantics changed: corrected terminal/draw handling, safe
transposition depth/context and move ordering produce different trees. A
fixed-depth stopwatch alone therefore does not establish playing strength.

The baseline cProfile run identified static evaluation and flying-king ray
scanning as major hot spots. Material/PST values are now folded into the
existing pattern tables exactly, king capture scans use ray masks, FEN parsing
builds bitboards directly, and undo touches only the affected bitboards.
Static scores are cached separately from context-dependent search bounds.
Raw repetitions and the top thirty profile rows are retained in
``benchmarks/review-2026-10-08/before.json`` and ``after.json``.

Correctness changes
-------------------

* Repetition compares complete positions and the side to move, includes the
  starting position, and handles cycles longer than four plies. It no longer
  infers a draw merely because one player repeated the same move.
* International five/sixteen-move endings use the correct material conditions.
  Those clocks survive man moves and captures; a terminal win on the final
  allowed ply takes precedence. Copies retain the endgame counters while, as
  before, ``copy()`` intentionally starts with an empty move history.
* A blocked or empty side is recognized as lost at a quiescence leaf.
  Requesting an evaluation of a forced move searches its consequences.
* Threat extensions retain the draw clocks. Transposition entries include
  clock/repetition context, normalize mate distance for the current ply, and
  store the requested search depth before a forced-reply extension.
* Timeout handling accepts only exact partial root results and resets them on
  every aspiration retry. Fail-high/low bounds are not compared as exact scores.
* TurboEngine rejects incompatible variants and invalid budgets. Move ordering
  adds two killers per ply and separate history tables for White and Black.
* Quiet moves no longer share mutable capture lists. Malformed trailing text
  in a black-piece FEN list is rejected instead of silently discarded. Explicit
  capture paths must match the order/length; endpoint abbreviations still work.
* The benchmark respects variant-specific results and wins on its final ply,
  accounts for Black-to-move openings, reports illegal moves as explicit errors,
  accepts both raw and wrapped opening FENs, and reports neutral Elo for an empty result set.

Draw rules were checked against `FMJD Annex 1, articles 6 and 7
<https://www.fmjd.org/docs/Annex_1.pdf>`_. Tests cover the relevant material,
history, capture, promotion, copy and undo cases; they are not a formal proof
of every reachable game state.

Strength experiment
-------------------

The final experiment uses **300 distinct openings / 600 games**, each opening
played with colours reversed. Openings are generated from legal starting
positions using seed **20261009**, with 4--12 random plies and equal material;
they are distinct from the development seed **73017**. Both engines receive
**0.1 seconds per move**, with six workers, fresh engine instances per game,
and a 300-ply maximum. Both use the corrected current board as referee.
An engine exception or illegal move aborts the run instead of becoming a win.

The frozen baseline checks its deadline every 2,048 nodes and can overrun the
budget more than the candidate, which checks every 128 nodes. Actual time
consumption is retained in the result file. This remaining asymmetry favours
the baseline; neither implementation is a hard real-time process.

The candidate scored **239 wins, 230 draws and 131 losses**,
for **59.0%** of the points. Its estimated gain is **+63.2
relative Elo**, with an approximate **95% interval of
+40.7 to +86.3**. The interval excludes zero.

Three games reached the 300-ply cap and were scored as draws; the other
597 finished under the board rules. Scoring all three capped games as
candidate losses or all three as candidate wins changes the point estimate
only to +61.4 / +65.0 Elo, respectively.

Actual engine time summed to **3211.5 s for the candidate** and
**3471.3 s for the baseline**; the baseline used
8.1% more time. No engine errors or illegal
moves occurred. The full fixed-size tournament took 18.9
minutes of wall time.
Raw per-game moves, final FENs, time, node counts, source/weight SHA-256 hashes
and the aggregate result live in ``benchmarks/review-2026-10-08/holdout.json``.

Relative Elo is ``400 * log10(p / (1 - p))``, where ``p`` is wins plus half
the draws, divided by games. The approximate 95% interval resamples whole
opening pairs 20,000 times, keeping the two correlated colour games together.
This is strength relative to this baseline at this time control and opening
distribution, **not an absolute FMJD, online, or human-player rating**.
Small development matches guided implementation and are not included in the
final confidence interval.

Validation and reproduction
---------------------------

* 607 tests passed; 9 existing Scan-oracle tests were skipped because the
  patched external binary is unavailable. There are 50 added regression cases.
* Ruff lint, Ruff formatting and mypy passed. Both wheel and sdist built; the
  wheel contains the new draw module and trained weights. The HTML docs built
  with sitemap generation disabled locally because its IPC socket is blocked
  in this runner.
* An additional exact comparison of 4,000 random mixed man/king positions
  against the frozen move core found zero differences, across International,
  Russian, Brazilian and American rules. This is a differential check, not
  an independent external rules oracle.

From a checkout of the reviewed branch::

    git worktree add --detach ../py-draughts-baseline b8c867f6ac047030bac693511f87ff3217ed58cf
    python -m pip install -e '.[dev]'
    python -m pytest test/ -q
    python -m ruff check .
    python -m ruff format --check .
    python -m mypy draughts --ignore-missing-imports
    python tools/review_performance.py --root ../py-draughts-baseline --out before.json
    python tools/review_performance.py --root . --out after.json
    python tools/compare_turbo.py --baseline ../py-draughts-baseline \
        --pairs 300 --time 0.1 --workers 6 --seed 20261009 --out holdout.json

Timed matches fluctuate with machine load and scheduling. Fixed-depth games
are also available with ``--depth 5`` in place of ``--time 0.1``, but they
answer a different resource-budget question.
