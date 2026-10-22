import itertools
import math
import random
import unittest

from src.tsp import solve_open_tsp, solve_tsp
from src.utils import UserFacingError


def brute_force(matrix, start):
    others = [i for i in range(len(matrix)) if i != start]
    return min(sum(matrix[a][b] for a, b in zip((start, *order), order))
               for order in itertools.permutations(others))


class OpenTspTests(unittest.TestCase):
    def test_fixed_end_matches_exhaustive_search(self):
        matrix = [
            [0, 4, 1, 8],
            [3, 0, 6, 2],
            [5, 1, 0, 7],
            [4, 3, 2, 0],
        ]
        for end in [1, 2, 3]:
            candidates = []
            for middle in itertools.permutations(i for i in range(1, 4) if i != end):
                order = [0, *middle, end]
                candidates.append(sum(matrix[a][b] for a, b in zip(order, order[1:])))
            order, cost = solve_tsp(matrix, end_index=end)
            self.assertEqual(order[0], 0)
            self.assertEqual(order[-1], end)
            self.assertEqual(cost, min(candidates))

    def test_closed_tsp_matches_exhaustive_search(self):
        matrix = [
            [0, 4, 1, 8],
            [3, 0, 6, 2],
            [5, 1, 0, 7],
            [4, 3, 2, 0],
        ]
        expected = min(
            sum(matrix[a][b] for a, b in zip((0, *middle), (*middle, 0)))
            for middle in itertools.permutations([1, 2, 3])
        )
        order, cost = solve_tsp(matrix, return_to_start=True)
        self.assertEqual(order[0], 0)
        self.assertEqual(order[-1], 0)
        self.assertEqual(set(order[:-1]), set(range(4)))
        self.assertEqual(cost, expected)

    def test_matches_exhaustive_search_asymmetric_all_starts(self):
        randomizer = random.Random(42)
        for size in range(2, 7):
            for trial in range(5):
                matrix = [[0 if i == j else randomizer.randint(1, 40)
                           for j in range(size)] for i in range(size)]
                for start in range(size):
                    with self.subTest(size=size, trial=trial, start=start):
                        order, cost = solve_open_tsp(matrix, start)
                        self.assertEqual(order[0], start)
                        self.assertEqual(len(order), size)
                        self.assertEqual(set(order), set(range(size)))
                        self.assertNotEqual(order[-1], start)
                        self.assertEqual(cost, sum(matrix[a][b] for a, b in zip(order, order[1:])))
                        self.assertEqual(cost, brute_force(matrix, start))

    def test_open_not_closed(self):
        matrix = [[0, 1, 8, 9], [90, 0, 1, 9], [90, 9, 0, 1], [1000, 9, 9, 0]]
        self.assertEqual(solve_open_tsp(matrix), ([0, 1, 2, 3], 3))

    def test_one_destination(self):
        self.assertEqual(solve_open_tsp([[0, 7], [math.inf, 0]]), ([0, 1], 7))

    def test_no_destinations_in_solver(self):
        self.assertEqual(solve_open_tsp([[0]]), ([0], 0))

    def test_disconnected_pairs_can_have_valid_open_route(self):
        matrix = [[0, 1, math.inf], [math.inf, 0, 2], [math.inf, math.inf, 0]]
        self.assertEqual(solve_open_tsp(matrix), ([0, 1, 2], 3))

    def test_no_feasible_route(self):
        with self.assertRaises(UserFacingError):
            solve_open_tsp([[0, math.inf], [1, 0]])

    def test_zero_cost_ties_and_input_unchanged(self):
        matrix = [[0] * 5 for _ in range(5)]
        before = [row[:] for row in matrix]
        order, cost = solve_open_tsp(matrix, 2)
        self.assertEqual(set(order), set(range(5)))
        self.assertEqual(cost, 0)
        self.assertEqual(matrix, before)

    def test_ten_destinations(self):
        matrix = [[0 if i == j else 1 for j in range(11)] for i in range(11)]
        order, cost = solve_open_tsp(matrix)
        self.assertEqual(len(set(order)), 11)
        self.assertEqual(cost, 10)

    def test_invalid_inputs(self):
        for matrix, start in [([], 0), ([[0, 1]], 0), ([[0]], 1), ([[0]], -1),
                              ([[0, -1], [1, 0]], 0), ([[0, math.nan], [1, 0]], 0),
                              ([[0] * 12 for _ in range(12)], 0)]:
            with self.subTest(matrix=matrix, start=start), self.assertRaises(ValueError):
                solve_open_tsp(matrix, start)
        with self.assertRaises(ValueError):
            solve_tsp([[0, 1], [1, 0]], end_index=1, return_to_start=True)
        with self.assertRaises(ValueError):
            solve_tsp([[0, 1], [1, 0]], end_index=0)
