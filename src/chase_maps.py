"""Offline demo and a bounded, versioned OSM arena for the chase game."""
from math import ceil, isfinite
from pathlib import Path

import networkx as nx
import osmnx as ox
from shapely.geometry import LineString
from shapely.ops import substring

from src.chase import Arena, new_game


MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "chase_hanoi.graphml"


def demo_graph():
    """Explicitly synthetic, geographically placed grid; never claimed as OSM."""
    graph = nx.MultiDiGraph(crs="EPSG:4326", source="Mạng ô lưới mô phỏng — không phải đường thực tế")
    for row in range(9):
        for col in range(9):
            graph.add_node(row * 9 + col, x=105.845 + col * .00077,
                           y=21.030 + row * .00072, name=f"Ô {row + 1}–{col + 1}")
    for row in range(9):
        for col in range(9):
            node = row * 9 + col
            for dr, dc in ((0, 1), (1, 0)):
                nr, nc = row + dr, col + dc
                if nr < 9 and nc < 9:
                    target = nr * 9 + nc
                    graph.add_edge(node, target, length=80.0)
                    graph.add_edge(target, node, length=80.0)
    return graph


def split_long_edges(graph, limit=90):
    """Add intermediate endpoints without changing edge length or direction."""
    if not isfinite(limit) or limit <= 0:
        raise ValueError("Độ dài phân đoạn phải hữu hạn và dương.")
    result = nx.MultiDiGraph(**graph.graph)
    result.add_nodes_from(graph.nodes(data=True))
    next_node = min(0, *graph.nodes) - 1
    coordinate_nodes = {(round(d["x"], 10), round(d["y"], 10)): n
                        for n, d in graph.nodes(data=True)}
    for u, v, data in graph.edges(data=True):
        length = float(data["length"])
        pieces = max(1, ceil(length / limit))
        a, b = graph.nodes[u], graph.nodes[v]
        line = data.get("geometry", LineString([(a["x"], a["y"]), (b["x"], b["y"])]))
        if LineString(line.coords).length == 0:
            continue
        if (line.coords[0][0] - a["x"]) ** 2 + (line.coords[0][1] - a["y"]) ** 2 > (
                (line.coords[-1][0] - a["x"]) ** 2 + (line.coords[-1][1] - a["y"]) ** 2):
            line = LineString(list(line.coords)[::-1])
        previous = u
        for index in range(1, pieces + 1):
            target = v if index == pieces else next_node
            if index != pieces:
                point = line.interpolate(index / pieces, normalized=True)
                coordinate = (round(point.x, 10), round(point.y, 10))
                if coordinate in coordinate_nodes:
                    target = coordinate_nodes[coordinate]
                else:
                    result.add_node(target, x=point.x, y=point.y)
                    coordinate_nodes[coordinate] = target
                    next_node -= 1
            segment = substring(line, (index - 1) / pieces, index / pieces, normalized=True)
            result.add_edge(previous, target, length=length / pieces,
                            geometry=segment, name=str(data.get("name", "Đường nối")))
            previous = target
    return result


def load_arena(source="demo"):
    if source == "demo":
        return Arena(demo_graph())
    if source != "osm":
        raise ValueError("Nguồn sân chơi không hợp lệ.")
    if not MAP_PATH.is_file():
        raise ValueError("Chưa có graph nhỏ. Chạy scripts/prepare_chase_map.py hoặc chọn sân mô phỏng.")
    return Arena(ox.load_graphml(MAP_PATH))


def scenario(arena, rules, seed=0):
    """Seeded starting locations; exits stay several turns from the runner."""
    from random import Random
    rng = Random(seed)
    candidates = [n for n in arena.nodes if len(arena.reachable(n, rules.hunter_budget)) > 1]
    rng.shuffle(candidates)
    for runner in candidates:
        far = [n for n in candidates if arena.distance(runner, n) > rules.runner_budget * 2
               and arena.distance(runner, n) < float("inf")]
        if len(far) < 5:
            continue
        exits = [far[0]]
        for node in far[1:]:
            if min(arena.distance(node, e) for e in exits) >= rules.runner_budget:
                exits.append(node)
            if len(exits) == 3:
                break
        if len(exits) < 3:
            continue
        hunters = [n for n in far if n not in exits and
                   min(arena.distance(n, e) for e in exits) > rules.hunter_budget]
        if len(hunters) >= 2:
            return new_game(arena, runner, hunters[:2], exits, rules)
    raise ValueError("Sân quá nhỏ cho cấu hình này. Hãy giảm ngân sách di chuyển.")
