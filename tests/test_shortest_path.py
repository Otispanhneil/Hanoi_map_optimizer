import math
import unittest

import networkx as nx
from shapely.geometry import LineString

from src.route_optimizer import optimize_route
from src.shortest_path import build_cost_matrix, path_edges, shortest_path
from src.utils import Location, UserFacingError


def sample_graph():
    graph = nx.MultiDiGraph(crs="EPSG:4326")
    for node, lon in enumerate([105.80, 105.81, 105.82]):
        graph.add_node(node, x=lon, y=21.03)
    graph.add_edge(0, 1, key=0, length=100, travel_time=100,
                   geometry=LineString([(105.80, 21.03), (105.805, 21.035), (105.81, 21.03)]))
    graph.add_edge(0, 1, key=1, length=200, travel_time=10,
                   geometry=LineString([(105.81, 21.03), (105.805, 21.025), (105.80, 21.03)]))
    graph.add_edge(1, 2, length=100, travel_time=20)
    graph.add_edge(0, 2, length=500, travel_time=80)
    return graph


class ShortestPathTests(unittest.TestCase):
    def test_direction_and_missing_path(self):
        graph = sample_graph()
        self.assertEqual(shortest_path(graph, 0, 2), ([0, 1, 2], 200))
        with self.assertRaises(UserFacingError):
            shortest_path(graph, 2, 0)

    def test_matrix_asymmetry_paths_and_diagonal(self):
        matrix, paths = build_cost_matrix(sample_graph(), [0, 1, 2])
        self.assertEqual(matrix[0][2], 200)
        self.assertEqual(matrix[2][0], math.inf)
        self.assertEqual(paths[0, 2], [0, 1, 2])
        self.assertNotIn((2, 0), paths)
        for i in range(3):
            self.assertEqual(matrix[i][i], 0)

    def test_parallel_edges_follow_objective(self):
        graph = sample_graph()
        path, cost = shortest_path(graph, 0, 2, "travel_time")
        self.assertEqual(cost, 30)
        self.assertEqual(path_edges(graph, path, "travel_time")[0][2], 1)
        self.assertEqual(path_edges(graph, path, "length")[0][2], 0)

    def test_route_statistics_and_geometry_use_same_edges(self):
        graph = sample_graph()
        locations = [Location(str(i), 21.03, graph.nodes[i]["x"]) for i in range(3)]
        for weight, expected_length, expected_time, middle_lat in [
                ("length", 200, 120, 21.035), ("travel_time", 300, 30, 21.025)]:
            result = optimize_route(graph, locations, [0, 1, 2], weight)
            self.assertEqual(result.order, [0, 1, 2])
            self.assertEqual(result.distance_m, expected_length)
            self.assertEqual(result.travel_time_s, expected_time)
            self.assertEqual(result.road_coordinates[0][0], (21.03, 105.80))
            self.assertEqual(result.road_coordinates[0][1][0], middle_lat)
            self.assertEqual(result.cost, expected_length if weight == "length" else expected_time)

    def test_fixed_end_and_closed_route_modes(self):
        graph = sample_graph()
        graph.add_edge(2, 1, length=110, travel_time=22)
        graph.add_edge(1, 0, length=120, travel_time=24)
        graph.add_edge(2, 0, length=250, travel_time=50)
        locations = [Location(str(i), 21.03, graph.nodes[i]["x"]) for i in range(3)]
        fixed = optimize_route(graph, locations, [0, 1, 2], "length",
                               route_mode="fixed_end", end_index=1)
        self.assertEqual(fixed.order, [0, 2, 1])
        self.assertEqual(fixed.route_mode, "fixed_end")
        closed = optimize_route(graph, locations, [0, 1, 2], "length", route_mode="closed")
        self.assertEqual(closed.order[0], 0)
        self.assertEqual(closed.order[-1], 0)
        self.assertEqual(set(closed.order[:-1]), {0, 1, 2})
        self.assertEqual(len(closed.legs), 3)
        self.assertEqual(closed.route_mode, "closed")
        self.assertEqual([row["algorithm"] for row in closed.comparisons],
                         ["Held–Karp", "Nearest Neighbor", "Nearest Neighbor + 2-opt"])

    def test_missing_negative_and_nan_weights_rejected(self):
        for value in [None, -1, math.nan, math.inf]:
            graph = sample_graph()
            graph[0][1][0]["length"] = value
            with self.assertRaises(UserFacingError):
                build_cost_matrix(graph, [0, 1])

    def test_unknown_node(self):
        with self.assertRaises(UserFacingError):
            shortest_path(sample_graph(), 77, 1)
