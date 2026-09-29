from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient

from draughts.engines import Engine, SimpleEngine
from draughts.move import Move
from draughts.server.server import Server
from test._test_helpers import get_board


class _SlowStaleEngine(Engine):
    """Engine stub that always returns the same *initial* move after a delay.

    This simulates autoplay overlap: a long search returns a move that was legal
    when the request started, but is no longer legal when it is applied.
    """

    def __init__(self, stale_move, delay_s: float = 0.15):
        import time

        self._stale_move = stale_move
        self._delay_s = delay_s
        self._time = time

    def get_best_move(self, _board, with_evaluation=False):
        self._time.sleep(self._delay_s)
        if with_evaluation:
            return self._stale_move, 0.0
        return self._stale_move


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
        assert set(body.keys()) == {"position", "history", "turn", "game_over", "result"}
        assert body["turn"] in {"white", "black"}
        assert body["history"] == []
        assert isinstance(body["game_over"], bool)
        assert isinstance(body["result"], str)

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


def test_goto_ply_pops_history():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        board = get_board("standard")
        server = Server(board=board)
        client = TestClient(server.APP)

        # Play 2 half-moves (if possible)
        m1 = list(board.legal_moves)[0]
        board.push(m1)
        m2_list = list(board.legal_moves)
        if m2_list:
            board.push(m2_list[0])

        assert len(server.board._moves_stack) in {1, 2}

        # Jump back to after first ply
        r = client.get("/goto/1")
        assert r.status_code == 200
        assert len(server.board._moves_stack) == 1

        # Jump back to start
        r = client.get("/goto/0")
        assert r.status_code == 200
        assert len(server.board._moves_stack) == 0

        # The move list can navigate forward again without losing the game.
        r = client.get("/goto/2")
        assert r.status_code == 200
        assert len(server.board._moves_stack) == 2
    finally:
        Server.APP = old_app


def test_refined_ui_and_variant_switch():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        server = Server(board=get_board("standard"))
        client = TestClient(server.APP)

        page = client.get("/")
        assert page.status_code == 200
        assert 'id="board"' in page.text
        assert 'id="server-config"' in page.text
        assert 'data-dialog="import"' in page.text
        assert 'data-dialog="api"' in page.text
        assert client.get("/static/css/style.css").status_code == 200
        assert client.get("/static/js/script.js").status_code == 200

        response = client.get("/set_board/brazilian", follow_redirects=True)
        assert response.status_code == 200
        assert '"variant": "brazilian"' in response.text
        assert len(server.board.friendly_form) == 64

        for variant in (
            "standard", "american", "frisian", "russian", "brazilian",
            "antidraughts", "breakthrough", "frysk",
        ):
            response = client.get(f"/set_board/{variant}", follow_redirects=True)
            assert response.status_code == 200
            assert f'"variant": "{variant}"' in response.text
            assert len(server.board.friendly_form) in (64, 100)
    finally:
        Server.APP = old_app


def test_new_move_after_navigation_discards_redo():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        server = Server(board=get_board("standard"))
        client = TestClient(server.APP)
        first = list(server.board.legal_moves)[0]
        server.board.push(first)
        second = list(server.board.legal_moves)[0]
        server.board.push(second)

        client.get("/goto/1")
        alternative = next(m for m in server.board.legal_moves if m != second)
        src, dst = str(alternative).split("-")
        assert client.post(f"/move/{src}/{dst}").status_code == 200
        assert client.get("/goto/3").json()["history"][-1][-1] == str(alternative)
        assert len(server.board._moves_stack) == 2
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
        engine = SimpleEngine(depth_limit=6)
        server = Server(board=board, white_engine=engine, black_engine=engine)
        client = TestClient(server.APP)

        r = client.get("/set_depth/0")
        assert r.status_code == 200
        assert r.json()["depth"] == 1
        assert engine.depth_limit == 1

        r = client.get("/set_depth/999")
        assert r.status_code == 200
        assert r.json()["depth"] == 10
        assert engine.depth_limit == 10
    finally:
        Server.APP = old_app


def test_overlapping_best_move_requests_do_not_corrupt_board():
    """Regression for autoplay at high depth.

    Without serialization/validation, overlapping /best_move calls can apply stale
    moves to a mutated board, effectively randomizing the position.
    """
    import threading

    old_app = Server.APP
    try:
        Server.APP = _new_test_app()

        board = get_board("standard")
        # Pick a deterministic legal move from the initial position.
        stale_move = list(board.legal_moves)[0]

        engine = _SlowStaleEngine(stale_move=stale_move, delay_s=0.15)
        server = Server(board=board, white_engine=engine, black_engine=engine)
        client = TestClient(server.APP)

        barrier = threading.Barrier(3)
        results = []

        def worker():
            barrier.wait()
            r = client.get("/best_move")
            results.append(r)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        barrier.wait()
        t1.join()
        t2.join()

        assert len(results) == 2
        assert all(r.status_code == 200 for r in results)

        # With serialization + legality checks, both requests may advance the game,
        # but the original stale move should not be applied twice.
        played = list(server.board._moves_stack)
        assert len(played) == 2
        assert sum(1 for m in played if str(m) == str(stale_move)) == 1

        # Replaying the stored move stack from the start should reproduce the same board.
        expected = get_board("standard")
        for m in played:
            assert m in list(expected.legal_moves)
            expected.push(m)
        assert server.board.fen == expected.fen
    finally:
        Server.APP = old_app


def test_best_move_falls_back_if_engine_returns_illegal_move():
    old_app = Server.APP
    try:
        Server.APP = _new_test_app()
        board = get_board("standard")

        class BadEngine(Engine):
            def get_best_move(self, _board, with_evaluation=False):
                # Definitely illegal: no-op move
                move = Move([0, 0])
                return (move, 0.0) if with_evaluation else move

        bad_engine = BadEngine()
        server = Server(board=board, white_engine=bad_engine, black_engine=bad_engine)
        client = TestClient(server.APP)

        r = client.get("/best_move")
        assert r.status_code == 200
        assert len(server.board._moves_stack) == 1
    finally:
        Server.APP = old_app
