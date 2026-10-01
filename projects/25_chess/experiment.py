"""Project 25: chess. Jev vs a cheap OpenAI model, on labelled tactics positions (Run / Dataset) and in a full
live game (the web UI's Play tab, via play()). Ported from jev_chess."""

import json
import random
from pathlib import Path
from typing import TypedDict

import chess
from langgraph.graph import END, START, StateGraph

from config import settings
from core.run import Result, Run

from . import engine

TITLE = "25 · Chess"
PRIMITIVE = "Choice"
LABELS = ["mate_in_1", "win_material", "save_piece", "avoid_blunder"]   # the tactic a position tests
MISS = "miss"   # the variant played a move outside the position's accepted set
DATASET = json.loads((Path(__file__).parent / "dataset.json").read_text(encoding="utf-8"))
EXAMPLES = {
    "Back-rank mate": DATASET[0]["input"],
    "Free queen": DATASET[3]["input"],
    "Queen attacked by a pawn": DATASET[6]["input"],
    "Mate threat on the back rank": DATASET[9]["input"],
}
MAX_PLIES = 300


class State(TypedDict, total=False):
    input: dict
    jev: Run
    cheap_llm: Run
    heuristic: Run


def _run(variant: str, board: chess.Board, rec: dict, inp: dict, confidence=None, raw=None) -> Run:
    move = chess.Move.from_uci(rec["uci"])
    return Run(variant=variant, model=rec["model"], label=inp["theme"] if rec["uci"] in inp["best"] else MISS,
               confidence=confidence, latency_ms=rec["latency_ms"], input_tokens=rec["input_tokens"],
               output_tokens=rec["output_tokens"], cost_usd=rec["cost_usd"],
               raw={"move": board.san(move), "uci": rec["uci"], "reason": rec["reason"],
                    "fallback": rec["fallback"], **(raw or {})})


def jev_node(state: State) -> State:
    board = chess.Board(state["input"]["fen"])
    rec = engine.jev_move(board, [])
    ans = rec["response"]["answers"]
    return {"jev": _run("jev", board, rec, state["input"], confidence=ans["move"]["confidence"],
                        raw={"probabilities": ans["move"]["probabilities"], "eval": ans["eval"].get("score"),
                             "threat": ans["threat"].get("noul")})}


def cheap_llm_node(state: State) -> State:
    board = chess.Board(state["input"]["fen"])
    return {"cheap_llm": _run("cheap_llm", board, engine.llm_move(board, [], settings.CHESS_OPPONENT_MODEL),
                              state["input"])}


def heuristic_node(state: State) -> State:
    board = chess.Board(state["input"]["fen"])
    return {"heuristic": _run("heuristic", board, engine.heuristic_move(board), state["input"])}


NODES = {"jev": jev_node, "cheap_llm": cheap_llm_node, "heuristic": heuristic_node}


def build_graph():
    g = StateGraph(State)
    for name, fn in NODES.items():   # fan out: every variant sees the same position, in parallel
        g.add_node(name, fn)
        g.add_edge(START, name)
        g.add_edge(name, END)
    return g.compile()


GRAPH = build_graph()


def run_experiment(inp: dict | str) -> Result:
    inp = json.loads(inp) if isinstance(inp, str) else inp
    chess.Board(inp["fen"])   # a bad FEN fails here, before any paid call
    out = GRAPH.invoke({"input": inp})
    return Result.of(*(out[name] for name in NODES))


# --- A full game for the Play tab. Not a LangGraph: one loop, one move per iteration. ---

PLAYERS = ["jev", *engine.OPPONENTS, "heuristic"]


def play(white: str, black: str):
    """Yields one record per ply until the game ends. The board is rebuilt from the uci list every turn,
    never from a FEN, so threefold repetition and the 50-move rule see the whole history."""
    uci, san = [], []
    while True:
        board = chess.Board()
        for u in uci:
            board.push_uci(u)
        side = engine.color_name(board.turn)
        player = white if board.turn else black
        rec = engine.get_move(board, san, player)
        move = chess.Move.from_uci(rec["uci"])
        if move not in board.legal_moves:   # defensive: never trust a model's output blindly
            move, rec["fallback"] = random.choice(list(board.legal_moves)), True
        piece = board.piece_at(move.from_square)
        captured = board.piece_at(move.to_square) or (
            chess.Piece(chess.PAWN, not board.turn) if board.is_en_passant(move) else None)
        san.append(board.san(move))
        uci.append(move.uci())
        board.push(move)
        result = None
        if board.is_game_over(claim_draw=True):
            o = board.outcome(claim_draw=True)
            result = f"{o.result()} · {o.termination.name.replace('_', ' ').lower()}"
        elif len(san) >= MAX_PLIES:
            result = "1/2-1/2 · move limit"
        yield {"ply": len(san), "side": side, "player": player, "uci": move.uci(), "san": san[-1],
               "piece": engine.NAMES[piece.piece_type], "from": chess.square_name(move.from_square),
               "to": chess.square_name(move.to_square),
               "captured": engine.NAMES[captured.piece_type] if captured else None, "fen": board.fen(),
               "result": result, **{k: rec[k] for k in ("model", "latency_ms", "cost_usd", "input_tokens",
                                                        "output_tokens", "reason", "request", "response", "fallback")}}
        if result:
            return
