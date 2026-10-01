"""Chess plumbing ported from jev_chess (backend/app/players.py). Python does the tactics bookkeeping
(hanging pieces, mate-in-1, repeats) and tags every legal move, so a model only has to choose.
Jev answers over OpenRouter's Decisions API; the cheap opponent is an OpenAI model, called directly."""

import json
import random
import re
import time

import chess
import httpx

from config import settings
from shared.openrouter import decide

NAMES = {chess.PAWN: "Pawn", chess.KNIGHT: "Knight", chess.BISHOP: "Bishop",
         chess.ROOK: "Rook", chess.QUEEN: "Queen", chess.KING: "King"}
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
# USD per 1M tokens (input, output); OpenAI's response carries no cost.
# ponytail: hand-copied price list (checked 2026-10-01), update it when OpenAI reprices.
OPENAI_PRICES = {"gpt-4.1-nano": (0.10, 0.40), "gpt-5-nano": (0.05, 0.40), "gpt-4o-mini": (0.15, 0.60),
                 "gpt-4.1-mini": (0.40, 1.60), "gpt-5-mini": (0.25, 2.00)}
OPPONENTS = list(OPENAI_PRICES)   # the cheap models the Play tab offers


def color_name(c: bool) -> str:
    return "white" if c else "black"


def hanging(board: chess.Board, color: bool) -> list[tuple[str, int]]:
    """Pieces of `color` that can be won: attacked and undefended, or attacked by a cheaper piece.
    ponytail: one-exchange heuristic, not full SEE; ignores pins/x-rays. Upgrade to SEE if it misjudges trades."""
    out = []
    for sq, p in board.piece_map().items():
        if p.color != color or p.piece_type == chess.KING:
            continue
        atk = board.attackers(not color, sq)
        if not atk:
            continue
        # an enemy king can only capture undefended pieces, so rank it as the most expensive attacker
        low = min(atk, key=lambda a: VALUES[board.piece_type_at(a)] or 100)
        if not board.attackers(color, sq) or (VALUES[board.piece_type_at(low)] or 100) < VALUES[p.piece_type]:
            out.append((f"{NAMES[p.piece_type]} {chess.square_name(sq)} (attacked by {NAMES[board.piece_type_at(low)]})",
                        VALUES[p.piece_type]))
    return out


def _gives_mate(board: chess.Board, reply: chess.Move) -> bool:
    board.push(reply)
    mate = board.is_checkmate()
    board.pop()
    return mate


def passed(board: chess.Board, sq: int, color: bool) -> bool:
    """No enemy pawn ahead of this pawn on its own or an adjacent file."""
    f, r = chess.square_file(sq), chess.square_rank(sq)
    ahead = range(r + 1, 8) if color else range(0, r)
    return not any(board.piece_at(chess.square(ff, rr)) == chess.Piece(chess.PAWN, not color)
                   for ff in (f - 1, f, f + 1) if 0 <= ff < 8 for rr in ahead)


def analyse(board: chess.Board, move: chess.Move) -> tuple[str, int]:
    """('Knight g1→f3 (Nf3), SAFE capture of Pawn, check', priority score used to sort options).
    The scores order the list both models choose from, so they favour forcing, game-ending moves: captures,
    checks, threats, trades when ahead, passed pawns. Quiet moves score 0."""
    p = board.piece_at(move.from_square)
    to = chess.square_name(move.to_square)
    parts = [f"{NAMES[p.piece_type]} {chess.square_name(move.from_square)}→{to} ({board.san(move)})"]
    score = 0
    cap = (chess.PAWN if board.is_en_passant(move) else board.piece_type_at(move.to_square)) if board.is_capture(move) else None
    if board.is_castling(move):
        parts.append("castles")
        score += 2
    if move.promotion:
        parts.append(f"promotes to {NAMES[move.promotion]}")
        score += VALUES[move.promotion] * 10
    own_last = board.move_stack[-2] if len(board.move_stack) >= 2 else None
    undoes = own_last and (move.from_square, move.to_square) == (own_last.to_square, own_last.from_square)
    me = board.turn
    mat = material(board)
    lead = (mat["white"] - mat["black"]) * (1 if me else -1)   # the mover's material lead before the move
    threatened_before = {d.split(" (")[0] for d, _ in hanging(board, not me)}
    board.push(move)
    try:
        if board.is_checkmate():
            return ", ".join(parts + ["CHECKMATE (wins the game)"]), 1000
        if board.is_stalemate():   # a draw: throws away a won game, rescues a lost one
            return ", ".join(parts + ["STALEMATE (draw)"]), -500 if lead >= 0 else 50
        mine = hanging(board, me)
        moved_hangs = any(d.split(" (")[0].endswith(to) for d, _ in mine)
        if cap:
            diff = VALUES[cap] - VALUES[p.piece_type]
            if not moved_hangs:
                parts.append(f"SAFE capture of {NAMES[cap]}")
                score += VALUES[cap] * 10
            elif diff > 0:
                parts.append(f"WINNING TRADE: your {NAMES[p.piece_type]} for their {NAMES[cap]}")
                score += diff * 10
            elif diff == 0:   # trading down while ahead is how a won game ends
                parts.append(f"EVEN TRADE ({NAMES[cap]} for {NAMES[p.piece_type]})" + (", you are ahead: simplify" if lead > 0 else ""))
                score += 8 if lead > 0 else 2
            else:
                parts.append(f"LOSING TRADE: your {NAMES[p.piece_type]} for their {NAMES[cap]}")
                score += diff * 10
        if board.is_check():
            parts.append("check")
            score += 3
        new = [(d, v) for d, v in hanging(board, not me) if d.split(" (")[0] not in threatened_before]
        if new and not moved_hangs:
            parts.append("THREATENS " + ", ".join(d.split(" (")[0] for d, _ in new))
            score += min(3 * max(v for _, v in new), 12)   # a threat is a tempo, not a capture: below a safe minor-piece capture
        if p.piece_type == chess.PAWN and not move.promotion and passed(board, move.to_square, me):
            rank = chess.square_rank(move.to_square) if me else 7 - chess.square_rank(move.to_square)
            parts.append(f"PASSED PAWN push (rank {rank + 1} of 8)")
            score += 2 + rank
        if mine:
            parts.append("BLUNDER RISK: leaves " + ", ".join(d for d, _ in mine) + " hanging")
            score -= 10 * max(v for _, v in mine)
        if any(_gives_mate(board, r) for r in list(board.legal_moves)):
            parts.append("BLUNDER: allows opponent CHECKMATE IN 1")
            score -= 900
        if p.piece_type != chess.KING:   # quiet moves get a direction: toward their king, pawns forward
            ek = board.king(not me)
            closer = chess.square_distance(move.from_square, ek) - chess.square_distance(move.to_square, ek)
            score += max(-2, min(3, closer)) + (1 if p.piece_type == chess.PAWN else 0)
        if lead >= 3:   # mop-up: a won ending is mated by shrinking the enemy king's box and walking yours over
            ksq, mine_k = board.king(not me), board.king(me)
            room = sum(1 for m in board.legal_moves if m.from_square == ksq) if not board.is_check() else 0
            close = 7 - chess.square_distance(ksq, mine_k)
            edge = max(abs(3.5 - chess.square_file(ksq)), abs(3.5 - chess.square_rank(ksq)))   # 0.5 centre .. 3.5 edge
            if room <= 3:
                parts.append(f"BOXES IN their king ({room} squares left)")
            score += (8 - room) + close + round(edge * 2)
        # repeats need real move history on the board (play() replays it), a FEN alone can't see them.
        # Not behind = a repeat wastes a winnable game; behind = a draw is a good result.
        if undoes:
            parts.append("UNDOES your previous move")
            score -= 10 if lead >= 0 else 3
        if board.is_repetition(3):
            parts.append("DRAW by threefold repetition")
            score += -60 if lead >= 0 else 5
        elif board.is_repetition(2):
            parts.append("REPEATS an earlier position")
            score -= 20 if lead >= 0 else 3
    finally:
        board.pop()
    return ", ".join(parts), score


def pgn(san_history: list[str]) -> str:
    return " ".join(f"{i // 2 + 1}. {m}" if i % 2 == 0 else m for i, m in enumerate(san_history))


def material(board: chess.Board) -> dict:
    w = sum(VALUES[p.piece_type] for p in board.piece_map().values() if p.color)
    b = sum(VALUES[p.piece_type] for p in board.piece_map().values() if not p.color)
    lead = "equal" if w == b else f"{'white' if w > b else 'black'} +{abs(w - b)}"
    return {"white": w, "black": b, "balance": lead}


def tempo(board: chess.Board) -> str:
    """One line of urgency, computed: who is ahead, and whether the game has stalled."""
    m = material(board)
    lead = (m["white"] - m["black"]) * (1 if board.turn else -1)
    out = (f"You are ahead by {lead}: trade pieces and push passed pawns to convert." if lead > 0 else
           f"You are behind by {-lead}: avoid trades, attack the king, create threats." if lead < 0 else
           "Material is equal: look for checks, captures and threats.")
    if board.halfmove_clock >= 16:
        out += f" No capture or pawn move for {board.halfmove_clock} plies: break it now with a capture, check or pawn push."
    return out


def position_state(board: chess.Board, san_history: list[str]) -> dict:
    pieces = {color_name(c): sorted(f"{NAMES[p.piece_type]} {chess.square_name(s)}"
                                    for s, p in board.piece_map().items() if p.color == c)
              for c in (chess.WHITE, chess.BLACK)}
    return {
        "side_to_move": color_name(board.turn),
        "fen": board.fen(),
        "board": str(board),  # uppercase = white, lowercase = black, rank 8 at top
        "pieces": pieces,  # explicit square→piece list so models don't lose track of the board
        "in_check": board.is_check(),
        "material": material(board),
        "your_pieces_in_danger": [d for d, _ in hanging(board, board.turn)],
        "enemy_pieces_you_can_win": [d for d, _ in hanging(board, not board.turn)],
        "move_number": board.fullmove_number,
        "plies_since_capture_or_pawn_move": board.halfmove_clock,  # 100 = fifty-move draw
        "tempo": tempo(board),
        "game_pgn": pgn(san_history),  # full game: ~3 tokens/ply, models play better with it
    }


def scored_moves(board: chess.Board) -> list[tuple[str, str, int]]:
    """(uci, description, score), most promising first: models (Jev included) lean toward options listed early."""
    return sorted(((m.uci(), *analyse(board, m)) for m in board.legal_moves), key=lambda x: -x[2])


def legal_options(board: chess.Board) -> dict[str, str]:
    return {u: d for u, d, _ in scored_moves(board)}


def jev_questions(board: chess.Board) -> dict:
    side = color_name(board.turn)
    return {
        "move": {
            "type": "choice",
            "instructions": (
                f"You are playing {side} and must WIN, fast. Pick the move that ends the game soonest, using the tags. "
                f"1) CHECKMATE always. 2) Never BLUNDER, BLUNDER RISK or LOSING TRADE. "
                f"3) Win material: SAFE captures, WINNING TRADEs. 4) Save a piece in your_pieces_in_danger. "
                f"5) Forcing moves: check, THREATENS. 6) Ahead: EVEN TRADEs and PASSED PAWN pushes; behind: no trades, attack. "
                f"7) Never a quiet shuffle, UNDOES or REPEATS: follow the state's tempo line. "
                f"The list is sorted best-first; prefer the top unless a lower move is clearly more forcing."),
            "criteria": legal_options(board),
        },
        "eval": {
            "type": "score",
            "instructions": "Who stands better in this position?",
            "criteria": ["Black is winning", "Black is better", "Equal", "White is better", "White is winning"],
        },
        "threat": {
            "type": "noul",
            "instructions": f"Is any {side} piece currently attacked and insufficiently defended?",
            "criteria": {"true": f"A {side} piece is hanging or the king is in danger",
                         "false": f"All {side} pieces are safe"},
        },
    }


def jev_move(board: chess.Board, san_history: list[str]) -> dict:
    """Jev picks from the tagged legal moves, so its answer is always legal."""
    state, questions = position_state(board, san_history), jev_questions(board)
    data, latency = decide(state, questions)
    usage = data.get("usage") or {}
    return {"uci": data["answers"]["move"]["choice"], "model": data.get("model", settings.JEV_MODEL),
            "latency_ms": latency, "cost_usd": usage.get("cost"), "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0), "reason": None,
            "request": {"model": settings.JEV_MODEL, "state": state, "questions": questions},
            "response": data, "fallback": False}


SYSTEM = """You are a ruthless chess engine playing a game against another AI. Your only goal is to WIN, as fast as possible.
Draws and long games count as failures. Decide quickly: the engine has already done the calculation for you.

## What you get each turn
- Side to move, move number, FEN, an ASCII board (uppercase = White, rank 8 at the top) and every piece's square.
- Material, your pieces in danger, enemy pieces you can win, and a TEMPO line telling you what the game needs now.
- LEGAL moves in UCI, sorted best-first by the engine, each with tags:
  - CHECKMATE: wins the game
  - SAFE capture of X: wins X for free
  - WINNING TRADE / EVEN TRADE / LOSING TRADE: a capture where your piece can be taken back
  - THREATENS X: after this move, X can be won next turn
  - PASSED PAWN push: no enemy pawn can stop it, the closer to rank 8 the better
  - check, castles, promotes to X
  - BLUNDER RISK: leaves your piece hanging | BLUNDER: allows CHECKMATE IN 1
  - UNDOES / REPEATS / DRAW: wastes time
Piece values: Pawn 1, Knight 3, Bishop 3, Rook 5, Queen 9.

## Pick the FIRST rule that applies
1. CHECKMATE: play it.
2. Never play BLUNDER, BLUNDER RISK or LOSING TRADE.
3. Win material: SAFE capture (highest value first), then WINNING TRADE.
4. A piece of yours is in danger: save it (move it, defend it, or trade it).
5. Force the opponent: check or THREATENS, preferring ones near their king.
6. Ahead in material: EVEN TRADE every piece you can and push PASSED PAWNs to promote. Behind: no trades, attack the king.
7. Otherwise push a pawn toward their king, or bring a piece closer to it. Castle early, then attack.
Never shuffle a piece back and forth, never UNDOES / REPEATS / DRAW. If the TEMPO line says the game has stalled,
play a capture, a check or a pawn push this move.
The list is sorted: when unsure, play the first move that breaks none of the rules.

## Answer
Only one JSON object, no markdown, no thinking out loud:
{"move": "<uci copied exactly from LEGAL>", "reason": "<max 8 words>"}

## Examples
LEGAL: b5c6: Bishop b5→c6 (Bxc6), SAFE capture of Knight | d1h5: Queen d1→h5 (Qh5), BLUNDER RISK: leaves Queen h5 hanging | e1g1: King e1→g1 (O-O), castles
{"move": "b5c6", "reason": "Free knight"}

TEMPO: You are ahead by 5: trade pieces and push passed pawns to convert.
LEGAL: d1d8: Rook d1→d8 (Rxd8+), EVEN TRADE (Rook for Rook), you are ahead: simplify, check | g1f1: King g1→f1 (Kf1) | b5b6: Pawn b5→b6 (b6), PASSED PAWN push (rank 6 of 8)
{"move": "d1d8", "reason": "Ahead: trade rooks, then promote"}

TEMPO: Material is equal. No capture or pawn move for 18 plies: break it now with a capture, check or pawn push.
LEGAL: f3e5: Knight f3→e5 (Ne5), THREATENS Queen d7 | c3d1: Knight c3→d1 (Nd1), UNDOES your previous move | g2g4: Pawn g2→g4 (g4)
{"move": "f3e5", "reason": "Hits the queen, forces a reply"}"""


def chat_messages(board: chess.Board, san_history: list[str], error: str | None = None) -> list[dict]:
    st = position_state(board, san_history)
    moves = "\n".join(f"{u}: {d}" for u, d in legal_options(board).items())
    m = st["material"]
    user = (f"Side to move: {st['side_to_move']}\nFEN: {st['fen']}\nIn check: {st['in_check']}\n"
            f"Board:\n{st['board']}\n"
            f"PIECES white: {', '.join(st['pieces']['white'])}\nPIECES black: {', '.join(st['pieces']['black'])}\n"
            f"Material: white {m['white']}, black {m['black']} ({m['balance']})\n"
            f"Your pieces in danger: {'; '.join(st['your_pieces_in_danger']) or 'none'}\n"
            f"Enemy pieces you can win: {'; '.join(st['enemy_pieces_you_can_win']) or 'none'}\n"
            f"Move number: {st['move_number']}\nTEMPO: {st['tempo']}\n"
            f"Game so far (PGN): {st['game_pgn'] or '(start)'}\n\nLEGAL moves:\n{moves}")
    if error:
        user += f"\n\nYour previous answer was rejected: {error}. Copy one UCI move exactly from the LEGAL list."
    # static system prompt first = stable prefix, which OpenAI caches automatically
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


UCI_RE = re.compile(r"\b([a-h][1-8][a-h][1-8][qrbn]?)\b")


def parse_move(text: str, board: chess.Board) -> tuple[chess.Move | None, str | None]:
    """(legal move or None, the model's stated reason)."""
    reason = None
    try:
        obj = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
        cand, reason = [str(obj["move"]).strip().lower()], obj.get("reason")
    except Exception:
        cand = UCI_RE.findall(text.lower())
    for c in cand:
        try:
            m = chess.Move.from_uci(c)
        except ValueError:
            continue
        if m in board.legal_moves:
            return m, reason
    return None, reason


def _post(url: str, body: dict, headers: dict) -> httpx.Response:
    for attempt in range(4):   # retry transient 429/5xx only; low OpenAI tiers rate-limit tokens per minute
        r = httpx.post(url, json=body, headers=headers, timeout=settings.HTTP_TIMEOUT_S)
        if r.status_code != 429 and r.status_code < 500 or "quota" in r.text or "credits" in r.text:
            break
        wait = r.headers.get("retry-after")
        time.sleep(min(float(wait), 20) if wait and wait.replace(".", "").isdigit() else 2.0 * (attempt + 1))
    return r


def openai_chat(model: str, messages: list[dict]) -> dict:
    """One chat completion on OpenAI, with OPENAI_API_KEY. A failure (no credits, bad key) stops the game with
    OpenAI's own message."""
    body = {"model": model, "messages": messages, "max_completion_tokens": 300}   # the reply is ~25 tokens
    if model.startswith("gpt-5"):
        body["reasoning_effort"] = "minimal"   # gpt-5 thinks by default and rejects temperature
    else:
        body["temperature"] = 0.2
    key = settings.require(settings.OPENAI_API_KEY, "OPENAI_API_KEY")
    r = _post(OPENAI_URL, body, {"Authorization": f"Bearer {key}"})
    if r.is_error:
        raise RuntimeError(f"OpenAI {r.status_code}: {r.json().get('error', {}).get('message', r.text)[:200]}")
    return r.json()


def llm_move(board: chess.Board, san_history: list[str], model: str, retries: int = 2) -> dict:
    """A cheap OpenAI model picks a move; up to `retries` re-asks, then a random legal move (fallback)."""
    total = {"latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
    price = OPENAI_PRICES.get(model)
    error, messages, data, move, reason = None, None, None, None, None
    for _ in range(retries + 1):
        messages = chat_messages(board, san_history, error)
        t0 = time.perf_counter()
        data = openai_chat(model, messages)
        total["latency_ms"] += (time.perf_counter() - t0) * 1000
        u = data.get("usage") or {}
        total["input_tokens"] += u.get("prompt_tokens", 0)
        total["output_tokens"] += u.get("completion_tokens", 0)
        # OpenAI reports no cost: priced from OPENAI_PRICES (None if the model isn't listed)
        total["cost_usd"] = None if not price or total["cost_usd"] is None else total["cost_usd"] + (
            u.get("prompt_tokens", 0) * price[0] + u.get("completion_tokens", 0) * price[1]) / 1e6
        text = data["choices"][0]["message"].get("content") or ""
        move, reason = parse_move(text, board)
        if move:
            break
        error = f"'{text[:80]}' is not a legal move"
    fallback = move is None
    if fallback:   # never produced a legal move: play a random one so the game continues
        move = random.choice(list(board.legal_moves))
    return {"uci": move.uci(), "model": data.get("model", model), "reason": reason, **total,
            "request": {"model": model, "messages": messages}, "response": data, "fallback": fallback}


def heuristic_move(board: chess.Board) -> dict:
    """No model: the top of the tag-sorted list, i.e. what Jev and the LLM are shown first."""
    return {"uci": scored_moves(board)[0][0], "model": "(no model)", "latency_ms": 0.0, "cost_usd": 0.0,
            "input_tokens": 0, "output_tokens": 0, "reason": "highest tag score", "request": None,
            "response": None, "fallback": False}


def get_move(board: chess.Board, san_history: list[str], player: str) -> dict:
    if player == "jev":
        return jev_move(board, san_history)
    if player == "heuristic":
        return heuristic_move(board)
    return llm_move(board, san_history, player)
