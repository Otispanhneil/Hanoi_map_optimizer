import unittest

import networkx as nx
from shapely.geometry import LineString

from scripts.preload_hanoi_pbf import compact_graph


class PbfPreloadTests(unittest.TestCase):
    def test_compact_graph_keeps_only_runtime_attributes(self):
        graph = nx.MultiDiGraph(crs="EPSG:4326", name="test")
        graph.add_node(1, x=105.8, y=21.0, visible=True, street_count=3)
        graph.add_node(2, x=105.81, y=21.01, visible=True)
        graph.add_edge(1, 2, length=100, travel_time=10, highway="primary",
                       name="Test", geometry=LineString([(105.8, 21.0), (105.81, 21.01)]))
        compact_graph(graph)
        self.assertEqual(set(graph.nodes[1]), {"x", "y"})
        self.assertEqual(set(graph[1][2][0]), {"length", "travel_time", "geometry"})
        self.assertEqual(graph.graph, {"crs": "EPSG:4326", "simplified": True})


if __name__ == "__main__":
    unittest.main()
