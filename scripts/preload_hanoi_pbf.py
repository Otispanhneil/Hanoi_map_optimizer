"""Tạo graph Hà Nội cục bộ từ tệp Geofabrik PBF, không dùng Overpass."""
import argparse
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import networkx as nx
import osmnx as ox
from pyrosm import OSM

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.popular_locations import POPULAR_LOCATIONS
from src.constants import (
    BUNDLED_GRAPH_FAST_PATH,
    BUNDLED_GRAPH_METADATA_PATH,
    BUNDLED_GRAPH_PATH,
    HANOI_ENVELOPE,
    HANOI_PBF_PATH,
)
from src.map_service import add_travel_times, snap_locations
from src.utils import Location, UserFacingError


# Các điểm kiểm tra đại diện cho trung tâm, phía tây và phía bắc Hà Nội.
VALIDATION_LOCATIONS = [
    *POPULAR_LOCATIONS,
    Location("Hòa Lạc", 21.0092, 105.5250),
    Location("Sơn Tây", 21.1398, 105.5045),
    Location("Sóc Sơn", 21.2577, 105.8490),
]


def build_graph_from_pbf(pbf_path: Path, bbox: tuple[float, float, float, float]) -> nx.MultiDiGraph:
    if not pbf_path.is_file():
        raise UserFacingError(f"Không tìm thấy tệp PBF: {pbf_path}")
    osm = OSM(str(pbf_path), bounding_box=list(bbox), keep_metadata=False,
              engine="out_of_core", progress=True)
    graph = osm.get_graph(
        network_type="driving",
        graph_type="networkx",
        retain_all=False,
        osmnx_compatible=True,
        simplify=True,
    )
    if not isinstance(graph, nx.MultiDiGraph) or graph.number_of_edges() == 0:
        raise UserFacingError("Không trích được mạng đường ô tô từ tệp PBF.")
    graph.graph["crs"] = "EPSG:4326"
    graph = add_travel_times(graph)
    component = max(nx.strongly_connected_components(graph), key=len)
    return compact_graph(graph.subgraph(component).copy())


def compact_graph(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Chỉ giữ thuộc tính cần lúc chạy để giảm thời gian đọc pickle và RAM."""
    graph.graph.clear()
    graph.graph.update({"crs": "EPSG:4326", "simplified": True})
    for _, data in graph.nodes(data=True):
        x, y = float(data["x"]), float(data["y"])
        data.clear()
        data.update({"x": x, "y": y})
    for _, _, data in graph.edges(data=True):
        retained = {
            "length": float(data["length"]),
            "travel_time": float(data["travel_time"]),
        }
        if data.get("geometry") is not None:
            retained["geometry"] = data["geometry"]
        data.clear()
        data.update(retained)
    return graph


def validate_graph(graph: nx.MultiDiGraph) -> None:
    nodes, distances = snap_locations(graph, VALIDATION_LOCATIONS)
    if any(distance > 1500 for distance in distances):
        raise UserFacingError("Graph PBF không phủ đủ các điểm kiểm tra Hà Nội.")
    origin = nodes[0]
    if not all(nx.has_path(graph, origin, node) and nx.has_path(graph, node, origin)
               for node in nodes[1:]):
        raise UserFacingError("Graph PBF chưa liên thông hai chiều giữa các vùng kiểm tra.")


def write_bundle(graph: nx.MultiDiGraph, bbox: tuple[float, float, float, float],
                 source: Path) -> None:
    graphml_temporary = BUNDLED_GRAPH_PATH.with_suffix(".tmp.graphml")
    pickle_temporary = BUNDLED_GRAPH_FAST_PATH.with_suffix(".tmp.pkl")
    metadata_temporary = BUNDLED_GRAPH_METADATA_PATH.with_suffix(".tmp.json")
    BUNDLED_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        ox.io.save_graphml(graph, graphml_temporary)
        with pickle_temporary.open("wb") as stream:
            pickle.dump(graph, stream, protocol=pickle.HIGHEST_PROTOCOL)
        metadata_temporary.write_text(json.dumps({
            "profile": "hanoi-pbf",
            "bbox": bbox,
            "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(),
            "source": source.name,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(graphml_temporary, BUNDLED_GRAPH_PATH)
        os.replace(pickle_temporary, BUNDLED_GRAPH_FAST_PATH)
        os.replace(metadata_temporary, BUNDLED_GRAPH_METADATA_PATH)
    finally:
        graphml_temporary.unlink(missing_ok=True)
        pickle_temporary.unlink(missing_ok=True)
        metadata_temporary.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tạo graph Hà Nội ngoại tuyến từ OSM PBF.")
    parser.add_argument("--pbf", type=Path, default=HANOI_PBF_PATH,
                        help="Đường dẫn tới vietnam-latest.osm.pbf")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started = perf_counter()
    print(f"Đang đọc {args.pbf} và trích mạng đường Hà Nội…", flush=True)
    graph = build_graph_from_pbf(args.pbf, HANOI_ENVELOPE)
    print(f"Đã trích {graph.number_of_nodes():,} nút; đang kiểm tra liên thông…", flush=True)
    validate_graph(graph)
    write_bundle(graph, HANOI_ENVELOPE, args.pbf)
    print(
        f"Hoàn tất trong {perf_counter() - started:.1f} giây: "
        f"{graph.number_of_nodes():,} nút, {graph.number_of_edges():,} cạnh.",
        flush=True,
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except UserFacingError as exc:
        print(f"Không thể tạo graph PBF: {exc}", flush=True)
        sys.exit(1)
