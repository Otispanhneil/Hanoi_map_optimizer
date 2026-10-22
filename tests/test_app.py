import os
from pathlib import Path
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

from tests.test_shortest_path import sample_graph
from src.utils import Location

os.environ["HANOI_PRELOAD_MAP"] = "0"

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def button(app, label):
    return next(item for item in app.button if item.label == label)


def button_by_key(app, key):
    return next(item for item in app.button if item.key == key)


def map_click(lat, lng):
    """Giả lập callback của component trước lượt chạy lại Streamlit."""
    def fake_st_folium(*args, **kwargs):
        st.session_state["route_map"] = {"last_clicked": {"lat": lat, "lng": lng}}
        kwargs["on_change"]()
        return st.session_state["route_map"]
    return fake_st_folium


class AppTests(unittest.TestCase):
    def test_first_map_click_sets_start_then_next_click_adds_destination(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        with patch("src.geocoding.ensure_in_hanoi"), patch(
            "streamlit_folium.st_folium", side_effect=map_click(21.03, 105.8)
        ):
            app.run()
        self.assertEqual(app.session_state["start"].name, "Điểm tùy chọn 1")
        self.assertEqual(len(app.session_state["destinations"]), 0)
        with patch("src.geocoding.ensure_in_hanoi"), patch(
            "src.map_service.load_road_network", return_value=sample_graph()
        ), patch("streamlit_folium.st_folium", side_effect=map_click(21.04, 105.82)):
            app.run()
        self.assertEqual(len(app.session_state["destinations"]), 1)
        self.assertEqual(app.session_state["destinations"][0].name, "Điểm tùy chọn 2")

    def test_map_click_outside_hanoi_is_rejected(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        from src.utils import UserFacingError
        with patch("src.geocoding.ensure_in_hanoi", side_effect=UserFacingError("Địa điểm nằm ngoài Hà Nội.")), patch(
            "streamlit_folium.st_folium", side_effect=map_click(22.0, 105.9)
        ):
            app.run()
        app.run()
        self.assertIsNone(app.session_state["start"])
        self.assertEqual(len(app.session_state["destinations"]), 0)
        self.assertTrue(any("ngoài Hà Nội" in item.value for item in app.error))
        self.assertFalse(app.exception)

    def test_startup_validation_add_remove_and_duplicates(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertFalse(any(item.label == "Phạm vi tải mạng đường" for item in app.expander))
        self.assertFalse(any(item.label == "Vùng đệm quanh các điểm (km)" for item in app.slider))
        button(app, "TỐI ƯU LỘ TRÌNH").click().run()
        self.assertTrue(any("xuất phát" in item.value for item in app.error))
        app.selectbox[0].select(0).run()
        button(app, "Đặt điểm xuất phát").click().run()
        app.selectbox[1].select(1).run()
        with patch("src.map_service.load_road_network", return_value=sample_graph()):
            button(app, "Thêm điểm đã chọn").click().run()
        self.assertEqual(len(app.session_state["destinations"]), 1)
        button(app, "Thêm điểm đã chọn").click().run()
        self.assertEqual(len(app.session_state["destinations"]), 1)
        self.assertTrue(app.error)
        button_by_key(app, "remove_0").click().run()
        self.assertEqual(len(app.session_state["destinations"]), 0)
        button_by_key(app, "remove_start").click().run()
        self.assertIsNone(app.session_state["start"])
        self.assertIsNone(app.session_state["result"])
        self.assertFalse(app.exception)

    def test_clear_destinations_resets_custom_names_and_last_click(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        app.session_state["start"] = Location("Điểm xuất phát có sẵn", 20.85, 105.40)
        app.session_state["destinations"] = [
            Location("Điểm tùy chọn 8", 21.15, 105.90),
            Location("Điểm tùy chọn 9", 21.10, 105.85),
        ]
        app.session_state["custom_count"] = 9
        app.session_state["last_click"] = (21.10, 105.85)
        app.run()
        button(app, "Xóa tất cả điểm cần ghé").click().run()
        self.assertEqual(app.session_state["destinations"], [])
        self.assertEqual(app.session_state["custom_count"], 0)
        self.assertIsNone(app.session_state["last_click"])
        with patch("src.geocoding.ensure_in_hanoi"), patch(
            "streamlit_folium.st_folium", side_effect=map_click(21.06, 105.83)
        ):
            app.run()
        self.assertEqual(app.session_state["destinations"][0].name, "Điểm tùy chọn 1")

    def test_full_ui_pipeline_with_offline_graph_and_invalidation(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        graph = sample_graph()
        app.session_state["start"] = Location("A", 21.03, 105.8)
        app.session_state["destinations"] = [Location("B", 21.03, 105.81), Location("C", 21.03, 105.82)]
        with patch("src.geocoding.ensure_in_hanoi"), patch("src.map_service.load_road_network", return_value=graph):
            button(app, "TỐI ƯU LỘ TRÌNH").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.session_state["result"].order, [0, 1, 2])
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(app.metric[0].value, "0.20 km")
        app.radio[0].set_value("Thời gian di chuyển").run()
        self.assertIsNone(app.session_state["result"])
        self.assertFalse(app.exception)

    def test_closed_route_option_through_ui(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        graph = sample_graph()
        graph.add_edge(2, 1, length=110, travel_time=22)
        graph.add_edge(1, 0, length=120, travel_time=24)
        graph.add_edge(2, 0, length=250, travel_time=50)
        app.session_state["start"] = Location("A", 21.03, 105.8)
        app.session_state["destinations"] = [
            Location("B", 21.03, 105.81), Location("C", 21.03, 105.82)
        ]
        with patch("src.map_service.load_road_network", return_value=graph):
            app.run()
        route_mode = next(item for item in app.selectbox if item.label == "Điểm kết thúc")
        route_mode.select("Quay về điểm xuất phát").run()
        with patch("src.geocoding.ensure_in_hanoi"), patch(
            "src.map_service.load_road_network", return_value=graph
        ):
            button(app, "TỐI ƯU LỘ TRÌNH").click().run()
        result = app.session_state["result"]
        self.assertEqual(result.route_mode, "closed")
        self.assertEqual(result.order[0], result.order[-1])
        self.assertFalse(app.exception)

    def test_excessive_region_fails_fast_without_loading_graph(self):
        app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()
        app.session_state["start"] = Location("A", 20.85, 105.4)
        app.session_state["destinations"] = [Location("B", 21.15, 105.9)]
        app.run()
        with patch("src.geocoding.ensure_in_hanoi"), patch(
            "src.map_service.load_road_network"
        ) as loader:
            button(app, "TỐI ƯU LỘ TRÌNH").click().run()
        self.assertIsNone(app.session_state["result"])
        self.assertTrue(any("quá rộng" in item.value for item in app.error))
        loader.assert_not_called()
        self.assertFalse(app.exception)
