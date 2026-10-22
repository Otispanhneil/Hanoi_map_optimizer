"""Dijkstra trên MultiDiGraph: giữ nguyên chiều đường và cạnh song song."""
from math import inf, isfinite
from heapq import heappop, heappush
from itertools import count
from typing import Hashable

import networkx as nx

from src.utils import UserFacingError


def validate_weights(graph: nx.MultiDiGraph, weight: str) -> None:
    if weight not in {"length", "travel_time"}:
        raise ValueError("Trọng số phải là length hoặc travel_time.")
    for _, _, data in graph.edges(data=True):
        value = data.get(weight)
        if value is None or not isfinite(float(value)) or float(value) < 0:
            raise UserFacingError("Dữ liệu đường có trọng số thiếu hoặc không hợp lệ. Hãy tải lại dữ liệu.")


def shortest_path(graph: nx.MultiDiGraph, source: Hashable, target: Hashable,
                  weight: str = "length") -> tuple[list, float]:
    """Tìm đường ngắn nhất bằng Dijkstra, trả (node path, cost)."""
    distances, paths = multi_target_dijkstra(graph, source, {target}, weight)
    if target not in distances:
        raise UserFacingError("Không tìm được đường ô tô giữa hai điểm đã chọn.")
    return paths[target], distances[target]


def _edge_cost(parallel_edges: dict, weight: str) -> float:
    best = inf
    for data in parallel_edges.values():
        value = data.get(weight)
        if value is None or not isfinite(float(value)) or float(value) < 0:
            raise UserFacingError("Dữ liệu đường có trọng số thiếu hoặc không hợp lệ. Hãy tải lại dữ liệu.")
        best = min(best, float(value))
    return best


def multi_target_dijkstra(graph: nx.MultiDiGraph, source: Hashable, targets: set,
                          weight: str = "length") -> tuple[dict, dict]:
    """Dijkstra một nguồn, dừng ngay khi đã chốt đủ các đích cần thiết."""
    if weight not in {"length", "travel_time"}:
        raise ValueError("Trọng số phải là length hoặc travel_time.")
    if source not in graph:
        raise UserFacingError("Không tìm thấy nút đường tương ứng địa điểm.")
    remaining = set(targets)
    distances: dict = {}
    tentative = {source: 0.0}
    previous = {source: None}
    tie_breaker = count()
    queue = [(0.0, next(tie_breaker), source)]
    while queue and remaining:
        distance, _, node = heappop(queue)
        if node in distances:
            continue
        distances[node] = distance
        remaining.discard(node)
        for neighbor, edges in graph.adj[node].items():
            candidate = distance + _edge_cost(edges, weight)
            if neighbor in distances:
                continue
            if candidate < tentative.get(neighbor, inf):
                tentative[neighbor] = candidate
                previous[neighbor] = node
                heappush(queue, (candidate, next(tie_breaker), neighbor))
    paths = {}
    for target in set(targets) - remaining:
        path = []
        node = target
        while node is not None:
            path.append(node)
            node = previous[node]
        paths[target] = list(reversed(path))
    return distances, paths


def build_cost_matrix(graph: nx.MultiDiGraph, nodes: list,
                      weight: str = "length") -> tuple[list[list[float]], dict]:
    """Chạy một Dijkstra mỗi nguồn; lưu path cho từng cặp chỉ số địa điểm.

    Cặp không tới được có chi phí +inf. Không yêu cầu graph liên thông mạnh:
    một Open TSP vẫn có thể tồn tại dù không thể đi ngược từ điểm cuối.
    """
    if weight not in {"length", "travel_time"}:
        raise ValueError("Trọng số phải là length hoặc travel_time.")
    size = len(nodes)
    matrix = [[inf] * size for _ in range(size)]
    paths = {}
    for i, source in enumerate(nodes):
        lengths, source_paths = multi_target_dijkstra(graph, source, set(nodes), weight)
        for j, target in enumerate(nodes):
            if target in lengths:
                matrix[i][j] = float(lengths[target])
                paths[i, j] = source_paths[target]
    return matrix, paths


def path_edges(graph: nx.MultiDiGraph, path: list, weight: str) -> list[tuple]:
    """Lấy đúng cạnh song song có chi phí nhỏ nhất theo tiêu chí Dijkstra."""
    edges = []
    for source, target in zip(path, path[1:]):
        candidates = graph[source][target]
        key = min(candidates, key=lambda key: candidates[key][weight])
        edges.append((source, target, key, candidates[key]))
    return edges
