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
    """Complete private game state."""

    board: dict[Position, dict[str, Any]] = field(default_factory=dict)
    captured: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    turn: str = "red"
    winner: str | None = None
    status: str = "等待黑方玩家加入"
    revision: int = 0

    # 上一手棋
    last_move: dict[str, Any] | None = None

    # True：暗棋被吃后，只允许吃子方知道身份
    # False：双方都能看到
    hide_captured_dark: bool = False

    def __post_init__(self) -> None:
        if not self.board:
            self.reset()

    # =========================================================
    # 初始化
    # =========================================================

    def reset(self) -> None:
        self.board = {}
        self.captured = []
        self.history = []

        self.turn = "red"
        self.winner = None
        self.status = "红方先行"
        self.last_move = None

        self.revision += 1

        shuffled: list[dict[str, Any]] = []

        for name in [
            "車", "馬", "象", "士", "士", "象", "馬", "車",
            "砲", "砲",
            "卒", "卒", "卒", "卒", "卒",
        ]:
            shuffled.append({
                "name": name,
                "color": "black",
                "revealed": False,
            })

        for name in [
            "俥", "傌", "相", "仕", "仕", "相", "傌", "俥",
            "炮", "炮",
            "兵", "兵", "兵", "兵", "兵",
        ]:
            shuffled.append({
                "name": name,
                "color": "red",
                "revealed": False,
            })

        secrets.SystemRandom().shuffle(shuffled)

        # 将帅固定明牌
        self.board[(0, 4)] = self._piece(
            "將", "black", "king", "black", True
        )

        self.board[(9, 4)] = self._piece(
            "帥", "red", "king", "red", True
        )

        positions: list[tuple[int, int, str, str]] = []

        back_row = [
            "rook",
            "horse",
            "elephant",
            "advisor",
            "king",
            "advisor",
            "elephant",
            "horse",
            "rook",
        ]

        for col in range(9):
            if col != 4:
                positions.append(
                    (0, col, back_row[col], "black")
                )
                positions.append(
                    (9, col, back_row[col], "red")
                )

        for col in (1, 7):
            positions.append(
                (2, col, "cannon", "black")
            )
            positions.append(
                (7, col, "cannon", "red")
            )

        for col in (0, 2, 4, 6, 8):
            positions.append(
                (3, col, "pawn", "black")
            )
            positions.append(
                (6, col, "pawn", "red")
            )

        for (
            row,
            col,
            hidden_type,
            control_side,
        ), piece in zip(positions, shuffled):

            piece["hidden_type"] = hidden_type
            piece["control_side"] = control_side

            self.board[(row, col)] = piece

    @staticmethod
    def _piece(
        name: str,
        color: str,
        hidden_type: str,
        control_side: str,
        revealed: bool,
    ) -> dict[str, Any]:

        return {
            "name": name,
            "color": color,
            "revealed": revealed,
            "hidden_type": hidden_type,
            "control_side": control_side,
        }

    # =========================================================
    # 当前身份 / 控制方
    # =========================================================

    def active_type(
        self,
        piece: dict[str, Any],
    ) -> str:
        """
        暗棋按初始位置原来的棋种走。
        明棋按真实棋种走。
        """

        if piece["revealed"]:
            return PIECE_TYPES[piece["name"]]

        return piece["hidden_type"]

    def movement_side(
        self,
        piece: dict[str, Any],
    ) -> str:
        """
        暗棋按初始位置阵营判断兵卒方向等。
        明棋按真实颜色判断。
        """

        if piece["revealed"]:
            return piece["color"]

        return piece["control_side"]

    def controller_side(
        self,
        piece: dict[str, Any],
    ) -> str:
        """
        暗棋：由初始位置一方控制。
        明棋：由真实颜色一方控制。
        """

        if piece["revealed"]:
            return piece["color"]

        return piece["control_side"]

    # =========================================================
    # 棋盘工具
    # =========================================================

    @staticmethod
    def in_bounds(pos: Position) -> bool:
        return (
            0 <= pos[0] <= 9
            and 0 <= pos[1] <= 8
        )

    @staticmethod
    def in_palace(
        row: int,
        col: int,
        side: str,
    ) -> bool:

        if not 3 <= col <= 5:
            return False

        if side == "black":
            return 0 <= row <= 2

        return 7 <= row <= 9

    @staticmethod
    def crossed_river(
        row: int,
        side: str,
    ) -> bool:

        if side == "black":
            return row >= 5

        return row <= 4

    def count_between(
        self,
        start: Position,
        end: Position,
    ) -> int:

        r1, c1 = start
        r2, c2 = end

        if r1 == r2:
            step = 1 if c2 > c1 else -1

            return sum(
                (r1, col) in self.board
                for col in range(
                    c1 + step,
                    c2,
                    step,
                )
            )

        if c1 == c2:
            step = 1 if r2 > r1 else -1

            return sum(
                (row, c1) in self.board
                for row in range(
                    r1 + step,
                    r2,
                    step,
                )
            )

        return 0

    # =========================================================
    # 吃子规则
    # =========================================================

    def can_capture(
        self,
        piece: dict[str, Any],
        target: dict[str, Any],
    ) -> bool:

        moving_revealed = piece["revealed"]
        target_revealed = target["revealed"]

        # 明棋可以吃任何暗棋
        if moving_revealed and not target_revealed:
            return True

        # 暗棋不能吃同一初始阵营的暗棋
        if not moving_revealed and not target_revealed:
            return (
                piece["control_side"]
                != target["control_side"]
            )

        # 明棋 -> 明棋
        # 暗棋 -> 明棋
        # 按当前实际归属判断
        return (
            self.controller_side(piece)
            != self.controller_side(target)
        )

    # =========================================================
    # 行棋规则
    # =========================================================

    def is_valid_move(
        self,
        start: Position,
        end: Position,
    ) -> bool:

        if start not in self.board:
            return False

        if start == end:
            return False

        if not self.in_bounds(end):
            return False

        piece = self.board[start]
        target = self.board.get(end)

        if target is not None:
            if not self.can_capture(piece, target):
                return False

        piece_type = self.active_type(piece)
        side = self.movement_side(piece)

        r1, c1 = start
        r2, c2 = end

        dr = r2 - r1
        dc = c2 - c1

        ar = abs(dr)
        ac = abs(dc)

        # 車
        if piece_type == "rook":

            if r1 != r2 and c1 != c2:
                return False

            return (
                self.count_between(start, end)
                == 0
            )

        # 馬
        if piece_type == "horse":

            if (ar, ac) not in (
                (2, 1),
                (1, 2),
            ):
                return False

            if ar == 2:
                leg = (
                    r1 + dr // 2,
                    c1,
                )
            else:
                leg = (
                    r1,
                    c1 + dc // 2,
                )

            return leg not in self.board

        # 象 / 相
        # 可以过河，但不能塞象眼
        if piece_type == "elephant":

            if ar != 2 or ac != 2:
                return False

            eye = (
                r1 + dr // 2,
                c1 + dc // 2,
            )

            return eye not in self.board

        # 士 / 仕
        # 不限制九宫格
        if piece_type == "advisor":

            return (
                ar == 1
                and ac == 1
            )

        # 将 / 帅
        if piece_type == "king":

            # 飞将
            if target is not None:

                if (
                    self.active_type(target)
                    == "king"
                    and self.controller_side(target)
                    != self.controller_side(piece)
                    and c1 == c2
                    and self.count_between(
                        start,
                        end,
                    ) == 0
                ):
                    return True

            if ar + ac != 1:
                return False

            return self.in_palace(
                r2,
                c2,
                side,
            )

        # 炮
        if piece_type == "cannon":

            if r1 != r2 and c1 != c2:
                return False

            between = self.count_between(
                start,
                end,
            )

            if target is not None:
                return between == 1

            return between == 0

        # 兵 / 卒
        if piece_type == "pawn":

            forward = (
                1
                if side == "black"
                else -1
            )

            if (
                dr == forward
                and dc == 0
            ):
                return True

            if self.crossed_river(
                r1,
                side,
            ):
                if (
                    dr == 0
                    and ac == 1
                ):
                    return True

            return False

        return False

    # =========================================================
    # 将军检测
    # =========================================================

    def find_king(
        self,
        side: str,
    ) -> Position | None:

        for pos, piece in self.board.items():

            if not piece["revealed"]:
                continue

            if (
                PIECE_TYPES.get(piece["name"])
                != "king"
            ):
                continue

            if (
                self.controller_side(piece)
                == side
            ):
                return pos

        return None

    def is_in_check(
        self,
        side: str,
    ) -> bool:

        king_pos = self.find_king(side)

        if king_pos is None:
            return False

        enemy = (
            "black"
            if side == "red"
            else "red"
        )

        for pos, piece in self.board.items():

            if pos == king_pos:
                continue

            if (
                self.controller_side(piece)
                != enemy
            ):
                continue

            if self.is_valid_move(
                pos,
                king_pos,
            ):
                return True

        return False

    def check_sides(self) -> list[str]:

        result: list[str] = []

        if self.is_in_check("red"):
            result.append("red")

        if self.is_in_check("black"):
            result.append("black")

        return result

    # =========================================================
    # 合法落点
    # =========================================================

    def legal_moves(
        self,
        start: Position,
        side: str,
    ) -> list[list[int]]:

        piece = self.board.get(start)

        if not piece:
            return []

        if (
            self.controller_side(piece)
            != side
        ):
            return []

        if self.turn != side:
            return []

        if self.winner:
            return []

        return [
            [row, col]
            for row in range(10)
            for col in range(9)
            if self.is_valid_move(
                start,
                (row, col),
            )
        ]

    # =========================================================
    # 移动
    # =========================================================

    def move(
        self,
        start: Position,
        end: Position,
        side: str,
    ) -> None:

        if self.winner:
            raise GameError(
                "棋局已经结束"
            )

        if side != self.turn:
            raise GameError(
                "还没轮到你"
            )

        piece = self.board.get(start)

        if not piece:
            raise GameError(
                "该位置没有棋子"
            )

        if (
            self.controller_side(piece)
            != side
        ):
            raise GameError(
                "这不是你控制的棋子"
            )

        if not self.is_valid_move(
            start,
            end,
        ):
            raise GameError(
                "该落点不符合行棋规则"
            )

        self.history.append({
            "board":
                copy.deepcopy(self.board),

            "captured":
                copy.deepcopy(self.captured),

            "turn":
                self.turn,

            "winner":
                self.winner,

            "status":
                self.status,

            "last_move":
                copy.deepcopy(
                    self.last_move
                ),
        })

        captured = self.board.get(end)

        if captured is not None:

            captured_record = copy.deepcopy(captured)

            # 被吃之前是否已经是明棋
            captured_record["was_revealed"] = captured["revealed"]

            # 哪一方吃掉了它
            captured_record["captured_by"] = side

            # 被吃前由哪一方控制。
            # 必须在 revealed 改成 True 之前记录。
            captured_record["captured_from_side"] = (
                self.controller_side(captured)
            )

            # 服务端内部公开真实身份
            captured_record["revealed"] = True

            self.captured.append(captured_record)

        moving = self.board.pop(start)

        # 走过以后翻明
        moving["revealed"] = True

        self.board[end] = moving

        # 上一步位置
        self.last_move = {
            "from": [
                start[0],
                start[1],
            ],
            "to": [
                end[0],
                end[1],
            ],
            "side": side,
        }

        # 吃将帅结束
        if (
            captured is not None
            and PIECE_TYPES.get(
                captured["name"]
            ) == "king"
        ):

            self.winner = side

            self.status = (
                f"{'红' if side == 'red' else '黑'}方获胜"
            )

            self.revision += 1
            return

        self.turn = (
            "black"
            if side == "red"
            else "red"
        )

        checked = self.check_sides()

        if len(checked) == 1:

            checked_name = (
                "红方"
                if checked[0] == "red"
                else "黑方"
            )

            self.status = (
                f"{moving['name']} 已移动，"
                f"{checked_name}被将军！"
                f"轮到"
                f"{'红' if self.turn == 'red' else '黑'}方"
            )

        elif len(checked) == 2:

            self.status = (
                f"{moving['name']} 已移动，"
                f"双方将帅均受到攻击！"
                f"轮到"
                f"{'红' if self.turn == 'red' else '黑'}方"
            )

        else:

            self.status = (
                f"{moving['name']} 已移动，"
                f"轮到"
                f"{'红' if self.turn == 'red' else '黑'}方"
            )

        self.revision += 1

    # =========================================================
    # 悔棋
    # =========================================================

    def undo(self) -> None:

        if not self.history:
            raise GameError(
                "当前没有可悔的棋"
            )

        snapshot = self.history.pop()

        self.board = snapshot["board"]
        self.captured = snapshot["captured"]
        self.turn = snapshot["turn"]
        self.winner = snapshot["winner"]

        self.last_move = snapshot.get(
            "last_move"
        )

        self.status = (
            "双方已同意悔棋"
        )

        self.revision += 1

    # =========================================================
    # 设置
    # =========================================================

    def set_hide_captured_dark(
        self,
        enabled: bool,
    ) -> None:

        self.hide_captured_dark = bool(
            enabled
        )

        self.revision += 1

    # =========================================================
    # 被吃棋子：按照观看者过滤
    # =========================================================

    def public_captured(
        self,
        viewer_side: str | None,
    ) -> list[dict[str, Any]]:

        result: list[dict[str, Any]] = []

        for piece in self.captured:

            was_revealed = piece.get(
                "was_revealed",
                True,
            )

            captured_by = piece.get(
                "captured_by"
            )

            captured_from_side = piece.get(
                "captured_from_side",
                piece.get("color"),
            )

            # 被吃前本来就是明棋：双方都可见
            if was_revealed:
                result.append({
                    "name": piece["name"],
                    "color": piece["color"],
                    "hidden": False,
                    "captured_from_side": captured_from_side,
                })
                continue

            # 关闭暗棋保密：双方都可见
            if not self.hide_captured_dark:
                result.append({
                    "name": piece["name"],
                    "color": piece["color"],
                    "hidden": False,
                    "captured_from_side": captured_from_side,
                })
                continue

            # 开启保密：吃子方可以看到真实身份
            if (
                viewer_side is not None
                and captured_by == viewer_side
            ):
                result.append({
                    "name": piece["name"],
                    "color": piece["color"],
                    "hidden": False,
                    "captured_from_side": captured_from_side,
                })

            # 对手只能知道有一枚暗棋被吃，
            # 绝不能收到 name/color
            else:
                result.append({
                    "hidden": True,
                    "captured_from_side": captured_from_side,
                })

        return result

    # =========================================================
    # 对客户端公开状态
    # =========================================================

    def public_state(
        self,
        viewer_side: str | None = None,
    ) -> dict[str, Any]:

        pieces = []

        for (
            row,
            col,
        ), piece in sorted(
            self.board.items()
        ):

            item = {
                "row":
                    row,

                "col":
                    col,

                "revealed":
                    piece["revealed"],

                # 当前控制权
                "control_side":
                    self.controller_side(
                        piece
                    ),
            }

            # 暗棋绝不泄露真实身份
            if piece["revealed"]:

                item.update(
                    name=
                        piece["name"],

                    color=
                        piece["color"],
                )

            pieces.append(item)

        checked = self.check_sides()

        return {
            "pieces":
                pieces,

            "captured":
                self.public_captured(
                    viewer_side
                ),

            "turn":
                self.turn,

            "winner":
                self.winner,

            "status":
                self.status,

            "can_undo":
                bool(self.history),

            "revision":
                self.revision,

            "last_move":
                copy.deepcopy(
                    self.last_move
                ),

            "check": {
                "red":
                    "red" in checked,

                "black":
                    "black" in checked,
            },

            "settings": {
                "hide_captured_dark":
                    self.hide_captured_dark,
            },
        }
