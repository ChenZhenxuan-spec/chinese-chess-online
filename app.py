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


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins=None)


@dataclass
class Player:
    name: str
    token: str
    side: str
    sid: str | None = None
    connected: bool = False


@dataclass
class Room:
    code: str
    game: Game = field(default_factory=Game)
    players: dict[str, Player] = field(default_factory=dict)
    proposal: dict[str, Any] | None = None

    def player_by_token(self, token: str) -> Player | None:
        return next((p for p in self.players.values() if secrets.compare_digest(p.token, token)), None)

    def player_by_sid(self, sid: str) -> Player | None:
        return next((p for p in self.players.values() if p.sid == sid), None)

    def public_state(self) -> dict[str, Any]:
        state = self.game.public_state()
        state.update({
            "room": self.code,
            "ready": len(self.players) == 2,
            "players": {
                side: {"name": p.name, "connected": p.connected}
                for side, p in self.players.items()
            },
            "proposal": ({"kind": self.proposal["kind"], "by": self.proposal["by"]}
                         if self.proposal else None),
        })
        return state


rooms: dict[str, Room] = {}
rooms_lock = threading.RLock()


def clean_name(value: Any) -> str:
    name = re.sub(r"\s+", " ", str(value or "").strip())[:16]
    if not name:
        raise GameError("请输入昵称")
    return name


def new_room_code() -> str:
    for _ in range(100):
        code = f"{secrets.randbelow(1_000_000):06d}"
        if code not in rooms:
            return code
    raise GameError("暂时无法创建房间，请稍后重试")


def current_room_player(data: dict[str, Any] | None = None) -> tuple[Room, Player]:
    data = data or {}
    code = str(data.get("room", "")).strip()
    token = str(data.get("token", ""))
    room = rooms.get(code)
    player = room.player_by_token(token) if room and token else None
    if not room or not player or player.sid != request.sid:
        raise GameError("登录状态已失效，请重新进入房间")
    return room, player


def broadcast_state(room: Room) -> None:
    socketio.emit("game_state", room.public_state(), to=room.code)


def send_error(message: str) -> None:
    emit("server_error", {"message": message})


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify(status="ok", rooms=len(rooms))


@socketio.on("create_room")
def on_create_room(data):
    try:
        with rooms_lock:
            name = clean_name((data or {}).get("name"))
            room = Room(new_room_code())
            player = Player(name, secrets.token_urlsafe(32), "red", request.sid, True)
            room.players["red"] = player
            rooms[room.code] = room
            socket_join_room(room.code)
            emit("session", {"room": room.code, "token": player.token,
                             "side": player.side, "name": player.name})
            broadcast_state(room)
    except GameError as exc:
        send_error(str(exc))


@socketio.on("join_room")
def on_join_room(data):
    try:
        with rooms_lock:
            name = clean_name((data or {}).get("name"))
            code = str((data or {}).get("room", "")).strip()
            room = rooms.get(code)
            if not room:
                raise GameError("房间不存在，请检查房间号")
            if len(room.players) >= 2:
                raise GameError("房间已有两名玩家")
            player = Player(name, secrets.token_urlsafe(32), "black", request.sid, True)
            room.players["black"] = player
            socket_join_room(room.code)
            emit("session", {"room": room.code, "token": player.token,
                             "side": player.side, "name": player.name})
            broadcast_state(room)
    except GameError as exc:
        send_error(str(exc))


@socketio.on("resume_session")
def on_resume(data):
    try:
        with rooms_lock:
            code = str((data or {}).get("room", "")).strip()
            token = str((data or {}).get("token", ""))
            room = rooms.get(code)
            player = room.player_by_token(token) if room else None
            if not player:
                raise GameError("原房间已失效")
            player.sid = request.sid
            player.connected = True
            socket_join_room(room.code)
            emit("session", {"room": room.code, "token": player.token,
                             "side": player.side, "name": player.name, "resumed": True})
            broadcast_state(room)
    except GameError as exc:
        send_error(str(exc))


@socketio.on("select_piece")
def on_select_piece(data):
    try:
        with rooms_lock:
            room, player = current_room_player(data)
            if len(room.players) < 2:
                raise GameError("请等待另一名玩家加入")
            start = (int(data["row"]), int(data["col"]))
            moves = room.game.legal_moves(start, player.side)
            piece = room.game.board.get(start)
            if not piece or piece["control_side"] != player.side:
                raise GameError("这不是你控制的棋子")
            if room.game.turn != player.side:
                raise GameError("还没轮到你")
            emit("legal_moves", {"start": list(start), "moves": moves,
                                 "revision": room.game.revision})
    except (GameError, KeyError, TypeError, ValueError) as exc:
        send_error(str(exc) if isinstance(exc, GameError) else "坐标无效")


@socketio.on("move_piece")
def on_move_piece(data):
    try:
        with rooms_lock:
            room, player = current_room_player(data)
            if len(room.players) < 2:
                raise GameError("请等待另一名玩家加入")
            start = tuple(map(int, data["start"]))
            end = tuple(map(int, data["end"]))
            if len(start) != 2 or len(end) != 2:
                raise GameError("坐标无效")
            room.game.move(start, end, player.side)
            room.proposal = None
            broadcast_state(room)
    except (GameError, KeyError, TypeError, ValueError) as exc:
        send_error(str(exc) if isinstance(exc, GameError) else "坐标无效")


@socketio.on("request_action")
def on_request_action(data):
    try:
        with rooms_lock:
            room, player = current_room_player(data)
            kind = str(data.get("kind", ""))
            if kind not in ("undo", "restart"):
                raise GameError("未知操作")
            if len(room.players) < 2:
                raise GameError("请等待另一名玩家加入")
            if not all(p.connected for p in room.players.values()):
                raise GameError("对方离线，暂时无法发起协商")
            if kind == "undo" and not room.game.history:
                raise GameError("当前没有可悔的棋")
            if room.proposal:
                raise GameError("已有一个待处理请求")
            room.proposal = {"kind": kind, "by": player.side}
            side_name = "红方" if player.side == "red" else "黑方"
            action_name = "悔棋" if kind == "undo" else "重新开局"
            room.game.status = f"{side_name}请求{action_name}，等待对方回应"
            room.game.revision += 1
            broadcast_state(room)
    except GameError as exc:
        send_error(str(exc))


@socketio.on("respond_action")
def on_respond_action(data):
    try:
        with rooms_lock:
            room, player = current_room_player(data)
            proposal = room.proposal
            if not proposal or proposal["by"] == player.side:
                raise GameError("没有需要你处理的请求")
            accepted = bool(data.get("accepted"))
            kind = proposal["kind"]
            room.proposal = None
            if accepted:
                room.game.undo() if kind == "undo" else room.game.reset()
            else:
                room.game.status = "对方拒绝了悔棋请求" if kind == "undo" else "对方拒绝了重新开局"
                room.game.revision += 1
            broadcast_state(room)
    except GameError as exc:
        send_error(str(exc))


@socketio.on("disconnect")
def on_disconnect():
    with rooms_lock:
        for room in rooms.values():
            player = room.player_by_sid(request.sid)
            if player:
                player.connected = False
                player.sid = None
                broadcast_state(room)
                break


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
