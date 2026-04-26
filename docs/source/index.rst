:layout: landing

.. meta::
   :description: py-draughts — the fastest Python draughts / checkers library. Bitboard move generation ~200x faster than pydraughts. Built-in alpha-beta engine, HUB protocol, web UI, SVG rendering, ML tensors. 8 variants: International, American, Frisian, Russian, Brazilian, Antidraughts, Breakthrough, Frysk!.
   :keywords: python draughts, python checkers, draughts library, checkers library, pydraughts alternative, international draughts, frisian draughts, russian draughts, brazilian draughts, antidraughts, breakthrough, frysk, bitboard, pdn, fen, alpha-beta engine, hub protocol, board game ai

py-draughts
===========

.. raw:: html

   <div class="hero">
     <div class="hero-title">py&#8209;draughts</div>
     <p class="hero-subtitle">
       The fastest pure-Python <strong>draughts / checkers</strong> library —
       bitboard move generation ~200× faster than pydraughts. Built-in
       alpha-beta engine, HUB protocol bridge (Scan, Kingsrow), web UI,
       SVG rendering, and ML/RL helpers across 8 variants:
       International, American, Frisian, Russian, Brazilian, Antidraughts,
       Breakthrough, and Frysk!.
     </p>
     <div class="hero-badges">
       <a href="https://pypi.org/project/py-draughts/"><img alt="PyPI" src="https://badge.fury.io/py/py-draughts.svg"></a>
       <a href="https://pepy.tech/project/py-draughts"><img alt="Downloads" src="https://static.pepy.tech/badge/py-draughts"></a>
       <a href="https://github.com/miskibin/py-draughts"><img alt="GitHub" src="https://img.shields.io/github/stars/miskibin/py-draughts?style=social"></a>
     </div>
   </div>

.. grid:: 2
   :gutter: 3
   :margin: 0 0 3 0

   .. grid-item-card:: :octicon:`rocket;1em;sd-text-primary` Quick Start
      :link: core
      :link-type: doc

      Spin up a board, push moves, query legal moves, parse PDN/FEN.
      The 5-minute path to a working game.

   .. grid-item-card:: :octicon:`cpu;1em;sd-text-primary` Engine
      :link: engine
      :link-type: doc

      Built-in alpha-beta engine, Hub protocol bridge, and a clean
      ``Engine`` interface for plugging in your own.

   .. grid-item-card:: :octicon:`zap;1em;sd-text-primary` AI / RL
      :link: ai
      :link-type: doc

      Tensor representations, legal-move masks, MCTS skeleton, and a
      complete REINFORCE self-play example.

   .. grid-item-card:: :octicon:`device-desktop;1em;sd-text-primary` Web UI
      :link: server
      :link-type: doc

      Drop-in FastAPI server with a polished UI for play, analysis,
      and engine matches.

   .. grid-item-card:: :octicon:`paintbrush;1em;sd-text-primary` SVG Rendering
      :link: svg
      :link-type: doc

      Render boards and pieces with arrows, highlights, and full
      Jupyter notebook integration.

   .. grid-item-card:: :octicon:`graph;1em;sd-text-primary` Benchmarks
      :link: benchmarking
      :link-type: doc

      Performance numbers for legal-move generation and engine search,
      plus the tooling used to produce them.

   .. grid-item-card:: :octicon:`git-compare;1em;sd-text-primary` vs pydraughts
      :link: comparison
      :link-type: doc

      Side-by-side comparison: speed, variants, engine, web UI, ML support.
      Why py-draughts is ~200× faster.

Installation
------------

.. tab-set::

   .. tab-item:: pip

      .. code-block:: bash

         pip install py-draughts

   .. tab-item:: uv

      .. code-block:: bash

         uv add py-draughts

   .. tab-item:: poetry

      .. code-block:: bash

         poetry add py-draughts

Hello, draughts
---------------

.. code-block:: python

   from draughts import Board, AlphaBetaEngine

   board = Board()                       # 10x10 international draughts
   board.push_uci("31-27")
   board.push_uci("18-22")

   engine = AlphaBetaEngine(depth_limit=5)
   board.push(engine.get_best_move(board))

   print(board)

Variants
--------

.. list-table::
   :header-rows: 1
   :widths: 22 12 16 50

   * - Class
     - Size
     - Flying kings
     - Notes
   * - :class:`draughts.StandardBoard`
     - 10×10
     - Yes
     - International draughts / FMJD (alias: :class:`draughts.Board`)
   * - :class:`draughts.AmericanBoard`
     - 8×8
     - No
     - English checkers
   * - :class:`draughts.FrisianBoard`
     - 10×10
     - Yes
     - Diagonal + orthogonal captures
   * - :class:`draughts.RussianBoard`
     - 8×8
     - Yes
     - Mid-capture promotion
   * - :class:`draughts.BrazilianBoard`
     - 8×8
     - Yes
     - International rules on 8×8
   * - :class:`draughts.AntidraughtsBoard`
     - 10×10
     - Yes
     - Lose all pieces (or get blocked) to win
   * - :class:`draughts.BreakthroughBoard`
     - 10×10
     - Yes
     - First player to make a king wins
   * - :class:`draughts.FryskBoard`
     - 10×10
     - Yes
     - Frisian rules with 5 men per side

.. toctree::
   :hidden:
   :caption: Guide

   core
   engine
   ai
   svg
   server

.. toctree::
   :hidden:
   :caption: Reference

   benchmarking
   comparison
