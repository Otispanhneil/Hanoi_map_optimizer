"""Tải trước mạng đường Hà Nội trước khi chạy ứng dụng.

Profile ``west`` chia vùng nội đô - Hòa Lạc thành các ô nhỏ. Mỗi ô được cache
riêng nên lệnh có thể chạy lại sau khi Overpass gián đoạn mà không tải lại các ô
đã hoàn thành.
"""
import argparse
import json
import os
import pickle
import sys
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from time import perf_counter

import networkx as nx
import osmnx as ox

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.popular_locations import POPULAR_LOCATIONS
from src.constants import (
    BUNDLED_GRAPH_FAST_PATH,
    BUNDLED_GRAPH_METADATA_PATH,
    BUNDLED_GRAPH_PATH,
    DEFAULT_MARGIN_KM,
)
from src.map_service import cache_aligned_bbox, load_road_network, selected_bbox
from src.utils import UserFacingError


PROFILES = {
    "urban": None,
    # Bao phủ hành lang nội đô - Hòa Lạc và các điểm trong test case mở rộng.
    "west": (105.40, 20.84, 105.91, 21.16),
}


def tiled_bboxes(bbox: tuple[float, float, float, float], tile_size: float = 0.10,
                 overlap: float = 0.005) -> list[tuple[float, float, float, float]]:
    """Chia bbox thành các ô có chồng mép để graph nối ổn định qua biên ô."""
    west, south, east, north = bbox
    columns = ceil((east - west) / tile_size)
    rows = ceil((north - south) / tile_size)
    tiles = []
    for row in range(rows):
        for column in range(columns):
            tile_west = max(west, west + column * tile_size - overlap)
            tile_south = max(south, south + row * tile_size - overlap)
            tile_east = min(east, west + (column + 1) * tile_size + overlap)
            tile_north = min(north, south + (row + 1) * tile_size + overlap)
            tiles.append(cache_aligned_bbox((tile_west, tile_south, tile_east, tile_north)))
    return list(dict.fromkeys(tiles))


def profile_bbox(profile: str) -> tuple[float, float, float, float]:
    bbox = PROFILES[profile]
    if bbox is None:
        bbox = selected_bbox(POPULAR_LOCATIONS, DEFAULT_MARGIN_KM)
    return cache_aligned_bbox(bbox)


def build_profile_graph(profile: str, tile_size: float) -> tuple[nx.MultiDiGraph, tuple]:
    bbox = profile_bbox(profile)
    tiles = [bbox] if profile == "urban" else tiled_bboxes(bbox, tile_size)
    combined = nx.MultiDiGraph()
    for index, tile in enumerate(tiles, start=1):
        print(f"[{index}/{len(tiles)}] Đọc/tải ô {tile}…", flush=True)
        combined = nx.compose(combined, load_road_network(tile))
    component = max(nx.strongly_connected_components(combined), key=len)
    return combined.subgraph(component).copy(), bbox


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chuẩn bị graph định tuyến Hà Nội cục bộ.")
    parser.add_argument("--profile", choices=PROFILES, default="urban",
                        help="urban: nội đô; west: nội đô đến Hòa Lạc")
    parser.add_argument("--tile-size", type=float, default=0.10,
                        help="Kích thước ô tải theo độ cho profile west (mặc định 0.10).")
    args = parser.parse_args()
    if not 0.04 <= args.tile_size <= 0.15:
        parser.error("--tile-size phải nằm trong khoảng 0.04 đến 0.15 độ.")
    return args


def main() -> None:
    args = parse_args()
    print(f"Đang chuẩn bị mạng đường Hà Nội (profile: {args.profile})…", flush=True)
    started = perf_counter()
    graph, bbox = build_profile_graph(args.profile, args.tile_size)
    temporary = BUNDLED_GRAPH_PATH.with_suffix(".tmp.graphml")
    fast_temporary = BUNDLED_GRAPH_FAST_PATH.with_suffix(".tmp.pkl")
    metadata_temporary = BUNDLED_GRAPH_METADATA_PATH.with_suffix(".tmp.json")
    BUNDLED_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    ox.io.save_graphml(graph, temporary)
    with fast_temporary.open("wb") as stream:
        pickle.dump(graph, stream, protocol=pickle.HIGHEST_PROTOCOL)
    metadata_temporary.write_text(json.dumps({
        "profile": args.profile,
        "bbox": bbox,
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    # Chỉ thay gói đang chạy sau khi cả ba tệp đã được tạo thành công.
    os.replace(temporary, BUNDLED_GRAPH_PATH)
    os.replace(fast_temporary, BUNDLED_GRAPH_FAST_PATH)
    os.replace(metadata_temporary, BUNDLED_GRAPH_METADATA_PATH)
    elapsed = perf_counter() - started
    print(
        f"Hoàn tất trong {elapsed:.1f} giây: "
        f"{graph.number_of_nodes():,} nút, {graph.number_of_edges():,} cạnh.",
        flush=True,
    )
    print(f"Dữ liệu đóng gói đã sẵn sàng tại {BUNDLED_GRAPH_PATH}.", flush=True)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        main()
    except UserFacingError as exc:
        print(f"Không thể preload: {exc}", flush=True)
        sys.exit(1)
