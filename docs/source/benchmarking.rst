Benchmarking (Internal)
=======================

This page documents the internal benchmarking tools used for performance testing py-draughts.

Overview
--------

The benchmarking system compares performance between different versions of py-draughts by:

1. Creating snapshots (wheel files) of the current version
2. Running benchmarks comparing a snapshot against the current source code

Workflow
--------

1. **Create a Snapshot**

   First, create a snapshot of the version you want to use as baseline:

   .. code-block:: bash

      python tools/create_snapshot.py

   This will:
   
   - Build a wheel file from the current source
   - Save it to ``snapshots/snapshot_YYYYMMDD_HHMMSS/``
   - Store metadata (git commit, timestamp) in ``metadata.json``

2. **Compare Versions**

   Then compare the snapshot against your current (modified) source:

   .. code-block:: bash

      # Compare latest snapshot vs current source
      python tools/compare_versions.py

      # Compare specific snapshot vs current source  
      python tools/compare_versions.py snapshots/snapshot_20251231_125057

   The comparison runs:
   
   - **Legal moves benchmark**: Measures time to generate legal moves from various positions
   - **Engine match**: Plays games between engines to compare move quality and speed

Configuration
-------------

The benchmark configuration is defined at the top of ``tools/compare_versions.py``:

.. code-block:: python

   WARMUP_ROUNDS = 5
   BENCHMARK_ROUNDS = 10
   BENCHMARK_ITERATIONS = 10
   ENGINE_DEPTH = 2
   NUM_GAMES = 20

Results
-------

Benchmark results are automatically appended to ``benchmark_results.csv`` in the project root.

Profiling
---------

For detailed profiling of specific functions, use:

.. code-block:: bash

   python tools/profile_engine.py

Or for more detailed analysis:

.. code-block:: bash

   python tools/profile_engine_detailed.py 5  # depth 5

This uses Python's ``cProfile`` to identify bottlenecks in the engine.
