from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def button(app, label):
    return next(item for item in app.button if item.label == label)


class ChaseAppTests(unittest.TestCase):
    def setUp(self):
        self.mock_path = patch("src.chase_ui.MAP_PATH", ROOT / "data" / "not-present-test.graphml")
        self.mock_path.start()
        self.addCleanup(self.mock_path.stop)
        self.mock_loader_path = patch("src.chase_maps.MAP_PATH", ROOT / "data" / "not-present-test.graphml")
        self.mock_loader_path.start()
        self.addCleanup(self.mock_loader_path.stop)
        from src.chase_ui import cached_arena
        cached_arena.clear()
        self.app = AppTest.from_file(str(ROOT / "chase_app.py"), default_timeout=30).run()

    def test_startup_offline_no_network(self):
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.error)
        self.assertEqual(self.app.session_state["chase_state"].observation.turn, 0)
        self.assertEqual(len(self.app.metric), 4)
        self.assertTrue(button(self.app, "Đi nước này").disabled)

    def test_move_and_restart_clear_history(self):
        app = self.app
        state = app.session_state["chase_state"]
        next(item for item in app.selectbox if item.key == "chase_destination").select(state.runner).run()
        button(app, "Đi nước này").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["chase_state"].observation.turn, 1)
        self.assertEqual(len(app.session_state["chase_history"]), 2)
        button(app, "Bắt đầu ván mới").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.session_state["chase_history"]), 1)
        self.assertEqual(app.session_state["chase_state"].observation.turn, 0)

    def test_settings_apply_only_on_restart(self):
        app = self.app
        next(item for item in app.slider if item.label == "Bạn đi tối đa mỗi lượt (m)").set_value(80)
        app.run()
        self.assertEqual(app.session_state["chase_state"].observation.rules.runner_budget, 160)
        button(app, "Bắt đầu ván mới").click().run()
        self.assertEqual(app.session_state["chase_state"].observation.rules.runner_budget, 80)
        self.assertFalse(app.exception)

    def test_missing_osm_is_clear_error_and_previous_game_survives(self):
        app = self.app
        previous = app.session_state["chase_state"]
        next(item for item in app.selectbox if item.label == "Sân chơi").select("Phố cổ Hà Nội · OSM")
        button(app, "Bắt đầu ván mới").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("Chưa có graph" in item.value for item in app.error))
        self.assertEqual(app.session_state["chase_state"], previous)

    def test_replay_disables_moves(self):
        app = self.app
        app.checkbox[0].check().run()
        self.assertFalse(app.exception)
        self.assertFalse(any(item.label == "Đi nước này" for item in app.button))

    def test_terminal_status_and_disabled_input(self):
        from dataclasses import replace
        for status in ("escaped", "caught", "timeout"):
            app = self.app
            app.session_state["chase_state"] = replace(app.session_state["chase_state"], status=status)
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(button(app, "Đi nước này").disabled)

    def test_original_app_can_open_chase_before_loading_missing_large_graph(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        app.query_params["mode"] = "chase"
        with patch("src.map_service.load_bundled_road_network") as loader:
            app.run()
        loader.assert_not_called()
        self.assertFalse(app.exception)
        self.assertIn("chase_state", app.session_state)

    def test_replay_shows_previous_turn_without_changing_live_state(self):
        app = self.app
        state = app.session_state["chase_state"]
        next(item for item in app.selectbox if item.key == "chase_destination").select(state.runner).run()
        button(app, "Đi nước này").click().run()
        live = app.session_state["chase_state"]
        app.checkbox[0].check().run()
        next(item for item in app.slider if item.label == "Xem lượt").set_value(0).run()
        self.assertEqual(app.session_state["chase_state"], live)
        self.assertEqual(len(app.session_state["chase_history"]), 2)
        self.assertFalse(app.exception)
        app.checkbox[0].uncheck().run()
        self.assertTrue(any(item.label == "Đi nước này" for item in app.button))

    def test_actual_ui_moves_reach_all_three_terminal_outcomes(self):
        from src.chase import Rules, new_game
        app = self.app
        arena = app.session_state["chase_arena"]
        for expected, hunters, exits, destination, max_turns in (
            ("escaped", (79, 80), (1,), 1, 10),
            ("caught", (1, 80), (8,), 1, 10),
            ("timeout", (79, 80), (8,), 0, 1),
        ):
            state = new_game(arena, 0, hunters, exits, Rules(160, 160, 3, max_turns))
            app.session_state["chase_state"] = state
            app.session_state["chase_history"] = [state]
            app.run()
            next(item for item in app.selectbox if item.key == "chase_destination").select(destination).run()
            button(app, "Đi nước này").click().run()
            self.assertEqual(app.session_state["chase_state"].status, expected)
            self.assertFalse(app.exception)
            self.assertTrue(button(app, "Đi nước này").disabled)


if __name__ == "__main__":
    unittest.main()
