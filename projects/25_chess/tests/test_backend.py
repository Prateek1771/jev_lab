"""Project 25, offline: move tags and ordering, Jev's criteria are exactly the legal moves, repetition ends a game,
the LLM's reply is parsed safely, and each variant scores against the position's accepted moves. No keys, no spend."""

import importlib

import chess
from fastapi.testclient import TestClient

exp = importlib.import_module("projects.25_chess.experiment")
engine = importlib.import_module("projects.25_chess.engine")
api = importlib.import_module("api.main")


def board_after(*moves: str) -> chess.Board:
    b = chess.Board()
    for m in moves:
        b.push_uci(m)
    return b


def test_tags_mate_and_opening_moves():
    mate = chess.Board("6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1")
    assert "CHECKMATE" in engine.analyse(mate, chess.Move.from_uci("d1d8"))[0]
    assert engine.analyse(chess.Board(), chess.Move.from_uci("g1f3"))[0].startswith("Knight g1→f3 (Nf3)")


def test_jev_criteria_are_exactly_the_legal_moves():
    b = chess.Board()
    q = engine.jev_questions(b)
    assert set(q["move"]["criteria"]) == {m.uci() for m in b.legal_moves}
    assert [q[k]["type"] for k in ("move", "eval", "threat")] == ["choice", "score", "noul"]


def test_repetition_tags_need_history():
    b = board_after("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1")
    assert "UNDOES" in engine.analyse(b, chess.Move.from_uci("f6g8"))[0]
    assert "DRAW by threefold" in engine.analyse(b, chess.Move.from_uci("f6g8"))[0]


def test_tactics_ordering_puts_mate_first_and_flags_blunders():
    b = chess.Board("3r2k1/5ppp/8/8/8/8/R4PPP/6K1 w - - 0 1")   # black threatens Rd1#
    opts = engine.legal_options(b)
    assert "allows opponent CHECKMATE IN 1" in opts["a2b2"]
    queen = chess.Board("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
    first, desc = next(iter(engine.legal_options(queen).items()))
    assert first == "d1d5" and "SAFE capture of Queen" in desc


def test_parse_move_reads_json_then_falls_back_to_any_legal_uci():
    b = chess.Board()
    assert engine.parse_move('{"move": "e2e4", "reason": "center"}', b) == (chess.Move.from_uci("e2e4"), "center")
    assert engine.parse_move("I play e7e5 or maybe d2d4", b)[0] == chess.Move.from_uci("d2d4")
    assert engine.parse_move('{"move": "e2e5"}', b)[0] is None


def test_a_shuffling_game_ends_in_a_threefold_draw(monkeypatch):
    shuffle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    monkeypatch.setattr(engine, "get_move", lambda board, san, player: engine.heuristic_move(board) | {
        "uci": shuffle[len(san) % 4]})
    plies = list(exp.play("jev", "gpt-4.1-nano"))
    assert [p["side"] for p in plies[:3]] == ["white", "black", "white"]
    assert plies[-1]["result"].startswith("1/2-1/2") and "threefold" in plies[-1]["result"]
    assert all("request" in p and "response" in p for p in plies)


def _jev(choice):
    def fake(state, questions):
        assert set(questions["move"]["criteria"]) >= {choice}
        return {"model": "typesafe/jev-1.13-20260917", "usage": {"input_tokens": 300, "output_tokens": 3, "cost": 1e-5},
                "answers": {"move": {"choice": choice, "confidence": 0.9, "probabilities": {choice: 0.9}},
                            "eval": {"score": 3.2}, "threat": {"noul": 0.1}}}, 120.0
    return fake


def test_run_experiment_scores_each_variant(monkeypatch):
    monkeypatch.setattr(engine, "decide", _jev("d1d8"))
    monkeypatch.setattr(engine, "openai_chat", lambda model, messages: {
        "model": model, "usage": {"prompt_tokens": 1000, "completion_tokens": 40},
        "choices": [{"message": {"content": '{"move": "d1d2", "reason": "safe"}'}}]})
    r = exp.run_experiment(exp.EXAMPLES["Back-rank mate"])
    assert list(r.runs) == ["jev", "cheap_llm", "heuristic"]
    assert r.runs["jev"].label == "mate_in_1" and r.runs["jev"].raw["move"] == "Rd8#"
    assert r.runs["cheap_llm"].label == exp.MISS and r.runs["cheap_llm"].cost_usd == (1000 * 0.10 + 40 * 0.40) / 1e6
    assert r.runs["heuristic"].label == "mate_in_1" and r.runs["heuristic"].cost_usd == 0


def test_llm_falls_back_to_a_random_legal_move(monkeypatch):
    monkeypatch.setattr(engine, "openai_chat", lambda model, messages: {
        "usage": {}, "choices": [{"message": {"content": "no idea"}}]})
    rec = engine.llm_move(chess.Board(), [], "gpt-4.1-nano")
    assert rec["fallback"] and chess.Move.from_uci(rec["uci"]) in chess.Board().legal_moves


def test_play_route_streams_and_rejects_unknown_players(monkeypatch):
    client = TestClient(api.app)
    assert client.post("/api/projects/25/play", json={"white": "jev", "black": "gpt-99"}).status_code == 422
    assert client.post("/api/projects/01/play", json={"white": "jev", "black": "jev"}).status_code == 404
    monkeypatch.setattr(exp, "play", lambda w, b: iter([{"ply": 1, "san": "e4"}]))
    body = client.post("/api/projects/25/play", json={"white": "jev", "black": "gpt-4.1-nano"}).text
    assert body.index("event: start") < body.index('"san": "e4"') < body.index("event: end")


def test_openai_calls_go_only_to_openai_with_its_key(monkeypatch):
    import httpx
    import pytest
    seen = []
    def post(url, body, headers):
        seen.append((url, body["model"], headers["Authorization"]))
        return httpx.Response(429, json={"error": {"message": "You have no credits remaining."}})
    monkeypatch.setattr(engine, "_post", post)
    monkeypatch.setattr(engine.settings, "OPENAI_API_KEY", "sk-test")
    with pytest.raises(RuntimeError, match="OpenAI 429: You have no credits remaining"):
        engine.openai_chat("gpt-4.1-nano", [])
    assert seen == [(engine.OPENAI_URL, "gpt-4.1-nano", "Bearer sk-test")]   # no OpenRouter fallback
    monkeypatch.setattr(engine.settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is not set"):
        engine.openai_chat("gpt-4.1-nano", [])


def tags(fen: str, uci: str) -> tuple[str, int]:
    return engine.analyse(chess.Board(fen), chess.Move.from_uci(uci))


def test_decisive_tags_trades_threats_passed_pawns():
    # equal rook trade: worth more when ahead (here White is a queen up)
    even, ahead = tags("3rk3/8/8/8/8/8/8/3RK3 w - - 0 1", "d1d8"), tags("3rk3/8/8/8/8/8/8/Q2RK3 w - - 0 1", "d1d8")
    assert "EVEN TRADE" in even[0] and "you are ahead" in ahead[0] and ahead[1] > even[1]
    assert "THREATENS Rook f7" in tags("4k3/5r2/8/8/8/8/8/4KB2 w - - 0 1", "f1c4")[0]   # new: f1 did not hit f7
    assert "PASSED PAWN push (rank 6 of 8)" in tags("4k3/8/8/1P6/8/8/8/4K3 w - - 0 1", "b5b6")[0]
    assert "LOSING TRADE" in tags("4k3/8/4p3/3p4/8/8/8/3QK3 w - - 0 1", "d1d5")[0]


def test_a_won_game_is_never_drawn_away():
    # K+Q vs K: Qb6 stalemates; a repeat while ahead costs more than a quiet move
    stale, score = tags("k7/8/2Q5/8/8/8/8/4K3 w - - 0 1", "c6b6")
    assert "STALEMATE" in stale and score < -100
    assert engine.scored_moves(chess.Board("k7/8/2Q5/8/8/8/8/4K3 w - - 0 1"))[0][0] != "c6b6"
    b = board_after("g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1")
    assert engine.analyse(b, chess.Move.from_uci("f6g8"))[1] <= -60   # material equal: a draw is a loss of the game


def test_the_tempo_line_calls_out_a_stalled_game():
    b = chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 20 40")
    line = engine.tempo(b)
    assert "ahead by 5" in line and "No capture or pawn move for 20 plies" in line
    user = engine.chat_messages(b, [])[1]["content"]
    assert "TEMPO: " + line in user and "Move number: 40" in user
