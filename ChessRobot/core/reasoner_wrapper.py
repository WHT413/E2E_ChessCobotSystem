from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
import chess
import numpy as np
import uuid
from datetime import datetime, timezone
import cv2
from collections import Counter, OrderedDict

@dataclass
class FilterResult:
    accepted: bool
    reason: str
    move_uci: Optional[str] = None
    new_fen: Optional[str] = None
    candidates: Optional[int] = None
    examples: Optional[List[str]] = None
    next_to_move: Optional[str] = None  # 'w' or 'b'
    last_mover: Optional[str] = None    # 'w' or 'b'

class OneMoveFilter:
    """
    Single-move validator for vision-derived chess snapshots.
    """

    def __init__(
        self,
        init_fen_like: str,
        default_fields: str = "w - - 0 1",
        use_fast_precheck: bool = True,
        cache_size: int = 256,
    ) -> None:
        self.default_fields = default_fields
        self.use_fast_precheck = use_fast_precheck
        self._allowed_diffs = {2, 3, 4}
        self.board = self._make_board(init_fen_like)
        self._last_obs_key: Optional[Tuple[str, bool, str]] = None
        self._lru: OrderedDict[Tuple[str, bool, str], List[chess.Move]] = OrderedDict()
        self._cache_size = cache_size

    # ---------------- Public API ----------------
    def set_fast_precheck(self, enabled: bool) -> None:
        self.use_fast_precheck = bool(enabled)

    def reset_to(self, fen_like: str) -> None:
        self.board = self._make_board(fen_like)
        self._last_obs_key = None

    def current_fen(self) -> str:
        return self.board.fen()

    def process_frame(self, obs_fen_like: str) -> FilterResult:
        try:
            obs_board = self._make_board(obs_fen_like)
        except ValueError:
            return FilterResult(accepted=False, reason="invalid_observation_fen")

        if not self.board.is_valid() or not obs_board.is_valid():
            return FilterResult(accepted=False, reason="invalid_board_state")

        # Fast recheck using cache key
        cur_key = (self.board.board_fen(), self.board.turn, obs_board.board_fen())
        if self._last_obs_key == cur_key:
            # Same comparison as last frame; avoid recompute
            cached = self._lru_get(cur_key)
            n = len(cached)
            if n == 1:
                mv = cached[0]
                self.board.push(mv)
                return FilterResult(
                    accepted=True,
                    reason="unique_match_cached",
                    move_uci=mv.uci(),
                    new_fen=self.board.fen(),
                    candidates=1,
                    next_to_move=self.next_side_token(),
                    last_mover=self.last_mover_token(),
                )
            if n == 0:
                return FilterResult(accepted=False, reason="no_legal_match_cached", candidates=0)
            return FilterResult(
                accepted=False,
                reason=f"ambiguous_{n}_cached",
                candidates=n,
                examples=[m.uci() for m in cached[:5]],
            )

        # Heuristics
        if self.use_fast_precheck:
            diff_sqs = self._diff_squares(self.board, obs_board)
            if not (2 <= len(diff_sqs) <= 4):
                return FilterResult(accepted=False, reason="no_legal_match")
            if not self._material_delta_one_move(self.board, obs_board):
                return FilterResult(accepted=False, reason="material_impossible")

        matches = self._find_matches_pruned(self.board, obs_board)
        self._lru_put(cur_key, matches)
        self._last_obs_key = cur_key

        n = len(matches)
        if n == 1:
            mv = matches[0]
            self.board.push(mv)
            return FilterResult(
                accepted=True,
                reason="unique_match",
                move_uci=mv.uci(),
                new_fen=self.board.fen(),
                candidates=1,
                next_to_move=self.next_side_token(),
                last_mover=self.last_mover_token(),
            )
        if n == 0:
            return FilterResult(accepted=False, reason="no_legal_match", candidates=0)
        return FilterResult(
            accepted=False,
            reason=f"ambiguous_{n}",
            candidates=n,
            examples=[m.uci() for m in matches[:5]],
        )

    # ---------------- Core helpers ----------------
    def _normalize_fen_like(self, fen_like: str) -> str:
        toks = (fen_like or "").strip().split()
        if not toks:
            raise ValueError("Empty FEN string")

        if len(toks) == 1:
            return f"{toks[0]} {self.default_fields}"

        if 2 <= len(toks) <= 5:
            def_side, def_cast, def_ep, def_half, def_full = self.default_fields.split()
            piece = toks[0]
            side = toks[1] if len(toks) > 1 else def_side
            cast = toks[2] if len(toks) > 2 else def_cast
            ep = toks[3] if len(toks) > 3 else def_ep
            half = toks[4] if len(toks) > 4 else def_half
            full = def_full
            return f"{piece} {side} {cast} {ep} {half} {full}"

        return " ".join(toks[:6])

    def next_side_token(self) -> str:
        return 'w' if self.board.turn else 'b'

    def last_mover_token(self) -> str:
        return 'b' if self.board.turn else 'w'

    def fen_with_side(self, fen_like: str, side: Optional[str] = None) -> str:
        fen6 = self._normalize_fen_like(fen_like)
        toks = fen6.split()
        toks[1] = side or self.next_side_token()
        return ' '.join(toks[:6])

    def _make_board(self, fen_like: str) -> chess.Board:
        norm = self._normalize_fen_like(fen_like)
        return chess.Board(norm)

    # ---------- Pruning & fast checks ----------
    def _diff_squares(self, a: chess.Board, b: chess.Board) -> List[int]:
        diffs: List[int] = []
        for sq in chess.SQUARES:
            if a.piece_at(sq) != b.piece_at(sq):
                diffs.append(sq)
        return diffs

    def _material_signature(self, board: chess.Board) -> Counter:
        # Count pieces by symbol (case-sensitive: white uppercase, black lowercase)
        cnt = Counter()
        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if p:
                cnt[p.symbol()] += 1
        return cnt

    def _material_delta_one_move(self, a: chess.Board, b: chess.Board) -> bool:
        """
        Allowable deltas in a single move:
        - No net material change (quiet move or non-capturing move).
        - Capture: exactly one enemy piece disappears.
        - Promotion: pawn changes type on b (handled later by exact match).
        """
        ca = self._material_signature(a)
        cb = self._material_signature(b)

        # Total piece count may change by at most 1 (capture) or stay same.
        na, nb = sum(ca.values()), sum(cb.values())
        if nb not in (na, na - 1, na + 0):  # nb == na or nb == na-1
            return False

        # Per-color piece count difference should be small
        wa = sum(v for k, v in ca.items() if k.isupper())
        wb = sum(v for k, v in cb.items() if k.isupper())
        ba = na - wa
        bb = nb - wb
        if abs(wa - wb) > 1 or abs(ba - bb) > 1:
            return False

        return True

    def _find_matches_pruned(self, a: chess.Board, b: chess.Board) -> List[chess.Move]:
        """
        Match moves with pruning:
        - Restrict candidate moves to those whose from_square is in the changed squares.
        - Use push/pop instead of copy to avoid allocations.
        """
        matches: List[chess.Move] = []

        # Candidate from-squares = changed squares that currently contain a piece.
        diff_sqs = set(self._diff_squares(a, b))
        from_candidates = {sq for sq in diff_sqs if a.piece_at(sq) is not None}
        if not from_candidates:
            return matches

        for mv in a.legal_moves:
            if mv.from_square not in from_candidates:
                continue
            a.push(mv)
            # Compare only piece placement; ignore clocks/EP/castling
            if a.board_fen() == b.board_fen():
                matches.append(mv)
            a.pop()
        return matches

    # ---------- Small LRU cache ----------
    def _lru_get(self, key: Tuple[str, bool, str]) -> List[chess.Move]:
        if key in self._lru:
            val = self._lru.pop(key)
            self._lru[key] = val
            return val
        return []

    def _lru_put(self, key: Tuple[str, bool, str], val: List[chess.Move]) -> None:
        if key in self._lru:
            self._lru.pop(key)
        self._lru[key] = val
        if len(self._lru) > self._cache_size:
            self._lru.popitem(last=False)

    @staticmethod
    def _piece_label(p):
        if p is None:
            return None
        color = "white" if p.color == chess.WHITE else "black"
        names = {1: "pawn", 2: "knight", 3: "bishop", 4: "rook", 5: "queen", 6: "king"}
        return f"{color}_{names[p.piece_type]}"

    @staticmethod
    def build_move_event_from(fen_str: str, uci: str) -> dict:
        # Create an ephemeral board from the provided FEN string
        b = chess.Board(fen=fen_str)
        mv = chess.Move.from_uci(uci)

        # Classify move
        if b.is_castling(mv):
            mv_type = "castle"
        elif b.is_capture(mv) or b.is_en_passant(mv):
            mv_type = "attack"
        else:
            mv_type = "move"

        # Resolve piece identities before the move
        from_sq, to_sq = mv.from_square, mv.to_square
        from_piece = b.piece_at(from_sq)
        if b.is_en_passant(mv):
            cap_sq = chess.square(chess.square_file(to_sq), chess.square_rank(from_sq))
            captured_piece = b.piece_at(cap_sq)
        else:
            captured_piece = b.piece_at(to_sq)

        # SAN + check flag (computed on a copy board)
        san = b.san(mv)
        b.push(mv)
        results_in_check = b.is_check()
        b.pop()

        return {
            "goal_id": f"{mv_type}_{uuid.uuid4().hex[:6]}",
            "header": {
                "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
            },
            "move": {
                "type": mv_type,
                "from": chess.square_name(from_sq),
                "to": chess.square_name(to_sq),
                "from_piece": OneMoveFilter._piece_label(from_piece),
                "to_piece": OneMoveFilter._piece_label(captured_piece),
                "notation": san,                # SAN (e.g., Qxf7+)
                "results_in_check": results_in_check,
            },
        }


# ------- Visualization (giữ nguyên nhưng tối ưu alpha blend) -------
def fen_to_symbol_grid(fen: str):
    board = chess.Board(fen)
    grid = [[None] * 8 for _ in range(8)]
    for sq in chess.SQUARES:
        r = 7 - chess.square_rank(sq)
        c = chess.square_file(sq)
        piece = board.piece_at(sq)
        grid[r][c] = piece.symbol() if piece else '.'
    return grid

def render_stable_fen_image(
    processor,
    fen: str,
    cell: int = 64,
    margin: int = 16,
    piece_images: Optional[dict] = None,
):
    sym_grid = fen_to_symbol_grid(fen)
    H = W = cell * 8 + margin * 2
    img = np.full((H, W, 3), 255, dtype=np.uint8)

    for r in range(8):
        for c in range(8):
            y1 = margin + r * cell
            x1 = margin + c * cell
            y2 = y1 + cell
            x2 = x1 + cell
            is_dark = (r + c) % 2 == 1
            color = (181, 136, 99) if is_dark else (240, 217, 181)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness=-1)

    for r in range(8):
        for c in range(8):
            s = sym_grid[r][c]
            if s == '.':
                continue
            y = margin + r * cell
            x = margin + c * cell
            if piece_images and s in piece_images:
                piece_img = cv2.resize(piece_images[s], (cell, cell), interpolation=cv2.INTER_AREA)
                if piece_img.shape[2] == 4:
                    alpha = piece_img[:, :, 3:4] / 255.0
                    img[y:y + cell, x:x + cell] = alpha * piece_img[:, :, :3] + (1 - alpha) * img[y:y + cell, x:x + cell]
                else:
                    img[y:y + cell, x:x + cell] = piece_img[:, :, :3]
            else:
                y_txt = y + int(cell * 0.65)
                x_txt = x + int(cell * 0.25)
                is_white = s.isupper()
                txt_color = (20, 20, 20) if is_white else (30, 30, 30)
                cv2.putText(img, s, (x_txt, y_txt), cv2.FONT_HERSHEY_SIMPLEX, 1.6, txt_color, 2, cv2.LINE_AA)

    return img
