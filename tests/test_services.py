import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import networkx as nx
from shapely.geometry import box

from src.geocoding import ensure_in_hanoi, search_location
from src.map_service import (
    _load_bundled_road_network,
    add_travel_times,
    bbox_contains,
    bbox_dimensions_km,
    bundled_area_contains,
    bundled_graph_version,
    bundled_routing_bbox,
    cache_aligned_bbox,
    load_bundled_road_network,
    dynamic_bbox_supported,
    selected_bbox,
    snap_locations,
)
from src.utils import Location, UserFacingError, validate_selection
from src.visualization import create_map
from tests.test_shortest_path import sample_graph


class ServiceTests(unittest.TestCase):
    def test_input_errors(self):
        start = Location("A", 21.03, 105.80)
        cases = [(None, [start]), (start, []), (start, [start]),
                 (start, [Location("gần", 21.03001, 105.80001)]),
                 (start, [Location("ngoài", 10.7, 106.7)]),
                 (start, [Location(str(i), 21.03, 105.81 + i * 0.001) for i in range(11)])]
        for origin, destinations in cases:
            with self.subTest(origin=origin, destinations=destinations), self.assertRaises(UserFacingError):
                validate_selection(origin, destinations)

    def test_actual_polygon_rejects_point_inside_envelope(self):
        with patch("src.geocoding.get_hanoi_boundary", return_value=box(105.7, 21, 105.9, 21.1)):
            ensure_in_hanoi(Location("trong", 21.03, 105.8))
            with self.assertRaises(UserFacingError):
                ensure_in_hanoi(Location("ngoài polygon", 21.2, 105.8))

    def test_geocoder_outage_is_friendly(self):
        search_location.clear()
        with patch("src.geocoding._nominatim_call", side_effect=TimeoutError):
            with self.assertRaises(UserFacingError):
                search_location("Địa chỉ kiểm thử timeout")

    def test_bounding_box_order_and_margin(self):
        west, south, east, north = selected_bbox([Location("A", 21.03, 105.8)], 5)
        self.assertLess(west, 105.8)
        self.assertGreater(east, 105.8)
        self.assertLess(south, 21.03)
        self.assertGreater(north, 21.03)

    def test_dynamic_bbox_rejects_excessive_region(self):
        small = selected_bbox([Location("A", 21.03, 105.8), Location("B", 21.05, 105.85)], 2)
        large = selected_bbox([Location("A", 20.85, 105.4), Location("B", 21.15, 105.9)], 2)
        width, height = bbox_dimensions_km(large)
        self.assertGreater(width, 35)
        self.assertGreater(height, 30)
        self.assertTrue(dynamic_bbox_supported(small))
        self.assertFalse(dynamic_bbox_supported(large))

    def test_bbox_containment_for_session_graph_reuse(self):
        outer = (105.7, 20.9, 105.9, 21.1)
        self.assertTrue(bbox_contains(outer, (105.75, 20.95, 105.85, 21.05)))
        self.assertTrue(bbox_contains(outer, outer))
        self.assertFalse(bbox_contains(outer, (105.6, 20.95, 105.85, 21.05)))

    def test_cache_aligned_bbox_is_stable_and_contains_request(self):
        first = (105.801, 21.021, 105.849, 21.069)
        nearby = (105.802, 21.022, 105.848, 21.068)
        aligned = cache_aligned_bbox(first)
        self.assertEqual(aligned, cache_aligned_bbox(nearby))
        self.assertTrue(bbox_contains(aligned, first))
        with self.assertRaises(ValueError):
            cache_aligned_bbox(first, 0)

    def test_bundled_area_covers_popular_locations_only(self):
        from data.popular_locations import POPULAR_LOCATIONS
        self.assertTrue(bundled_area_contains(POPULAR_LOCATIONS))
        self.assertFalse(bundled_area_contains([Location("ngoài vùng", 22.0, 105.9)]))

    def test_bundled_bbox_uses_valid_metadata_and_falls_back(self):
        with TemporaryDirectory() as directory:
            metadata = Path(directory) / "graph.meta.json"
            metadata.write_text(json.dumps({"bbox": [105.4, 20.84, 105.91, 21.16]}), encoding="utf-8")
            with patch("src.map_service.BUNDLED_GRAPH_METADATA_PATH", metadata):
                self.assertEqual(bundled_routing_bbox(), (105.4, 20.84, 105.91, 21.16))
                self.assertTrue(bundled_area_contains([Location("Hoa Lac", 21.0, 105.5)]))
                metadata.write_text('{"bbox": [1, 2]}', encoding="utf-8")
                from src.constants import BUNDLED_ROUTING_BBOX
                self.assertEqual(bundled_routing_bbox(), BUNDLED_ROUTING_BBOX)

    def test_bundled_graph_version_changes_when_bundle_changes(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pickle_path = root / "graph.pkl"
            graphml_path = root / "graph.graphml"
            metadata_path = root / "graph.json"
            for path in (pickle_path, graphml_path, metadata_path):
                path.write_bytes(b"v1")
            with patch("src.map_service.BUNDLED_GRAPH_FAST_PATH", pickle_path), patch(
                "src.map_service.BUNDLED_GRAPH_PATH", graphml_path
            ), patch("src.map_service.BUNDLED_GRAPH_METADATA_PATH", metadata_path):
                first = bundled_graph_version()
                pickle_path.write_bytes(b"version-two")
                self.assertNotEqual(first, bundled_graph_version())

    def test_bundled_loader_explains_missing_git_lfs_data(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pointer = b"version https://git-lfs.github.com/spec/v1\noid sha256:test\nsize 123\n"
            pickle_path = root / "graph.pkl"
            graphml_path = root / "graph.graphml"
            pickle_path.write_bytes(pointer)
            graphml_path.write_bytes(pointer)
            with patch("src.map_service.BUNDLED_GRAPH_FAST_PATH", pickle_path), patch(
                "src.map_service.BUNDLED_GRAPH_PATH", graphml_path
            ), self.assertRaisesRegex(UserFacingError, "git lfs pull"):
                _load_bundled_road_network(("lfs-pointer", str(root)))

    def test_bundled_loader_falls_back_when_pickle_is_corrupt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            pickle_path = root / "graph.pkl"
            graphml_path = root / "graph.graphml"
            pickle_path.write_bytes(b"not-a-pickle")
            graph = sample_graph()
            graph.add_edge(2, 1, length=100, travel_time=20)
            graph.add_edge(1, 0, length=100, travel_time=20)
            import osmnx as ox
            ox.io.save_graphml(graph, graphml_path)
            with patch("src.map_service.BUNDLED_GRAPH_FAST_PATH", pickle_path), patch(
                "src.map_service.BUNDLED_GRAPH_PATH", graphml_path
            ):
                loaded = _load_bundled_road_network(("fallback", str(root)))
            self.assertGreater(loaded.number_of_edges(), 0)

    def test_bundled_graph_routes_all_popular_locations(self):
        from data.popular_locations import POPULAR_LOCATIONS
        graph = load_bundled_road_network()
        nodes, distances = snap_locations(graph, POPULAR_LOCATIONS)
        self.assertGreater(graph.number_of_nodes(), 30_000)
        self.assertTrue(all(distance <= 1500 for distance in distances))
        self.assertTrue(all(nx.has_path(graph, nodes[0], node) for node in nodes[1:]))

    def test_speed_fallback_and_maxspeed(self):
        graph = nx.MultiDiGraph(crs="EPSG:4326")
        graph.add_node(0, x=105.8, y=21.03)
        graph.add_node(1, x=105.81, y=21.03)
        graph.add_edge(0, 1, length=100, highway="residential")
        graph.add_edge(1, 0, length=100, highway="primary", maxspeed="36")
        graph = add_travel_times(graph)
        self.assertAlmostEqual(graph[0][1][0]["speed_kph"], 25)
        self.assertAlmostEqual(graph[0][1][0]["travel_time"], 14.4)
        self.assertAlmostEqual(graph[1][0][0]["travel_time"], 10)

    def test_snap_nodes_same_node_and_far_point(self):
        graph = sample_graph()
        points = [Location("A", 21.03, 105.8), Location("B", 21.03, 105.82)]
        nodes, distances = snap_locations(graph, points)
        self.assertEqual(nodes, [0, 2])
        self.assertEqual(distances, [0, 0])
        with self.assertRaises(UserFacingError):
            snap_locations(graph, [points[0], Location("gần A", 21.03001, 105.80001)])
        with self.assertRaises(UserFacingError):
            snap_locations(graph, [Location("xa", 21.3, 105.8)])

    def test_map_escapes_place_names(self):
        result = create_map(Location("<script>alert(1)</script>", 21.03, 105.8), [])
        html = result.get_root().render()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_map_has_street_and_satellite_base_layers(self):
        html = create_map(Location("A", 21.03, 105.8), []).get_root().render()
        self.assertIn("tile.openstreetmap.org", html)
        self.assertIn("World_Imagery", html)
        self.assertIn(r"\u0110\u01b0\u1eddng ph\u1ed1", html)
        self.assertIn(r"V\u1ec7 tinh", html)
        self.assertIn("base_layers", html)
