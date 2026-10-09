"""Server-authoritative game engine for Chinese dark chess (揭棋)."""

from __future__ import annotations

import copy
import secrets
from dataclasses import dataclass, field
from typing import Any


Position = tuple[int, int]


class GameError(ValueError):
    """A safe, user-facing game error."""


PIECE_TYPES = {
    "車": "rook",
    "俥": "rook",
    "馬": "horse",
    "傌": "horse",
    "象": "elephant",
    "相": "elephant",
    "士": "advisor",
    "仕": "advisor",
    "將": "king",
    "帥": "king",
    "砲": "cannon",
    "炮": "cannon",
    "卒": "pawn",
    "兵": "pawn",
}


@dataclass
class Game:
    """Complete private state. Never serialize an unrevealed identity."""

    board: dict[Position, dict[str, Any]] = field(default_factory=dict)
    captured: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    turn: str = "red"
    winner: str | None = None
    status: str = "等待黑方玩家加入"
    revision: int = 0

    def __post_init__(self) -> None:
        if not self.board:
            self.reset()

    def reset(self) -> None:
        self.board = {}
        self.captured = []
        self.history = []
        self.turn = "red"
        self.winner = None
        self.status = "红方先行"
        self.revision += 1

        shuffled: list[dict[str, Any]] = []
        for name in [
            "車", "馬", "象", "士", "士", "象", "馬", "車",
            "砲", "砲", "卒", "卒", "卒", "卒", "卒",
        ]:
            shuffled.append({"name": name, "color": "black", "revealed": False})
        for name in [
            "俥", "傌", "相", "仕", "仕", "相", "傌", "俥",
            "炮", "炮", "兵", "兵", "兵", "兵", "兵",
        ]:
            shuffled.append({"name": name, "color": "red", "revealed": False})
        secrets.SystemRandom().shuffle(shuffled)

        self.board[(0, 4)] = self._piece("將", "black", "king", "black", True)
        self.board[(9, 4)] = self._piece("帥", "red", "king", "red", True)

        positions: list[tuple[int, int, str, str]] = []
        back_row = [
            "rook", "horse", "elephant", "advisor", "king",
            "advisor", "elephant", "horse", "rook",
        ]
        for col in range(9):
            if col != 4:
                positions.extend(((0, col, back_row[col], "black"),
                                  (9, col, back_row[col], "red")))
        for col in (1, 7):
            positions.extend(((2, col, "cannon", "black"),
                              (7, col, "cannon", "red")))
        for col in (0, 2, 4, 6, 8):
            positions.extend(((3, col, "pawn", "black"),
                              (6, col, "pawn", "red")))

        for (row, col, hidden_type, control_side), piece in zip(positions, shuffled):
            piece["hidden_type"] = hidden_type
            piece["control_side"] = control_side
            self.board[(row, col)] = piece

    @staticmethod
    def _piece(name: str, color: str, hidden_type: str,
               control_side: str, revealed: bool) -> dict[str, Any]:
        return {
            "name": name,
            "color": color,
            "revealed": revealed,
            "hidden_type": hidden_type,
            "control_side": control_side,
        }

    def active_type(self, piece: dict[str, Any]) -> str:
        return PIECE_TYPES[piece["name"]] if piece["revealed"] else piece["hidden_type"]

    def movement_side(self, piece: dict[str, Any]) -> str:
        # Once revealed, identity determines pawn direction and king palace.
        return piece["color"] if piece["revealed"] else piece["control_side"]

    @staticmethod
    def in_bounds(pos: Position) -> bool:
        return 0 <= pos[0] <= 9 and 0 <= pos[1] <= 8

    @staticmethod
    def in_palace(row: int, col: int, side: str) -> bool:
        return 3 <= col <= 5 and ((0 <= row <= 2) if side == "black" else (7 <= row <= 9))

    @staticmethod
    def crossed_river(row: int, side: str) -> bool:
        return row >= 5 if side == "black" else row <= 4

    def count_between(self, start: Position, end: Position) -> int:
        r1, c1 = start
        r2, c2 = end
        if r1 == r2:
            step = 1 if c2 > c1 else -1
            return sum((r1, col) in self.board for col in range(c1 + step, c2, step))
        if c1 == c2:
            step = 1 if r2 > r1 else -1
            return sum((row, c1) in self.board for row in range(r1 + step, r2, step))
        return 0

    def is_valid_move(self, start: Position, end: Position) -> bool:
        if start not in self.board or start == end or not self.in_bounds(end):
            return False
        piece = self.board[start]
        target = self.board.get(end)
        # Control never changes after a piece is revealed. A player cannot capture
        # another piece controlled by the same player, regardless of its identity.
        if target and target["control_side"] == piece["control_side"]:
            return False

        piece_type = self.active_type(piece)
        side = self.movement_side(piece)
        r1, c1 = start
        r2, c2 = end
        dr, dc = r2 - r1, c2 - c1
        ar, ac = abs(dr), abs(dc)

        if piece_type == "rook":
            return (r1 == r2 or c1 == c2) and self.count_between(start, end) == 0
        if piece_type == "horse":
            if (ar, ac) not in ((2, 1), (1, 2)):
                return False
            leg = (r1 + dr // 2, c1) if ar == 2 else (r1, c1 + dc // 2)
            return leg not in self.board
        if piece_type == "elephant":
            return ar == 2 and ac == 2 and (r1 + dr // 2, c1 + dc // 2) not in self.board
        if piece_type == "advisor":
            return ar == 1 and ac == 1
        if piece_type == "king":
            if (target and self.active_type(target) == "king"
                    and target["color"] != piece["color"] and c1 == c2
                    and self.count_between(start, end) == 0):
                return True
            return ar + ac == 1 and self.in_palace(r2, c2, side)
        if piece_type == "cannon":
            if r1 != r2 and c1 != c2:
                return False
            between = self.count_between(start, end)
            return between == (1 if target else 0)
        if piece_type == "pawn":
            forward = 1 if side == "black" else -1
            return ((dr == forward and dc == 0)
                    or (self.crossed_river(r1, side) and dr == 0 and ac == 1))
        return False

    def legal_moves(self, start: Position, side: str) -> list[list[int]]:
        piece = self.board.get(start)
        if not piece or piece["control_side"] != side or self.turn != side or self.winner:
            return []
        return [[row, col] for row in range(10) for col in range(9)
                if self.is_valid_move(start, (row, col))]

    def move(self, start: Position, end: Position, side: str) -> None:
        if self.winner:
            raise GameError("棋局已经结束")
        if side != self.turn:
            raise GameError("还没轮到你")
        piece = self.board.get(start)
        if not piece or piece["control_side"] != side:
            raise GameError("这不是你控制的棋子")
        if not self.is_valid_move(start, end):
            raise GameError("该落点不符合行棋规则")

        self.history.append({
            "board": copy.deepcopy(self.board),
            "captured": copy.deepcopy(self.captured),
            "turn": self.turn,
            "winner": self.winner,
            "status": self.status,
        })
        captured = self.board.get(end)
        if captured:
            public_capture = copy.deepcopy(captured)
            public_capture["revealed"] = True
            self.captured.append(public_capture)

        moving = self.board.pop(start)
        moving["revealed"] = True
        self.board[end] = moving
        if captured and PIECE_TYPES[captured["name"]] == "king":
            self.winner = side
            self.status = f"{'红' if side == 'red' else '黑'}方获胜"
        else:
            self.turn = "black" if side == "red" else "red"
            self.status = f"{moving['name']} 已移动，轮到{'红' if self.turn == 'red' else '黑'}方"
        self.revision += 1

    def undo(self) -> None:
        if not self.history:
            raise GameError("当前没有可悔的棋")
        snapshot = self.history.pop()
        self.board = snapshot["board"]
        self.captured = snapshot["captured"]
        self.turn = snapshot["turn"]
        self.winner = snapshot["winner"]
        self.status = "双方已同意悔棋"
        self.revision += 1

    def public_state(self) -> dict[str, Any]:
        pieces = []
        for (row, col), piece in sorted(self.board.items()):
            item = {
                "row": row,
                "col": col,
                "revealed": piece["revealed"],
                "control_side": piece["control_side"],
            }
            if piece["revealed"]:
                item.update(name=piece["name"], color=piece["color"])
            pieces.append(item)
        return {
            "pieces": pieces,
            "captured": [
                {"name": p["name"], "color": p["color"]} for p in self.captured
            ],
            "turn": self.turn,
            "winner": self.winner,
            "status": self.status,
            "can_undo": bool(self.history),
            "revision": self.revision,
        }
