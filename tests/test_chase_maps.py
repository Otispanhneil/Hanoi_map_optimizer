from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from xml.etree.ElementTree import ParseError

import networkx as nx

from scripts.extract_chase_map import extract_graphml
from src.chase import Rules, STRATEGIES, step
from src.chase_maps import MAP_PATH, load_arena, scenario
from src.chase_ui import handle_map_click
from tests.test_chase import line_graph


class Store(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class MapDataTests(unittest.TestCase):
    def test_failed_download_preserves_existing_arena_file(self):
        import requests
        from scripts import prepare_chase_map
        with TemporaryDirectory() as directory:
            target = Path(directory) / "existing.graphml"
            target.write_bytes(b"existing arena fixture")
            with patch.object(prepare_chase_map, "MAP_PATH", target), patch.object(
                    prepare_chase_map.requests, "get", side_effect=requests.ConnectionError("offline")):
                with self.assertRaises(SystemExit):
                    prepare_chase_map.main()
            self.assertEqual(target.read_bytes(), b"existing arena fixture")

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            load_arena("unknown")

    def test_missing_osm_rejected(self):
        with patch("src.chase_maps.MAP_PATH", Path("not-present-test.graphml")):
            with self.assertRaisesRegex(ValueError, "Chưa có graph"):
                load_arena("osm")

    def test_complete_and_explicit_partial_xml_extraction(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.graphml"
            nx.write_graphml(line_graph(), path)
            graph = extract_graphml(path, (105, 20, 107, 22))
            self.assertEqual(graph.graph["partial_source"], "False")
            self.assertAlmostEqual(nx.shortest_path_length(graph, 0, 11, weight="length"), 1100)
            text = path.read_text(encoding="utf-8")
            path.write_text(text.rsplit("</edge>", 1)[0] + "</edge>", encoding="utf-8")
            with self.assertRaises(ParseError):
                extract_graphml(path, (105, 20, 107, 22))
            recovered = extract_graphml(path, (105, 20, 107, 22), allow_truncated=True)
            self.assertEqual(recovered.graph["partial_source"], "True")
            self.assertTrue(nx.is_strongly_connected(recovered))

    def test_extraction_outside_bbox_fails(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.graphml"
            nx.write_graphml(line_graph(), path)
            with self.assertRaisesRegex(ValueError, "Không có cạnh"):
                extract_graphml(path, (1, 1, 2, 2))

    @unittest.skipUnless(MAP_PATH.exists(), "Optional OSM arena is not installed")
    def test_packaged_osm_topology_and_all_budget_choices(self):
        arena = load_arena("osm")
        self.assertTrue(nx.is_strongly_connected(arena.graph))
        self.assertLessEqual(len(arena.nodes), 600)
        self.assertLessEqual(max(d["length"] for _, _, d in arena.graph.edges(data=True)), 90 + 1e-8)
        for runner in (80, 100, 120, 140, 160, 180):
            for hunter in (80, 100, 120, 140, 160, 180):
                state = scenario(arena, Rules(runner, hunter), 7)
                self.assertIn(state.runner, state.observation.belief)

    @unittest.skipUnless(MAP_PATH.exists(), "Optional OSM arena is not installed")
    def test_osm_games_truth_invariant_for_all_strategies(self):
        from random import Random
        arena = load_arena("osm")
        for strategy in STRATEGIES:
            for seed in range(5):
                rng = Random(seed)
                state = scenario(arena, Rules(), seed)
                while state.status == "playing":
                    move = rng.choice(arena.reachable(state.runner, 160))
                    state = step(arena, state, move, strategy)
                    self.assertIn(state.runner, state.observation.belief)
                    self.assertLessEqual(state.observation.turn, 18)


class MapInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arena = load_arena("demo")

    def setUp(self):
        state = scenario(self.arena, Rules(), 7)
        self.store = Store(chase_state=state, chase_arena=self.arena, chase_destination=None,
                           chase_replay=False, chase_last_click=None)

    def test_click_exact_reachable_node_selects_it(self):
        node = self.arena.reachable(self.store.chase_state.runner, 160)[0]
        data = self.arena.graph.nodes[node]
        self.store["chase_map"] = {"last_object_clicked": {"lat": data["y"], "lng": data["x"]}}
        with patch("src.chase_ui.st.session_state", self.store):
            handle_map_click()
        self.assertEqual(self.store.chase_destination, node)

    def test_far_click_does_not_move_or_select(self):
        previous = self.store.chase_state
        self.store["chase_map"] = {"last_object_clicked": {"lat": 22, "lng": 106}}
        with patch("src.chase_ui.st.session_state", self.store):
            handle_map_click()
        self.assertIsNone(self.store.chase_destination)
        self.assertEqual(self.store.chase_state, previous)
        self.assertIn("chấm xanh", self.store.chase_notice)

    def test_replay_terminal_and_duplicate_click_are_ignored(self):
        from dataclasses import replace
        data = self.arena.graph.nodes[self.store.chase_state.runner]
        event = {"lat": data["y"], "lng": data["x"]}
        self.store["chase_map"] = {"last_object_clicked": event}
        for mode in ("replay", "terminal", "duplicate"):
            store = Store(self.store)
            if mode == "replay":
                store.chase_replay = True
            elif mode == "terminal":
                store.chase_state = replace(store.chase_state, status="escaped")
            else:
                store.chase_last_click = event
            with patch("src.chase_ui.st.session_state", store):
                handle_map_click()
            self.assertIsNone(store.chase_destination)

    def test_missing_map_event_is_ignored(self):
        with patch("src.chase_ui.st.session_state", self.store):
            handle_map_click()
        self.assertIsNone(self.store.chase_destination)


if __name__ == "__main__":
    unittest.main()
