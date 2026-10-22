"""Smoke test opt-in với dịch vụ thật; không chạy trong bộ test offline."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.geocoding import ensure_in_hanoi, search_location
from src.map_service import load_road_network, selected_bbox, snap_locations
from src.route_optimizer import optimize_route
from src.utils import Location, UserFacingError
from src.visualization import create_map


def main():
    locations = [Location("Hoan Kiem", 21.0300, 105.8535),
                 Location("Nha hat Lon", 21.0242, 105.8575)]
    print("Checking Hanoi boundary...", flush=True)
    for location in locations:
        ensure_in_hanoi(location)
    print("Searching a Hanoi address...", flush=True)
    search_failed = False
    try:
        found = search_location("Nhà hát Lớn Hà Nội")
        print(f"Search coordinate: {found.lat:.5f}, {found.lon:.5f}", flush=True)
    except UserFacingError as exc:
        search_failed = True
        print(f"Address search failed; continuing road-network check: {exc.__cause__}", flush=True)
    print("Loading small real driving network...", flush=True)
    graph = load_road_network(selected_bbox(locations, 2))
    nodes, distances = snap_locations(graph, locations)
    for weight in ["length", "travel_time"]:
        result = optimize_route(graph, locations, nodes, weight, distances)
        assert result.order == [0, 1]
        assert result.distance_m > 0 and result.travel_time_s > 0
        assert result.road_coordinates
        html = create_map(locations[0], locations[1:], result).get_root().render()
        assert "polyline" in html
        print(json.dumps({"weight": weight, "nodes": len(graph), "edges": graph.number_of_edges(),
                          "distance_m": result.distance_m, "time_s": result.travel_time_s,
                          "dijkstra_ms": result.dijkstra_seconds * 1000,
                          "tsp_ms": result.tsp_seconds * 1000}), flush=True)
    print("Live OSM pipeline OK", flush=True)
    if search_failed:
        print("Routing passed, but address search needs a successful retry.", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except UserFacingError as exc:
        print(f"Live check could not finish: {exc}", flush=True)
        print(f"Underlying service error: {exc.__cause__}", flush=True)
        sys.exit(1)
