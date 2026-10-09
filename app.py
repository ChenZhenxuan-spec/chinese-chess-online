"""Flask-SocketIO entry point for the two-player web game."""

from __future__ import annotations

import os
import re
import secrets
import threading
from dataclasses import dataclass, field
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit, join_room as socket_join_room

from game import Game, GameError


# =========================================================
# Flask / Socket.IO
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    secrets.token_hex(32),
)

socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins=None,
)


# =========================================================
# 玩家
# =========================================================

@dataclass
class Player:
    name: str
    token: str
    side: str

    sid: str | None = None
    connected: bool = False


# =========================================================
# 房间
# =========================================================

@dataclass
class Room:
    code: str

    game: Game = field(
        default_factory=Game
    )

    players: dict[str, Player] = field(
        default_factory=dict
    )

    proposal: dict[str, Any] | None = None

    def player_by_token(
        self,
        token: str,
    ) -> Player | None:

        return next(
            (
                player
                for player
                in self.players.values()
                if secrets.compare_digest(
                    player.token,
                    token,
                )
            ),
            None,
        )

    def player_by_sid(
        self,
        sid: str,
    ) -> Player | None:

        return next(
            (
                player
                for player
                in self.players.values()
                if player.sid == sid
            ),
            None,
        )

    def public_state(
        self,
        viewer_side: str | None = None,
    ) -> dict[str, Any]:
        """
        根据观看者身份生成状态。

        这一点非常重要：
        红方和黑方可能收到不同的 captured 数据，
        从服务端层面避免被吃暗棋身份泄露。
        """

        state = self.game.public_state(
            viewer_side
        )

        state.update({
            "room":
                self.code,

            "ready":
                len(self.players) == 2,

            "players": {
                side: {
                    "name":
                        player.name,

                    "connected":
                        player.connected,
                }
                for side, player
                in self.players.items()
            },

            "proposal": (
                {
                    "kind":
                        self.proposal["kind"],

                    "by":
                        self.proposal["by"],
                }
                if self.proposal
                else None
            ),
        })

        return state


# =========================================================
# 全局房间
# =========================================================

rooms: dict[str, Room] = {}

rooms_lock = threading.RLock()


# =========================================================
# 工具函数
# =========================================================

def clean_name(
    value: Any,
) -> str:

    name = re.sub(
        r"\s+",
        " ",
        str(value or "").strip(),
    )[:16]

    if not name:
        raise GameError(
            "请输入昵称"
        )

    return name


def new_room_code() -> str:

    for _ in range(100):

        code = (
            f"{secrets.randbelow(1_000_000):06d}"
        )

        if code not in rooms:
            return code

    raise GameError(
        "暂时无法创建房间，请稍后重试"
    )


def current_room_player(
    data: dict[str, Any] | None = None,
) -> tuple[Room, Player]:

    data = data or {}

    code = str(
        data.get("room", "")
    ).strip()

    token = str(
        data.get("token", "")
    )

    room = rooms.get(code)

    player = (
        room.player_by_token(token)
        if room and token
        else None
    )

    if (
        not room
        or not player
        or player.sid != request.sid
    ):
        raise GameError(
            "登录状态已失效，请重新进入房间"
        )

    return room, player


def broadcast_state(
    room: Room,
) -> None:
    """
    不再把同一份状态广播给整个房间。

    红方：
        game.public_state("red")

    黑方：
        game.public_state("black")

    这样在“隐藏被吃暗棋身份”模式下，
    对手从 WebSocket 数据中也看不到真实身份。
    """

    for side, player in room.players.items():

        if (
            not player.connected
            or not player.sid
        ):
            continue

        state = room.public_state(
            viewer_side=side
        )

        socketio.emit(
            "game_state",
            state,
            to=player.sid,
        )


def send_error(
    message: str,
) -> None:

    emit(
        "server_error",
        {
            "message":
                message,
        },
    )


# =========================================================
# HTTP
# =========================================================

@app.get("/")
def index():
    return render_template(
        "index.html"
    )


@app.get("/health")
def health():

    return jsonify(
        status="ok",
        rooms=len(rooms),
    )


# =========================================================
# 创建房间
# =========================================================

@socketio.on("create_room")
def on_create_room(data):

    try:

        with rooms_lock:

            name = clean_name(
                (data or {}).get("name")
            )

            room = Room(
                new_room_code()
            )

            player = Player(
                name=name,
                token=secrets.token_urlsafe(32),
                side="red",
                sid=request.sid,
                connected=True,
            )

            room.players["red"] = player

            rooms[room.code] = room

            socket_join_room(
                room.code
            )

            emit(
                "session",
                {
                    "room":
                        room.code,

                    "token":
                        player.token,

                    "side":
                        player.side,

                    "name":
                        player.name,
                },
            )

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 加入房间
# =========================================================

@socketio.on("join_room")
def on_join_room(data):

    try:

        with rooms_lock:

            name = clean_name(
                (data or {}).get("name")
            )

            code = str(
                (data or {}).get(
                    "room",
                    "",
                )
            ).strip()

            room = rooms.get(code)

            if not room:
                raise GameError(
                    "房间不存在，请检查房间号"
                )

            if len(room.players) >= 2:
                raise GameError(
                    "房间已有两名玩家"
                )

            player = Player(
                name=name,
                token=secrets.token_urlsafe(32),
                side="black",
                sid=request.sid,
                connected=True,
            )

            room.players["black"] = player

            socket_join_room(
                room.code
            )

            emit(
                "session",
                {
                    "room":
                        room.code,

                    "token":
                        player.token,

                    "side":
                        player.side,

                    "name":
                        player.name,
                },
            )

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 刷新 / 断线重新连接
# =========================================================

@socketio.on("resume_session")
def on_resume(data):

    try:

        with rooms_lock:

            code = str(
                (data or {}).get(
                    "room",
                    "",
                )
            ).strip()

            token = str(
                (data or {}).get(
                    "token",
                    "",
                )
            )

            room = rooms.get(code)

            player = (
                room.player_by_token(token)
                if room
                else None
            )

            if not player:
                raise GameError(
                    "原房间已失效"
                )

            player.sid = request.sid
            player.connected = True

            socket_join_room(
                room.code
            )

            emit(
                "session",
                {
                    "room":
                        room.code,

                    "token":
                        player.token,

                    "side":
                        player.side,

                    "name":
                        player.name,

                    "resumed":
                        True,
                },
            )

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 选择棋子
# =========================================================

@socketio.on("select_piece")
def on_select_piece(data):

    try:

        with rooms_lock:

            room, player = (
                current_room_player(
                    data
                )
            )

            if len(room.players) < 2:
                raise GameError(
                    "请等待另一名玩家加入"
                )

            start = (
                int(data["row"]),
                int(data["col"]),
            )

            piece = room.game.board.get(
                start
            )

            if not piece:
                raise GameError(
                    "该位置没有棋子"
                )

            # -------------------------------------------------
            # 关键修复
            #
            # 原来：
            # piece["control_side"]
            #
            # 现在：
            # 暗棋按初始阵营
            # 明棋按真实颜色
            # -------------------------------------------------

            if (
                room.game.controller_side(
                    piece
                )
                != player.side
            ):
                raise GameError(
                    "这不是你控制的棋子"
                )

            if (
                room.game.turn
                != player.side
            ):
                raise GameError(
                    "还没轮到你"
                )

            moves = (
                room.game.legal_moves(
                    start,
                    player.side,
                )
            )

            emit(
                "legal_moves",
                {
                    "start":
                        list(start),

                    "moves":
                        moves,

                    "revision":
                        room.game.revision,
                },
            )

    except (
        GameError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:

        send_error(
            str(exc)
            if isinstance(
                exc,
                GameError,
            )
            else "坐标无效"
        )


# =========================================================
# 移动棋子
# =========================================================

@socketio.on("move_piece")
def on_move_piece(data):

    try:

        with rooms_lock:

            room, player = (
                current_room_player(
                    data
                )
            )

            if len(room.players) < 2:
                raise GameError(
                    "请等待另一名玩家加入"
                )

            start = tuple(
                map(
                    int,
                    data["start"],
                )
            )

            end = tuple(
                map(
                    int,
                    data["end"],
                )
            )

            if (
                len(start) != 2
                or len(end) != 2
            ):
                raise GameError(
                    "坐标无效"
                )

            room.game.move(
                start,
                end,
                player.side,
            )

            # 有人走棋后，
            # 取消尚未完成的悔棋/重开协商
            room.proposal = None

            broadcast_state(
                room
            )

    except (
        GameError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:

        send_error(
            str(exc)
            if isinstance(
                exc,
                GameError,
            )
            else "坐标无效"
        )


# =========================================================
# 设置：
# 是否隐藏被吃暗棋身份
# =========================================================

@socketio.on("set_hide_captured_dark")
def on_set_hide_captured_dark(data):
    """
    红方为房主。

    enabled = True：
        暗棋被吃以后只有吃子方知道真实身份。

    enabled = False：
        双方都能看到被吃暗棋真实身份。
    """

    try:

        with rooms_lock:

            room, player = (
                current_room_player(
                    data
                )
            )

            # 当前设定：
            # 只有房主（红方）可以切换
            if player.side != "red":
                raise GameError(
                    "只有房主可以修改该设置"
                )

            enabled = (
                (data or {}).get(
                    "enabled"
                )
            )

            if not isinstance(
                enabled,
                bool,
            ):
                raise GameError(
                    "设置参数无效"
                )

            room.game.set_hide_captured_dark(
                enabled
            )

            if enabled:
                room.game.status = (
                    "已开启：被吃暗棋身份仅吃子方可见"
                )
            else:
                room.game.status = (
                    "已关闭：被吃暗棋身份双方可见"
                )

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 发起悔棋 / 重开
# =========================================================

@socketio.on("request_action")
def on_request_action(data):

    try:

        with rooms_lock:

            room, player = (
                current_room_player(
                    data
                )
            )

            kind = str(
                data.get(
                    "kind",
                    "",
                )
            )

            if kind not in (
                "undo",
                "restart",
            ):
                raise GameError(
                    "未知操作"
                )

            if len(room.players) < 2:
                raise GameError(
                    "请等待另一名玩家加入"
                )

            if not all(
                player.connected
                for player
                in room.players.values()
            ):
                raise GameError(
                    "对方离线，暂时无法发起协商"
                )

            if (
                kind == "undo"
                and not room.game.history
            ):
                raise GameError(
                    "当前没有可悔的棋"
                )

            if room.proposal:
                raise GameError(
                    "已有一个待处理请求"
                )

            room.proposal = {
                "kind":
                    kind,

                "by":
                    player.side,
            }

            side_name = (
                "红方"
                if player.side == "red"
                else "黑方"
            )

            action_name = (
                "悔棋"
                if kind == "undo"
                else "重新开局"
            )

            room.game.status = (
                f"{side_name}请求"
                f"{action_name}，"
                f"等待对方回应"
            )

            room.game.revision += 1

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 回应悔棋 / 重开
# =========================================================

@socketio.on("respond_action")
def on_respond_action(data):

    try:

        with rooms_lock:

            room, player = (
                current_room_player(
                    data
                )
            )

            proposal = room.proposal

            if (
                not proposal
                or proposal["by"]
                == player.side
            ):
                raise GameError(
                    "没有需要你处理的请求"
                )

            accepted = bool(
                data.get(
                    "accepted"
                )
            )

            kind = proposal["kind"]

            room.proposal = None

            if accepted:

                if kind == "undo":

                    room.game.undo()

                else:

                    # reset() 不会修改
                    # hide_captured_dark，
                    # 因此房间设置继续保留
                    room.game.reset()

            else:

                if kind == "undo":

                    room.game.status = (
                        "对方拒绝了悔棋请求"
                    )

                else:

                    room.game.status = (
                        "对方拒绝了重新开局"
                    )

                room.game.revision += 1

            broadcast_state(
                room
            )

    except GameError as exc:

        send_error(
            str(exc)
        )


# =========================================================
# 断线
# =========================================================

@socketio.on("disconnect")
def on_disconnect():

    with rooms_lock:

        for room in rooms.values():

            player = room.player_by_sid(
                request.sid
            )

            if player:

                player.connected = False
                player.sid = None

                broadcast_state(
                    room
                )

                break


# =========================================================
# 本地启动
# =========================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5000",
        )
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        allow_unsafe_werkzeug=True,
    )