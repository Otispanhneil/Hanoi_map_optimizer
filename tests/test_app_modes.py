"""Round-trip tests for the original routing UI and the integrated chase mode."""
from concurrent.futures import Future
from contextlib import ExitStack
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from src.utils import Location, UserFacingError
from tests.test_shortest_path import sample_graph


ROOT = Path(__file__).resolve().parents[1]


def button(app, key):
    return next(item for item in app.button if item.key == key)


class IntegratedModeTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict("os.environ", {"HANOI_PRELOAD_MAP": "0"}))
        missing = ROOT / "data" / "not-present-test.graphml"
        self.stack.enter_context(patch("src.chase_ui.MAP_PATH", missing))
        self.stack.enter_context(patch("src.chase_maps.MAP_PATH", missing))
        self.stack.enter_context(patch("src.geocoding.ensure_in_hanoi"))
        self.graph = sample_graph()
        self.graph.add_edge(2, 1, length=110, travel_time=22)
        self.graph.add_edge(1, 0, length=120, travel_time=24)
        self.graph.add_edge(2, 0, length=250, travel_time=50)
        self.stack.enter_context(patch("src.map_service.load_road_network", return_value=self.graph))
        future = Future()
        future.set_result(self.graph)
        self.stack.enter_context(patch("src.map_service.prefetch_road_network", side_effect=lambda bbox: (bbox, future)))
        from src.chase_ui import cached_arena
        cached_arena.clear()

    def app(self, mode=None):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
        if mode:
            app.query_params["mode"] = mode
        return app.run()

    def prepared_route(self, mode="Quay về điểm xuất phát"):
        app = self.app()
        app.session_state["start"] = Location("A", 21.03, 105.8)
        app.session_state["destinations"] = [Location("B", 21.03, 105.81), Location("C", 21.03, 105.82)]
        app.run()
        app.radio[0].set_value("Thời gian di chuyển").run()
        next(item for item in app.selectbox if item.key == "routing_end_mode").select(mode).run()
        if mode == "Do tôi chọn":
            next(item for item in app.selectbox if item.key == "routing_end_choice").select(1).run()
        next(item for item in app.button if item.label == "TỐI ƯU LỘ TRÌNH").click().run()
        self.assertIsNotNone(app.session_state["result"])
        self.assertFalse(app.exception)
        return app

    def test_default_is_original_routing_ui(self):
        app = self.app()
        self.assertEqual(app.session_state["workspace_mode"], "route")
        self.assertTrue(any(item.label == "TỐI ƯU LỘ TRÌNH" for item in app.button))
        self.assertFalse(any(item.label == "Đi nước này" for item in app.button))
        self.assertFalse(app.exception)

    def test_deep_link_and_unknown_mode(self):
        chase = self.app("chase")
        self.assertEqual(chase.session_state["workspace_mode"], "chase")
        self.assertFalse(chase.exception)
        unknown = self.app("unknown")
        self.assertEqual(unknown.session_state["workspace_mode"], "route")
        self.assertFalse(unknown.exception)

    def test_closed_time_route_survives_three_round_trips(self):
        app = self.prepared_route()
        result = app.session_state["result"]
        start, destinations = app.session_state["start"], app.session_state["destinations"]
        next(item for item in app.toggle if item.key == "enable_map_click").set_value(False).run()
        for _ in range(3):
            button(app, "mode_chase").click().run()
            self.assertEqual(app.session_state["workspace_mode"], "chase")
            button(app, "mode_route").click().run()
            self.assertEqual(app.session_state["result"], result)
            self.assertEqual(app.session_state["start"], start)
            self.assertEqual(app.session_state["destinations"], destinations)
            self.assertEqual(app.radio[0].value, "Thời gian di chuyển")
            self.assertEqual(app.session_state["routing_end_mode"], "Quay về điểm xuất phát")
            self.assertFalse(app.session_state["enable_map_click"])
            self.assertFalse(app.exception)

    def test_fixed_end_choice_survives_round_trip(self):
        app = self.prepared_route("Do tôi chọn")
        result = app.session_state["result"]
        button(app, "mode_chase").click().run()
        button(app, "mode_route").click().run()
        self.assertEqual(app.session_state["routing_end_choice"], 1)
        self.assertEqual(app.session_state["result"], result)
        self.assertEqual(result.order[-1], 2)
        self.assertFalse(app.exception)

    def test_chase_progress_survives_route_visit(self):
        app = self.app("chase")
        state = app.session_state["chase_state"]
        next(item for item in app.selectbox if item.key == "chase_destination").select(state.runner).run()
        next(item for item in app.button if item.label == "Đi nước này").click().run()
        state = app.session_state["chase_state"]
        history = list(app.session_state["chase_history"])
        button(app, "mode_route").click().run()
        button(app, "mode_chase").click().run()
        self.assertEqual(app.session_state["chase_state"], state)
        self.assertEqual(app.session_state["chase_history"], history)
        self.assertFalse(app.exception)

    def test_changing_objective_after_return_still_invalidates_route(self):
        app = self.prepared_route()
        button(app, "mode_chase").click().run()
        button(app, "mode_route").click().run()
        app.radio[0].set_value("Quãng đường").run()
        self.assertIsNone(app.session_state["result"])
        self.assertFalse(app.exception)

    def test_missing_bundled_graph_keeps_original_ui_and_navigation_available(self):
        with patch.dict("os.environ", {"HANOI_PRELOAD_MAP": "1"}), patch(
            "src.map_service.load_bundled_road_network", side_effect=UserFacingError("Chưa có graph lớn.")
        ) as loader:
            app = self.app()
            self.assertTrue(app.warning)
            self.assertFalse(app.exception)
            self.assertTrue(any(item.label == "TỐI ƯU LỘ TRÌNH" for item in app.button))
            calls = loader.call_count
            button(app, "mode_chase").click().run()
            self.assertEqual(loader.call_count, calls)
            self.assertIn("chase_state", app.session_state)
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
