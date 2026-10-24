"""Benchmark tầng tối ưu thứ tự ghé: Held–Karp so với nearest-neighbor và 2-opt.

Đo trên graph Hà Nội đóng gói với số điểm tăng dần để kiểm chứng thực nghiệm
độ phức tạp O(n² 2ⁿ) và khoảng cách chất lượng của hai heuristic baseline.
"""
import argparse
import json
from pathlib import Path
import sys
from statistics import mean
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.popular_locations import POPULAR_LOCATIONS
from src.heuristics import nearest_neighbor, two_opt
from src.map_service import load_bundled_road_network, snap_locations
from src.shortest_path import build_cost_matrix
from src.tsp import solve_tsp
from src.utils import UserFacingError


def submatrix(matrix: list[list[float]], size: int) -> list[list[float]]:
    return [row[:size] for row in matrix[:size]]


def timed(call, repeats: int) -> tuple[object, float, float]:
    """Trả về (kết quả, thời gian trung bình ms, thời gian nhỏ nhất ms)."""
    samples = []
    value = None
    for _ in range(repeats):
        started = perf_counter()
        value = call()
        samples.append((perf_counter() - started) * 1000)
    return value, mean(samples), min(samples)


def measure(matrix: list[list[float]], mode: str, repeats: int, scale: float,
            unit: str) -> dict:
    size = len(matrix)
    end_index = size - 1 if mode == "fixed_end" else None
    closed = mode == "closed"
    (order, exact_cost), hk_mean, hk_min = timed(
        lambda: solve_tsp(matrix, end_index=end_index, return_to_start=closed), repeats)
    row = {
        "points": size,
        "destinations": size - 1,
        "route_mode": mode,
        "states": (1 << (size - 1)) * (size - 1),
        "exact_order": order,
        "unit": unit,
        "exact_cost": round(exact_cost / scale, 3),
        "held_karp_mean_ms": round(hk_mean, 3),
        "held_karp_min_ms": round(hk_min, 3),
    }
    try:
        (greedy_order, greedy_cost), nn_mean, _ = timed(
            lambda: nearest_neighbor(matrix, end_index=end_index, return_to_start=closed), repeats)
        (_, opt_cost), opt_mean, _ = timed(
            lambda: two_opt(greedy_order, matrix, fixed_end=mode == "fixed_end",
                            return_to_start=closed), repeats)
        row.update({
            "nn_cost": round(greedy_cost / scale, 3),
            "nn_gap_percent": round((greedy_cost / exact_cost - 1) * 100, 2),
            "nn_mean_ms": round(nn_mean, 3),
            "two_opt_cost": round(opt_cost / scale, 3),
            "two_opt_gap_percent": round((opt_cost / exact_cost - 1) * 100, 2),
            "two_opt_mean_ms": round(nn_mean + opt_mean, 3),
        })
    except UserFacingError as error:
        row["heuristic_error"] = str(error)
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight", default="length", choices=["length", "travel_time"])
    parser.add_argument("--min-points", type=int, default=4)
    parser.add_argument("--max-points", type=int, default=11)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", default="output/routing/benchmark-tsp.json")
    args = parser.parse_args()

    started = perf_counter()
    graph = load_bundled_road_network()
    load_seconds = perf_counter() - started

    locations = POPULAR_LOCATIONS[:args.max_points]
    nodes, snap_distances = snap_locations(graph, locations)
    started = perf_counter()
    full_matrix, _ = build_cost_matrix(graph, nodes, args.weight)
    matrix_seconds = perf_counter() - started

    scale, unit = (1000.0, "km") if args.weight == "length" else (60.0, "minute")
    rows, dijkstra_rows = [], []
    for size in range(args.min_points, args.max_points + 1):
        started = perf_counter()
        build_cost_matrix(graph, nodes[:size], args.weight)
        dijkstra_rows.append({"points": size,
                              "dijkstra_seconds": round(perf_counter() - started, 3)})
        matrix = submatrix(full_matrix, size)
        for mode in ("open", "fixed_end", "closed"):
            rows.append(measure(matrix, mode, args.repeats, scale, unit))

    payload = {
        "weight": args.weight,
        "repeats": args.repeats,
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "graph_load_seconds": round(load_seconds, 3),
        "full_matrix_seconds": round(matrix_seconds, 3),
        "max_snap_distance_m": round(max(snap_distances), 2),
        "locations": [location.name for location in locations],
        "dijkstra_scaling": dijkstra_rows,
        "results": rows,
        "status": "OK",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
