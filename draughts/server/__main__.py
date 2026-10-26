"""Start the web UI: ``draughts-server`` or ``python -m draughts.server``."""

import argparse

from draughts import SimpleEngine, StandardBoard
from draughts.server.server import Server


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the py-draughts web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--depth", type=int, default=6, help="SimpleEngine search depth")
    args = parser.parse_args()
    print(f"py-draughts UI: http://{args.host}:{args.port}")
    Server(
        board=StandardBoard(),
        white_engine=SimpleEngine(depth_limit=args.depth),
        black_engine=SimpleEngine(depth_limit=args.depth),
    ).run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
