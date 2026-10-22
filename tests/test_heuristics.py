import random
import unittest

from src.heuristics import nearest_neighbor, route_cost, two_opt
from src.tsp import solve_tsp


class HeuristicTests(unittest.TestCase):
    def setUp(self):
        randomizer = random.Random(7)
        self.matrix = [[0 if i == j else randomizer.randint(1, 50)
                        for j in range(7)] for i in range(7)]

    def test_open_route_visits_all_nodes_and_two_opt_never_worsens(self):
        greedy_order, greedy_cost = nearest_neighbor(self.matrix)
        improved_order, improved_cost = two_opt(greedy_order, self.matrix)
        self.assertEqual(greedy_order[0], 0)
        self.assertEqual(set(greedy_order), set(range(7)))
        self.assertEqual(set(improved_order), set(range(7)))
        self.assertLessEqual(improved_cost, greedy_cost)
        self.assertEqual(improved_cost, route_cost(improved_order, self.matrix))
        _, optimal_cost = solve_tsp(self.matrix)
        self.assertGreaterEqual(improved_cost, optimal_cost)

    def test_fixed_end_is_preserved(self):
        greedy_order, greedy_cost = nearest_neighbor(self.matrix, end_index=4)
        improved_order, improved_cost = two_opt(greedy_order, self.matrix, fixed_end=True)
        self.assertEqual(greedy_order[-1], 4)
        self.assertEqual(improved_order[-1], 4)
        self.assertLessEqual(improved_cost, greedy_cost)

    def test_closed_route_returns_to_start(self):
        greedy_order, greedy_cost = nearest_neighbor(self.matrix, return_to_start=True)
        improved_order, improved_cost = two_opt(greedy_order, self.matrix, return_to_start=True)
        self.assertEqual(greedy_order[0], greedy_order[-1])
        self.assertEqual(improved_order[0], improved_order[-1])
        self.assertEqual(set(improved_order[:-1]), set(range(7)))
        self.assertLessEqual(improved_cost, greedy_cost)
