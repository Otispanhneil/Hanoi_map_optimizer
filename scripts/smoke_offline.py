"""Kiểm tra nhanh toàn bộ pipeline bằng graph Hà Nội đóng gói, không cần Internet."""
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.popular_locations import POPULAR_LOCATIONS
from src.map_service import load_bundled_road_network, snap_locations
from src.route_optimizer import optimize_route


def main() -> None:
    started = perf_counter()
    graph = load_bundled_road_network()
    load_seconds = perf_counter() - started
    if graph.number_of_nodes() < 30_000 or graph.number_of_edges() < 50_000:
        raise RuntimeError("Graph đóng gói nhỏ bất thường.")

    locations = POPULAR_LOCATIONS[:5]
    nodes, snap_distances = snap_locations(graph, locations)
    results = []
    for weight in ("length", "travel_time"):
        result = optimize_route(graph, locations, nodes, weight, snap_distances)
        expected_cost = result.distance_m if weight == "length" else result.travel_time_s
        if abs(result.cost - expected_cost) > 1e-6:
            raise RuntimeError(f"Tổng chi phí {weight} không khớp với các chặng.")
        results.append({
            "weight": weight,
            "order": result.order,
            "cost": round(result.cost, 3),
            "distance_km": round(result.distance_m / 1000, 3),
            "travel_time_min": round(result.travel_time_s / 60, 2),
            "dijkstra_seconds": round(result.dijkstra_seconds, 3),
            "tsp_milliseconds": round(result.tsp_seconds * 1000, 3),
        })

    print(json.dumps({
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "graph_load_seconds": round(load_seconds, 3),
        "max_snap_distance_m": round(max(snap_distances), 2),
        "locations": [location.name for location in locations],
        "results": results,
        "status": "OK",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
