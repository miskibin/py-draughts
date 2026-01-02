from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from draughts import get_board
from draughts.engine import AlphaBetaEngine
from draughts.server.server import Server


def _new_test_app():
    app = FastAPI(title="py-draughts test")
    app.mount("/static", StaticFiles(directory=Server.static_dir), name="static")
    return app


def test_position_and_move_and_pop_smoke():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        board = get_board("standard")
        server = Server(board=board)
        client = TestClient(server.APP)

        r = client.get("/position")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"position", "history", "turn"}
        assert body["turn"] in {"white", "black"}
        assert body["history"] == []

        move = next(m for m in list(board.legal_moves) if "-" in str(m))
        src, dst = str(move).split("-")

        r = client.post(f"/move/{src}/{dst}")
        assert r.status_code == 200
        assert r.json()["history"] != []

        r = client.get("/pop")
        assert r.status_code == 200
        assert r.json()["history"] == []
    finally:
        Server.APP = old_app


def test_load_fen_resets_state():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        board = get_board("standard")
        starting_fen = board.fen

        server = Server(board=board)
        client = TestClient(server.APP)

        move = next(m for m in list(board.legal_moves) if "-" in str(m))
        src, dst = str(move).split("-")
        client.post(f"/move/{src}/{dst}")
        assert client.get("/position").json()["history"] != []

        r = client.post("/load_fen", json={"fen": starting_fen})
        assert r.status_code == 200
        assert r.json()["history"] == []
        assert server.board.fen == starting_fen
    finally:
        Server.APP = old_app


def test_set_depth_clamps_and_updates_engine():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        board = get_board("standard")
        engine = AlphaBetaEngine(depth=6)
        server = Server(
            board=board, get_best_move_method=engine.get_best_move, engine=engine
        )
        client = TestClient(server.APP)

        r = client.get("/set_depth/0")
        assert r.status_code == 200
        assert r.json()["depth"] == 1
        assert engine.depth == 1

        r = client.get("/set_depth/999")
        assert r.status_code == 200
        assert r.json()["depth"] == 10
        assert engine.depth == 10
    finally:
        Server.APP = old_app
