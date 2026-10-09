import unittest

from game import Game, GameError


def piece(name, color, kind, controller, revealed=True):
    return {"name": name, "color": color, "hidden_type": kind,
            "control_side": controller, "revealed": revealed}


class GameRulesTest(unittest.TestCase):
    def setUp(self):
        self.game = Game()

    def test_setup_has_32_pieces_and_hides_30_identities(self):
        public = self.game.public_state()
        self.assertEqual(32, len(public["pieces"]))
        hidden = [p for p in public["pieces"] if not p["revealed"]]
        self.assertEqual(30, len(hidden))
        self.assertTrue(all("name" not in p and "color" not in p for p in hidden))

    def test_dark_piece_uses_initial_rule_then_reveals(self):
        self.game.board = {
            (9, 0): piece("兵", "red", "rook", "red", False),
            (0, 4): piece("將", "black", "king", "black"),
            (9, 4): piece("帥", "red", "king", "red"),
        }
        self.assertTrue(self.game.is_valid_move((9, 0), (5, 0)))
        self.game.move((9, 0), (5, 0), "red")
        self.assertTrue(self.game.board[(5, 0)]["revealed"])
        self.assertFalse(self.game.is_valid_move((5, 0), (3, 0)))

    def test_revealed_piece_keeps_original_controller(self):
        self.game.board = {
            (9, 0): piece("卒", "black", "rook", "red", True),
            (0, 4): piece("將", "black", "king", "black"),
            (9, 4): piece("帥", "red", "king", "red"),
        }
        self.assertTrue(self.game.legal_moves((9, 0), "red"))
        self.assertEqual([], self.game.legal_moves((9, 0), "black"))

    def test_advisor_can_leave_palace_and_elephant_can_cross_river(self):
        self.game.board = {
            (5, 4): piece("仕", "red", "advisor", "red"),
            (6, 0): piece("相", "red", "elephant", "red"),
        }
        self.assertTrue(self.game.is_valid_move((5, 4), (4, 5)))
        self.assertTrue(self.game.is_valid_move((6, 0), (4, 2)))

    def test_horse_leg_and_elephant_eye_blocking(self):
        blocker = piece("兵", "red", "pawn", "red")
        self.game.board = {(5, 4): piece("傌", "red", "horse", "red"), (4, 4): blocker}
        self.assertFalse(self.game.is_valid_move((5, 4), (3, 5)))
        self.game.board = {(6, 0): piece("相", "red", "elephant", "red"), (5, 1): blocker}
        self.assertFalse(self.game.is_valid_move((6, 0), (4, 2)))

    def test_cannon_requires_exactly_one_screen_when_capturing(self):
        self.game.board = {
            (7, 1): piece("炮", "red", "cannon", "red"),
            (5, 1): piece("兵", "red", "pawn", "red"),
            (2, 1): piece("車", "black", "rook", "black"),
        }
        self.assertTrue(self.game.is_valid_move((7, 1), (2, 1)))
        self.game.board[(4, 1)] = piece("卒", "black", "pawn", "black")
        self.assertFalse(self.game.is_valid_move((7, 1), (2, 1)))

    def test_cannot_capture_piece_with_same_controller(self):
        self.game.board = {
            (5, 0): piece("俥", "red", "rook", "red"),
            (5, 2): piece("卒", "black", "pawn", "red"),
        }
        self.assertFalse(self.game.is_valid_move((5, 0), (5, 2)))

    def test_capture_reveals_identity_and_undo_restores_dark_state(self):
        self.game.board = {
            (5, 0): piece("車", "black", "rook", "red", False),
            (5, 2): piece("兵", "red", "pawn", "black", False),
        }
        self.game.move((5, 0), (5, 2), "red")
        self.assertEqual("兵", self.game.captured[0]["name"])
        self.assertTrue(self.game.captured[0]["revealed"])
        self.game.undo()
        self.assertFalse(self.game.board[(5, 0)]["revealed"])
        self.assertFalse(self.game.board[(5, 2)]["revealed"])
        self.assertEqual([], self.game.captured)

    def test_wrong_turn_is_rejected(self):
        with self.assertRaisesRegex(GameError, "还没轮到你"):
            self.game.move((0, 0), (1, 0), "black")


if __name__ == "__main__":
    unittest.main()
