import unittest

import app as webapp


class SocketFlowTest(unittest.TestCase):
    def setUp(self):
        webapp.rooms.clear()
        webapp.app.config["TESTING"] = True
        self.red = webapp.socketio.test_client(webapp.app)
        self.black = webapp.socketio.test_client(webapp.app)

    def tearDown(self):
        if self.red.is_connected():
            self.red.disconnect()
        if self.black.is_connected():
            self.black.disconnect()

    @staticmethod
    def event(client, name):
        matches = [x for x in client.get_received() if x["name"] == name]
        return matches[-1]["args"][0] if matches else None

    def create_and_join(self):
        self.red.emit("create_room", {"name": "红方"})
        red_session = self.event(self.red, "session")
        self.black.emit("join_room", {"name": "黑方", "room": red_session["room"]})
        black_session = self.event(self.black, "session")
        self.red.get_received(); self.black.get_received()
        return red_session, black_session

    def test_two_players_join_and_hidden_identity_is_not_leaked(self):
        red, _ = self.create_and_join()
        room = webapp.rooms[red["room"]]
        state = room.public_state()
        self.assertTrue(state["ready"])
        hidden = [p for p in state["pieces"] if not p["revealed"]]
        self.assertTrue(hidden)
        self.assertTrue(all("name" not in p and "color" not in p for p in hidden))

    def test_move_broadcast_and_mutual_undo(self):
        red, black = self.create_and_join()
        room = webapp.rooms[red["room"]]
        start = next(pos for pos, p in room.game.board.items()
                     if p["control_side"] == "red" and room.game.legal_moves(pos, "red"))
        end = room.game.legal_moves(start, "red")[0]
        self.red.emit("move_piece", {**red, "start": list(start), "end": end})
        moved = self.event(self.red, "game_state")
        self.assertEqual("black", moved["turn"])
        self.red.emit("request_action", {**red, "kind": "undo"})
        self.red.get_received(); self.black.get_received()
        self.black.emit("respond_action", {**black, "accepted": True})
        restored = self.event(self.red, "game_state")
        self.assertEqual("red", restored["turn"])
        self.assertFalse(restored["can_undo"])

    def test_disconnect_and_token_reconnect(self):
        red, _ = self.create_and_join()
        room_code = red["room"]
        self.red.disconnect()
        replacement = webapp.socketio.test_client(webapp.app)
        replacement.emit("resume_session", {"room": room_code, "token": red["token"]})
        resumed = self.event(replacement, "session")
        self.assertTrue(resumed["resumed"])
        self.assertTrue(webapp.rooms[room_code].players["red"].connected)
        replacement.disconnect()

    def test_restart_requires_opponent_acceptance(self):
        red, black = self.create_and_join()
        room = webapp.rooms[red["room"]]
        original_revision = room.game.revision
        self.red.emit("request_action", {**red, "kind": "restart"})
        self.assertIsNotNone(room.proposal)
        self.assertEqual(original_revision + 1, room.game.revision)
        self.black.emit("respond_action", {**black, "accepted": True})
        restarted = self.event(self.black, "game_state")
        self.assertEqual("red", restarted["turn"])
        self.assertEqual(32, len(restarted["pieces"]))
        self.assertIsNone(room.proposal)


if __name__ == "__main__":
    unittest.main()
