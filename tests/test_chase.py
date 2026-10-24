from dataclasses import fields, replace
from math import inf
from random import Random
import unittest
from unittest.mock import patch

import networkx as nx

from src.chase import Arena, Observation, Rules, STRATEGIES, hunter_decision, new_game, step
from src.chase_maps import demo_graph, scenario, split_long_edges
from src.chase_ui import game_map


def line_graph(directed=False):
    graph = nx.MultiDiGraph()
    for node in range(12):
        graph.add_node(node, x=105.84 + node * .001, y=21.03)
    for node in range(11):
        graph.add_edge(node, node + 1, length=100)
        if not directed:
            graph.add_edge(node + 1, node, length=100)
    return graph


class ChaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arena = Arena(line_graph())
        cls.grid = Arena(demo_graph())

    def game(self, rules=None, hunters=(8, 9), exits=(11,)):
        return new_game(self.arena, 0, hunters, exits, rules or Rules(100, 100, 3, 10))

    def test_budget_validation(self):
        for bad in (-1, 0, inf, float("nan"), True, None, "fast"):
            for key in ("runner_budget", "hunter_budget"):
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                    Rules(**{key: bad})

    def test_integer_rule_validation(self):
        for bad in (0, -1, 1.5, True):
            for key in ("reveal_every", "max_turns"):
                with self.subTest(key=key, value=bad), self.assertRaises(ValueError):
                    Rules(**{key: bad})

    def test_invalid_graph_type_and_size(self):
        for graph in (nx.Graph(), nx.MultiDiGraph(), nx.MultiDiGraph(nx.path_graph(601))):
            with self.assertRaises(ValueError):
                Arena(graph)

    def test_invalid_edge_lengths(self):
        for bad in (-1, 0, inf, float("nan"), None):
            graph = line_graph()
            graph[0][1][0].pop("length")
            if bad is not None:
                graph[0][1][0]["length"] = bad
            with self.subTest(value=bad), self.assertRaises(ValueError):
                Arena(graph)

    def test_invalid_coordinates(self):
        for bad in (None, float("nan"), "invalid", inf):
            graph = line_graph()
            graph.nodes[0]["x"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                Arena(graph)

    def test_graph_is_structurally_frozen_and_copied(self):
        graph = line_graph()
        arena = Arena(graph)
        graph.remove_node(0)
        self.assertIn(0, arena.graph)
        with self.assertRaises(nx.NetworkXError):
            arena.graph.remove_node(0)

    def test_dijkstra_matches_independent_networkx_oracle(self):
        rng = Random(41)
        for seed in range(12):
            graph = nx.MultiDiGraph()
            graph.add_nodes_from((n, {"x": 105.8 + n * .001, "y": 21.03}) for n in range(9))
            for u in graph:
                for v in graph:
                    if u != v and rng.random() < .24:
                        graph.add_edge(u, v, length=rng.randint(1, 400))
                        graph.add_edge(u, v, length=rng.randint(1, 400))
            arena = Arena(graph)
            for source in graph:
                expected = nx.single_source_dijkstra_path_length(graph, source, weight="length")
                self.assertEqual(arena.distances[source], expected, f"seed={seed}")
                self.assertEqual(set(arena.reachable(source, 150)),
                                 {n for n, cost in expected.items() if cost <= 150})

    def test_parallel_edges_choose_shortest(self):
        graph = line_graph()
        graph.add_edge(0, 1, length=40)
        arena = Arena(graph)
        self.assertEqual(arena.distance(0, 2), 140)
        self.assertIn(1, arena.reachable(0, 40))

    def test_exact_boundary_and_no_teleportation(self):
        self.assertEqual(self.arena.reachable(0, 100), (0, 1))
        self.assertEqual(self.arena.reachable(0, 99), (0,))
        self.assertEqual(self.arena.advance(0, 11, 250), 2)

    def test_one_way_and_unreachable(self):
        arena = Arena(line_graph(True))
        self.assertEqual(arena.reachable(5, 200), (5, 6, 7))
        self.assertEqual(arena.advance(5, 0, 200), 5)
        self.assertEqual(arena.distance(5, 0), inf)
        state = new_game(arena, 5, [8], [11], Rules(100, 100, 3, 10))
        with self.assertRaises(ValueError):
            step(arena, state, 4)

    def test_invalid_start_positions(self):
        cases = [(99, [8], [11]), (0, [], [11]), (0, [8, 8], [11]),
                 (0, [7, 8, 9], [11]), (0, [8], []), (0, [8], [11, 11]),
                 (0, [0], [11]), (0, [8], [0]), (0, [8], [8])]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError):
                new_game(self.arena, *args)

    def test_unreachable_exits_rejected(self):
        arena = Arena(line_graph(True))
        with self.assertRaises(ValueError):
            new_game(arena, 5, [9], [0])

    def test_invalid_move_is_atomic(self):
        state = self.game()
        for destination in (2, 99):
            with self.assertRaises(ValueError):
                step(self.arena, state, destination)
            self.assertEqual(state, self.game())

    def test_invalid_strategy(self):
        state = self.game()
        with self.assertRaises(ValueError):
            step(self.arena, state, 1, "omniscient")
        with self.assertRaises(ValueError):
            hunter_decision(self.arena, state.observation, "omniscient")

    def test_wait_is_legal(self):
        updated = step(self.arena, self.game(), 0, "trail")
        self.assertEqual(updated.runner, 0)
        self.assertEqual(updated.runner_path, (0,))
        self.assertEqual(updated.observation.turn, 1)

    def test_runner_into_hunter_caught_without_policy_call(self):
        state = self.game(hunters=(1, 9))
        with patch("src.chase.hunter_decision") as policy:
            result = step(self.arena, state, 1)
        self.assertEqual(result.status, "caught")
        policy.assert_not_called()

    def test_runner_escape_before_hunters(self):
        state = self.game(exits=(1,))
        with patch("src.chase.hunter_decision") as policy:
            result = step(self.arena, state, 1)
        self.assertEqual(result.status, "escaped")
        policy.assert_not_called()

    def test_occupied_exit_capture_precedes_escape(self):
        state = self.game(exits=(1,))
        state = replace(state, observation=replace(state.observation, hunters=(1, 9)))
        self.assertEqual(step(self.arena, state, 1).status, "caught")

    def test_hunter_capture_after_move(self):
        state = self.game(hunters=(1, 9))
        self.assertEqual(step(self.arena, state, 0, "trail").status, "caught")

    def test_endpoint_only_no_mid_path_capture(self):
        state = self.game(Rules(300, 50, 3, 10), hunters=(1, 9))
        result = step(self.arena, state, 3, "trail")
        self.assertEqual(result.runner_path, (0, 1, 2, 3))
        self.assertEqual(result.status, "playing")

    def test_timeout_is_loss(self):
        result = step(self.arena, self.game(Rules(100, 100, 3, 1)), 0, "trail")
        self.assertEqual(result.status, "timeout")

    def test_last_turn_escape_wins(self):
        result = step(self.arena, self.game(Rules(100, 100, 3, 1), exits=(1,)), 1)
        self.assertEqual(result.status, "escaped")

    def test_last_turn_capture_precedes_timeout(self):
        result = step(self.arena, self.game(Rules(100, 100, 3, 1), hunters=(1, 9)), 0, "trail")
        self.assertEqual(result.status, "caught")

    def test_terminal_states_cannot_advance(self):
        state = self.game()
        for status in ("escaped", "caught", "timeout"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                step(self.arena, replace(state, status=status), 0)

    def test_belief_expands_and_filters_negative_observations(self):
        state = self.game(hunters=(2, 9))
        result = step(self.arena, state, 0, "trail")
        self.assertEqual(result.observation.belief, frozenset({0}))
        self.assertNotIn(1, result.observation.belief)  # hunter moved to 1 without a capture

    def test_periodic_reveal_before_hunter_decision(self):
        state = self.game(Rules(100, 100, 1, 10))
        observed = []
        def policy(arena, obs, strategy):
            observed.append(obs)
            return obs.hunters, obs.hunters, "test"
        with patch("src.chase.hunter_decision", side_effect=policy):
            result = step(self.arena, state, 1)
        self.assertEqual(observed[0].belief, frozenset({1}))
        self.assertEqual(result.observation.last_seen, 1)
        self.assertEqual(result.observation.last_seen_turn, 1)

    def test_observation_contains_no_hidden_state(self):
        names = {field.name for field in fields(Observation)}
        self.assertNotIn("runner", names)
        self.assertNotIn("runner_path", names)
        self.assertNotIn("destination", names)

    def test_hidden_moves_induce_identical_policy_inputs(self):
        state = self.game()
        for strategy in STRATEGIES:
            with patch("src.chase.hunter_decision", wraps=hunter_decision) as policy:
                a = step(self.arena, state, 0, strategy)
                first_obs = policy.call_args.args[1]
                b = step(self.arena, state, 1, strategy)
                second_obs = policy.call_args.args[1]
            self.assertEqual(first_obs, second_obs)
            self.assertEqual(a.observation.hunters, b.observation.hunters)

    def test_policies_are_deterministic_and_legal(self):
        state = scenario(self.grid, Rules(160, 120, 3, 12), 7)
        observation = replace(state.observation, belief=self.grid.expand(state.observation.belief, 160))
        for strategy in STRATEGIES:
            first = hunter_decision(self.grid, observation, strategy)
            self.assertEqual(first, hunter_decision(self.grid, observation, strategy))
            for source, target in zip(observation.hunters, first[0]):
                self.assertLessEqual(self.grid.distance(source, target), observation.rules.hunter_budget + 1e-8)

    def test_empty_belief_rejected(self):
        state = self.game()
        with self.assertRaises(ValueError):
            hunter_decision(self.arena, replace(state.observation, belief=frozenset()), "contain")

    def test_disconnected_hunter_and_single_hunter_are_supported(self):
        graph = line_graph()
        graph.add_node(99, x=105.9, y=21.05)
        arena = Arena(graph)
        for strategy in STRATEGIES:
            state = new_game(arena, 0, [99], [11], Rules(100, 100, 3, 10))
            updated = step(arena, state, 1, strategy)
            self.assertEqual(updated.observation.hunters, (99,))
            self.assertIn(1, updated.observation.belief)

    def test_scenarios_reproducible_and_separated(self):
        rules = Rules(160, 120, 3, 18)
        for seed in range(20):
            state = scenario(self.grid, rules, seed)
            self.assertEqual(state, scenario(self.grid, rules, seed))
            self.assertEqual(len(state.observation.exits), 3)
            self.assertEqual(len(state.observation.hunters), 2)
            for exit_node in state.observation.exits:
                self.assertGreater(self.grid.distance(state.runner, exit_node), 2 * rules.runner_budget)

    def test_impossible_scenario_fails_clearly(self):
        with self.assertRaises(ValueError):
            scenario(self.arena, Rules(9999, 9999))

    def test_all_difficulty_budgets_have_scenarios(self):
        for runner in (80, 120, 160, 180):
            for hunter in (80, 120, 180):
                scenario(self.grid, Rules(runner, hunter), 7)

    def test_random_games_preserve_truth_and_movement_invariants(self):
        for strategy in STRATEGIES:
            for seed in range(16):
                rng = Random(seed)
                state = scenario(self.grid, Rules(160, 120, 3, 12), seed)
                while state.status == "playing":
                    previous = state
                    destination = rng.choice(self.grid.reachable(state.runner, 160))
                    state = step(self.grid, state, destination, strategy)
                    self.assertEqual(state.observation.turn, previous.observation.turn + 1)
                    self.assertIn(state.runner, state.observation.belief)
                    for source, target in zip(previous.observation.hunters, state.observation.hunters):
                        self.assertLessEqual(self.grid.distance(source, target), 120 + 1e-8)
                    if state.status == "playing":
                        self.assertNotIn(state.runner, state.observation.hunters)
                        self.assertNotIn(state.runner, state.observation.exits)
                        self.assertTrue(state.observation.belief.isdisjoint(state.observation.hunters))
                self.assertLessEqual(state.observation.turn, 12)

    def test_edge_subdivision_preserves_cost_direction_and_reverse_access(self):
        graph = line_graph()
        divided = split_long_edges(graph, 40)
        self.assertAlmostEqual(nx.shortest_path_length(divided, 0, 11, weight="length"), 1100)
        self.assertTrue(nx.is_strongly_connected(divided))
        self.assertLessEqual(max(d["length"] for _, _, d in divided.edges(data=True)), 40)
        directed = split_long_edges(line_graph(True), 40)
        self.assertFalse(nx.has_path(directed, 11, 0))

    def test_subdivision_invalid_limit(self):
        for limit in (0, -1, inf, float("nan")):
            with self.assertRaises(ValueError):
                split_long_edges(line_graph(), limit)

    def test_map_renders_without_tiles_and_does_not_mutate_state(self):
        state = scenario(self.grid, Rules(160, 120), 7)
        before = state
        html = game_map(self.grid, state, tiles=False).get_root().render()
        for label in ("BẠN", "ĐỘI 1", "THOÁT 3", "leaflet"):
            self.assertIn(label, html)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
