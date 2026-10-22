from dataclasses import dataclass
from time import perf_counter

import networkx as nx

from src.heuristics import nearest_neighbor, two_opt
from src.shortest_path import build_cost_matrix, path_edges
from src.tsp import solve_tsp
from src.utils import Location, UserFacingError, validate_selection


@dataclass
class RouteResult:
    locations: list[Location]
    order: list[int]
    cost: float
    weight: str
    cost_matrix: list[list[float]]
    legs: list[dict]
    distance_m: float
    travel_time_s: float
    dijkstra_seconds: float
    tsp_seconds: float
    road_coordinates: list[list[tuple[float, float]]]
    snapped_coordinates: list[tuple[float, float]]
    snap_distances: list[float]
    route_mode: str
    comparisons: list[dict]


def optimize_route(graph: nx.MultiDiGraph, locations: list[Location], nodes: list,
                   weight: str = "length", snap_distances: list[float] | None = None,
                   route_mode: str = "open", end_index: int | None = None) -> RouteResult:
    """Tối ưu trên graph đã tải; runtime thuật toán không chứa thời gian mạng."""
    validate_selection(locations[0] if locations else None, locations[1:])
    if len(nodes) != len(locations):
        raise ValueError("Số node và số địa điểm không khớp.")
    if route_mode not in {"open", "fixed_end", "closed"}:
        raise ValueError("Kiểu hành trình không hợp lệ.")
    if route_mode == "fixed_end" and end_index is None:
        raise ValueError("Cần chọn điểm kết thúc.")
    if route_mode != "fixed_end":
        end_index = None
    started = perf_counter()
    matrix, paths = build_cost_matrix(graph, nodes, weight)
    dijkstra_seconds = perf_counter() - started
    started = perf_counter()
    order, cost = solve_tsp(
        matrix,
        end_index=end_index,
        return_to_start=route_mode == "closed",
    )
    tsp_seconds = perf_counter() - started

    comparisons = [{"algorithm": "Held–Karp", "cost": cost,
                    "runtime_ms": tsp_seconds * 1000, "gap_percent": 0.0}]
    try:
        started = perf_counter()
        greedy_order, greedy_cost = nearest_neighbor(
            matrix, end_index=end_index, return_to_start=route_mode == "closed"
        )
        greedy_seconds = perf_counter() - started
        comparisons.append({"algorithm": "Nearest Neighbor", "cost": greedy_cost,
                            "runtime_ms": greedy_seconds * 1000,
                            "gap_percent": (greedy_cost / cost - 1) * 100 if cost else 0.0})
        started = perf_counter()
        _, improved_cost = two_opt(
            greedy_order, matrix,
            fixed_end=route_mode == "fixed_end",
            return_to_start=route_mode == "closed",
        )
        two_opt_seconds = perf_counter() - started
        comparisons.append({"algorithm": "Nearest Neighbor + 2-opt", "cost": improved_cost,
                            "runtime_ms": (greedy_seconds + two_opt_seconds) * 1000,
                            "gap_percent": (improved_cost / cost - 1) * 100 if cost else 0.0})
    except UserFacingError:
        # Heuristic có thể thất bại trên graph có hướng dù Held–Karp vẫn có nghiệm.
        pass

    legs, coordinates = [], []
    for source, target in zip(order, order[1:]):
        edges = path_edges(graph, paths[source, target], weight)
        length = sum(float(data["length"]) for _, _, _, data in edges)
        travel_time = sum(float(data["travel_time"]) for _, _, _, data in edges)
        legs.append({"from": locations[source].name, "to": locations[target].name,
                     "distance_m": length, "travel_time_s": travel_time})
        for u, v, _, data in edges:
            geometry = data.get("geometry")
            if geometry is not None:
                segment = [(float(y), float(x)) for x, y in geometry.coords]
                origin = (graph.nodes[u]["y"], graph.nodes[u]["x"])
                # Một số geometry lưu theo chiều ngược của cạnh.
                if sum((a - b) ** 2 for a, b in zip(segment[-1], origin)) < sum((a - b) ** 2 for a, b in zip(segment[0], origin)):
                    segment.reverse()
            else:
                # Cạnh OSM chưa gộp chỉ có hai node: đoạn thẳng chính là geometry cạnh.
                segment = [(graph.nodes[u]["y"], graph.nodes[u]["x"]),
                           (graph.nodes[v]["y"], graph.nodes[v]["x"])]
            coordinates.append(segment)
    return RouteResult(
        locations, order, cost, weight, matrix, legs,
        sum(leg["distance_m"] for leg in legs), sum(leg["travel_time_s"] for leg in legs),
        dijkstra_seconds, tsp_seconds, coordinates,
        [(float(graph.nodes[node]["y"]), float(graph.nodes[node]["x"])) for node in nodes],
        snap_distances or [0.0] * len(nodes),
        route_mode, comparisons,
    )
