"""Turn-based pursuit with an explicit information boundary and metric movement."""
from dataclasses import dataclass, replace
from itertools import product
from math import isfinite
from numbers import Real

import networkx as nx

from src.shortest_path import multi_target_dijkstra


STRATEGIES = ("trail", "search", "contain")


@dataclass(frozen=True)
class Rules:
    runner_budget: float = 160
    hunter_budget: float = 160
    reveal_every: int = 3
    max_turns: int = 18

    def __post_init__(self):
        for value in (self.runner_budget, self.hunter_budget):
            if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(value) or value <= 0:
                raise ValueError("Ngân sách di chuyển phải hữu hạn và lớn hơn 0.")
        for value in (self.reveal_every, self.max_turns):
            if type(value) is not int or value < 1:
                raise ValueError("Chu kỳ tiết lộ và số lượt phải là số nguyên dương.")


@dataclass(frozen=True)
class Observation:
    """Everything the policy may know; never contains the hidden runner position."""
    turn: int
    hunters: tuple
    exits: tuple
    belief: frozenset
    last_seen: object
    last_seen_turn: int
    rules: Rules


@dataclass(frozen=True)
class State:
    runner: object
    observation: Observation
    status: str = "playing"
    runner_path: tuple = ()
    hunter_paths: tuple = ()
    targets: tuple = ()
    explanation: str = "Vị trí xuất phát đã được tiết lộ."


class Arena:
    """Small, immutable road graph with reusable Dijkstra distances and paths."""

    def __init__(self, graph):
        if not isinstance(graph, nx.MultiDiGraph) or not 3 <= len(graph) <= 600:
            raise ValueError("Sân chơi cần MultiDiGraph có từ 3 đến 600 nút.")
        try:
            for _, data in graph.nodes(data=True):
                if not all(isfinite(float(data.get(key, float("nan")))) for key in ("x", "y")):
                    raise ValueError("Nút đường thiếu tọa độ hữu hạn.")
            for _, _, data in graph.edges(data=True):
                length = float(data.get("length", float("nan")))
                if not isfinite(length) or length <= 0:
                    raise ValueError("Chiều dài đường phải hữu hạn và lớn hơn 0.")
        except (TypeError, OverflowError) as exc:
            raise ValueError("Tọa độ hoặc chiều dài đường không hợp lệ.") from exc
        self.graph = nx.freeze(graph.copy())
        self.nodes = tuple(graph)
        self.rank = {node: index for index, node in enumerate(self.nodes)}
        self.distances, self.paths = {}, {}
        for source in self.nodes:
            distances, paths = multi_target_dijkstra(self.graph, source, set(self.nodes))
            self.distances[source] = distances
            self.paths[source] = paths

    def distance(self, source, target):
        return self.distances[source].get(target, float("inf"))

    def reachable(self, source, budget):
        return tuple(node for node in self.nodes if self.distance(source, node) <= budget + 1e-8)

    def expand(self, nodes, budget):
        return frozenset(target for source in nodes for target in self.reachable(source, budget))

    def advance(self, source, target, budget):
        path = self.paths[source].get(target, [source])
        reachable = [node for node in path if self.distance(source, node) <= budget + 1e-8]
        return reachable[-1]


def new_game(arena, runner, hunters, exits, rules=None):
    rules = rules or Rules()
    hunters, exits = tuple(hunters), tuple(exits)
    if runner not in arena.graph or any(n not in arena.graph for n in (*hunters, *exits)):
        raise ValueError("Vị trí không thuộc sân chơi.")
    if not 1 <= len(hunters) <= 2 or len(set(hunters)) != len(hunters):
        raise ValueError("Cần một hoặc hai đội ở các vị trí khác nhau.")
    if not exits or len(set(exits)) != len(exits):
        raise ValueError("Cần các lối thoát khác nhau.")
    if runner in hunters or runner in exits or set(hunters) & set(exits):
        raise ValueError("Các vị trí xuất phát và lối thoát không được trùng nhau.")
    if not any(isfinite(arena.distance(runner, exit_node)) for exit_node in exits):
        raise ValueError("Người trốn không thể tới bất kỳ lối thoát nào.")
    observation = Observation(0, hunters, exits, frozenset({runner}), runner, 0, rules)
    return State(runner, observation)


def hunter_decision(arena, observation, strategy):
    """A pure policy: its entire input is public knowledge, not State."""
    if strategy not in STRATEGIES:
        raise ValueError("Chiến thuật không hợp lệ.")
    hunters, belief = observation.hunters, observation.belief
    budget = observation.rules.hunter_budget
    if not belief:
        raise ValueError("Vùng nghi ngờ không được rỗng.")
    if strategy == "trail":
        targets = (observation.last_seen,) * len(hunters)
        moves = tuple(arena.advance(h, t, budget) for h, t in zip(hunters, targets))
        return moves, targets, "Đuổi tới vị trí được tiết lộ gần nhất."

    # Reciprocal distances stay finite even on directed, disconnected graphs.
    def coverage(node, points):
        return sum(1 / (1 + arena.distance(node, p) / budget) for p in points) / len(points)

    pools = []
    for hunter in hunters:
        options = sorted(arena.reachable(hunter, budget),
                         key=lambda n: (-coverage(n, belief), arena.rank[n]))
        pools.append(options[:8])
    if strategy == "search":
        moves = tuple(options[0] for options in pools)
        return moves, moves, "Mỗi đội chọn vị trí bao phủ vùng nghi ngờ tốt nhất."

    def joint_score(moves):
        belief_score = sum(max(1 / (1 + arena.distance(m, p) / budget) for m in moves)
                           for p in belief) / len(belief)
        exit_score = sum(max(1 / (1 + arena.distance(m, e) / budget) for m in moves)
                         for e in observation.exits) / len(observation.exits)
        return belief_score + 0.35 * exit_score

    # Include exit-directed moves so the coverage shortlist cannot hide a blockade.
    for index, hunter in enumerate(hunters):
        pools[index] = list(dict.fromkeys([
            *pools[index], *(arena.advance(hunter, e, budget) for e in observation.exits)
        ]))
    moves = max(product(*pools), key=joint_score)
    return moves, moves, "Phối hợp bao phủ vùng nghi ngờ và tiếp cận các lối thoát (heuristic)."


def step(arena, state, destination, strategy="contain"):
    """Runner moves first; collisions at endpoints precede escape; timeout loses."""
    if strategy not in STRATEGIES:
        raise ValueError("Chiến thuật không hợp lệ.")
    if state.status != "playing":
        raise ValueError("Ván đã kết thúc. Hãy bắt đầu ván mới.")
    obs = state.observation
    if destination not in arena.graph or destination not in arena.reachable(state.runner, obs.rules.runner_budget):
        raise ValueError("Điểm đến nằm ngoài ngân sách hoặc không thể tới theo chiều đường.")
    turn = obs.turn + 1
    belief = arena.expand(obs.belief, obs.rules.runner_budget)
    revealed = turn % obs.rules.reveal_every == 0
    if revealed:
        belief = frozenset({destination})
    obs = replace(obs, turn=turn, belief=belief,
                  last_seen=destination if revealed else obs.last_seen,
                  last_seen_turn=turn if revealed else obs.last_seen_turn)
    runner_path = tuple(arena.paths[state.runner][destination])
    if destination in obs.hunters or destination in obs.exits:
        status = "caught" if destination in obs.hunters else "escaped"
        obs = replace(obs, belief=frozenset({destination}), last_seen=destination, last_seen_turn=turn)
        return State(destination, obs, status, runner_path,
                     tuple((h,) for h in obs.hunters), (), "Ván kết thúc sau bước di chuyển của người trốn.")
    # Surviving the runner phase also rules out all currently occupied hunter nodes.
    obs = replace(obs, belief=obs.belief.difference(obs.hunters))
    moves, targets, explanation = hunter_decision(arena, obs, strategy)
    paths = tuple(tuple(arena.paths[h][m]) for h, m in zip(obs.hunters, moves))
    status = "caught" if destination in moves else ("timeout" if turn >= obs.rules.max_turns else "playing")
    belief = frozenset({destination}) if status != "playing" else obs.belief.difference(moves)
    obs = replace(obs, hunters=tuple(moves), belief=belief)
    if status != "playing":
        obs = replace(obs, last_seen=destination, last_seen_turn=turn)
    return State(destination, obs, status, runner_path, paths, tuple(targets), explanation)
