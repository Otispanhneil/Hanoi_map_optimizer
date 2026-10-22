"""Tải graph ô tô theo vùng cần thiết, cache RAM và GraphML trên ổ đĩa."""
import hashlib
import json
import logging
import os
import pickle
from concurrent.futures import Future, ThreadPoolExecutor
from math import ceil, cos, floor, radians
from threading import Lock
from uuid import uuid4

import networkx as nx
import osmnx as ox
import streamlit as st

from src.constants import (
    BUNDLED_GRAPH_PATH,
    BUNDLED_GRAPH_FAST_PATH,
    BUNDLED_GRAPH_METADATA_PATH,
    BUNDLED_ROUTING_BBOX,
    CACHE_DIR,
    DEFAULT_SPEED_KPH,
    MAX_DYNAMIC_BBOX_AREA_KM2,
    MAX_DYNAMIC_BBOX_SIDE_KM,
    MAX_SNAP_DISTANCE_M,
    ROAD_SPEEDS,
)
from src.utils import Location, UserFacingError

logger = logging.getLogger(__name__)

# Căn bbox theo lưới xấp xỉ 1,1 km. Các lựa chọn gần nhau nhờ vậy dùng chung
# cache thay vì tạo một tệp GraphML mới cho từng thay đổi tọa độ rất nhỏ.
BBOX_GRID_DEGREES = 0.01
_PREFETCH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="road-network")
_PREFETCH_FUTURES: dict[tuple[float, float, float, float], Future] = {}
_PREFETCH_LOCK = Lock()
_BUNDLED_FUTURE: Future | None = None
_BUNDLED_FUTURE_VERSION: tuple | None = None
_OVERPASS_LOCK = Lock()
OVERPASS_ENDPOINTS = (
    "https://overpass.private.coffee/api",
    "https://overpass-api.de/api",
)


def bbox_contains(outer: tuple[float, float, float, float],
                  inner: tuple[float, float, float, float]) -> bool:
    """Kiểm tra bbox ngoài có phủ hoàn toàn bbox trong hay không."""
    outer_west, outer_south, outer_east, outer_north = outer
    inner_west, inner_south, inner_east, inner_north = inner
    return (outer_west <= inner_west and outer_south <= inner_south
            and outer_east >= inner_east and outer_north >= inner_north)


def bundled_area_contains(locations: list[Location]) -> bool:
    """Kiểm tra mọi điểm có thuộc vùng graph đô thị đóng gói hay không."""
    west, south, east, north = bundled_routing_bbox()
    return bool(locations) and all(
        west <= point.lon <= east and south <= point.lat <= north
        for point in locations
    )


def bundled_routing_bbox() -> tuple[float, float, float, float]:
    """Lấy phạm vi từ metadata của graph; dùng phạm vi mặc định cho gói cũ."""
    if not BUNDLED_GRAPH_METADATA_PATH.is_file():
        return BUNDLED_ROUTING_BBOX
    try:
        metadata = json.loads(BUNDLED_GRAPH_METADATA_PATH.read_text(encoding="utf-8"))
        bbox = tuple(float(value) for value in metadata["bbox"])
        if len(bbox) != 4:
            raise ValueError
        west, south, east, north = bbox
        if west >= east or south >= north:
            raise ValueError
        return bbox
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("Metadata graph đóng gói không hợp lệ; dùng phạm vi mặc định.", exc_info=True)
        return BUNDLED_ROUTING_BBOX


def selected_bbox(locations: list[Location], margin_km: float) -> tuple[float, float, float, float]:
    """OSMnx 2.x: (west, south, east, north), thêm vùng đệm theo km."""
    mean_lat = sum(p.lat for p in locations) / len(locations)
    lat_margin = margin_km / 111.32
    lon_margin = margin_km / (111.32 * cos(radians(mean_lat)))
    return (min(p.lon for p in locations) - lon_margin,
            min(p.lat for p in locations) - lat_margin,
            max(p.lon for p in locations) + lon_margin,
            max(p.lat for p in locations) + lat_margin)


def bbox_dimensions_km(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    """Ước tính chiều rộng/cao bbox theo km tại vĩ độ trung tâm."""
    west, south, east, north = bbox
    mean_lat = (south + north) / 2
    width = abs(east - west) * 111.32 * cos(radians(mean_lat))
    height = abs(north - south) * 111.32
    return width, height


def dynamic_bbox_supported(bbox: tuple[float, float, float, float]) -> bool:
    """Chỉ cho phép Overpass động với vùng đủ nhỏ để phản hồi có kiểm soát."""
    width, height = bbox_dimensions_km(bbox)
    return (max(width, height) <= MAX_DYNAMIC_BBOX_SIDE_KM
            and width * height <= MAX_DYNAMIC_BBOX_AREA_KM2)


def cache_aligned_bbox(bbox: tuple[float, float, float, float],
                       grid: float = BBOX_GRID_DEGREES) -> tuple[float, float, float, float]:
    """Mở bbox ra mép lưới ổn định để tăng khả năng trúng cache giữa các lượt chọn."""
    if grid <= 0:
        raise ValueError("Kích thước lưới bbox phải lớn hơn 0.")
    west, south, east, north = bbox
    return (
        round(floor(west / grid) * grid, 7),
        round(floor(south / grid) * grid, 7),
        round(ceil(east / grid) * grid, 7),
        round(ceil(north / grid) * grid, 7),
    )


def add_travel_times(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Ưu tiên maxspeed của OSM; thiếu thì dùng giả định theo loại đường."""
    graph = ox.routing.add_edge_speeds(graph, hwy_speeds=ROAD_SPEEDS, fallback=DEFAULT_SPEED_KPH)
    # Chặn maxspeed=0 hoặc giá trị lỗi trước khi chia để tính thời gian.
    for _, _, data in graph.edges(data=True):
        speed = float(data.get("speed_kph", DEFAULT_SPEED_KPH))
        if not 0 < speed < float("inf"):
            highway = data.get("highway", "unclassified")
            highway = highway[0] if isinstance(highway, list) else highway
            data["speed_kph"] = ROAD_SPEEDS.get(highway, DEFAULT_SPEED_KPH)
    return ox.routing.add_edge_travel_times(graph)


def graph_cache_path(bbox: tuple[float, float, float, float]):
    """Trả đường dẫn cache ổn định cho bbox đã căn lưới."""
    bbox = cache_aligned_bbox(bbox)
    signature = json.dumps(["drive-v3-grid-bbox", ox.__version__, bbox, ROAD_SPEEDS], sort_keys=True)
    key = hashlib.sha256(signature.encode()).hexdigest()[:20]
    return CACHE_DIR / "graphs" / f"{key}.graphml"


def has_cached_road_network(bbox: tuple[float, float, float, float]) -> bool:
    return graph_cache_path(bbox).is_file()


def bundled_graph_version() -> tuple:
    """Khóa cache thay đổi ngay khi Pickle/metadata trên đĩa được thay thế."""
    return tuple(
        (path.stat().st_mtime_ns, path.stat().st_size) if path.is_file() else None
        for path in (BUNDLED_GRAPH_FAST_PATH, BUNDLED_GRAPH_PATH, BUNDLED_GRAPH_METADATA_PATH)
    )


@st.cache_resource(show_spinner=False)
def _load_bundled_road_network(version: tuple) -> nx.MultiDiGraph:
    """Đọc graph đi kèm và giữ thành phần liên thông mạnh chính để định tuyến ổn định."""
    # ``version`` được dùng làm khóa cache; dữ liệu thực vẫn đọc từ các đường dẫn chuẩn.
    if BUNDLED_GRAPH_FAST_PATH.is_file():
        with BUNDLED_GRAPH_FAST_PATH.open("rb") as stream:
            graph = pickle.load(stream)
        if not isinstance(graph, nx.MultiDiGraph):
            raise UserFacingError("Dữ liệu mạng đường Hà Nội đóng gói không hợp lệ.")
        return graph
    if not BUNDLED_GRAPH_PATH.is_file():
        raise UserFacingError("Chưa có dữ liệu mạng đường Hà Nội đóng gói.")
    graph = ox.io.load_graphml(BUNDLED_GRAPH_PATH)
    component = max(nx.strongly_connected_components(graph), key=len)
    return graph.subgraph(component).copy()


def load_bundled_road_network() -> nx.MultiDiGraph:
    return _load_bundled_road_network(bundled_graph_version())


def prefetch_bundled_road_network() -> Future:
    """Nạp graph đóng gói ở nền ngay khi ứng dụng khởi động."""
    global _BUNDLED_FUTURE, _BUNDLED_FUTURE_VERSION
    version = bundled_graph_version()
    with _PREFETCH_LOCK:
        if (_BUNDLED_FUTURE_VERSION != version
                or _BUNDLED_FUTURE is None
                or (_BUNDLED_FUTURE.done() and _BUNDLED_FUTURE.exception() is not None)):
            _BUNDLED_FUTURE = _PREFETCH_EXECUTOR.submit(load_bundled_road_network)
            _BUNDLED_FUTURE_VERSION = version
        return _BUNDLED_FUTURE


@st.cache_resource(show_spinner=False, max_entries=4)
def load_road_network(bbox: tuple[float, float, float, float]) -> nx.MultiDiGraph:
    """Giữ mọi thành phần liên thông; không biến đường một chiều thành hai chiều.

    Graph cache chỉ đọc sau khi tạo. Cache đĩa cho phép chạy lại vùng đã tải
    mà không tải Overpass lần nữa, kể cả khi mất mạng.
    """
    bbox = cache_aligned_bbox(bbox)
    cache_path = graph_cache_path(bbox)
    if cache_path.exists():
        try:
            return ox.io.load_graphml(cache_path)
        except Exception:
            logger.warning("Graph cache không đọc được: %s", cache_path, exc_info=True)
    # Các điểm đã được kiểm tra bằng polygon Hà Nội trước bước này. BBox tạo câu
    # Overpass đơn giản hơn polygon hành chính nhiều đỉnh. Hai endpoint công khai
    # giúp ứng dụng tiếp tục khi một máy chủ đang quá tải hoặc không truy cập được.
    graph = None
    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            # overpass_url là cấu hình toàn cục của OSMnx nên cần khóa giữa các
            # tác vụ prefetch chạy nền.
            with _OVERPASS_LOCK:
                previous_endpoint = ox.settings.overpass_url
                ox.settings.overpass_url = endpoint
                try:
                    graph = ox.graph.graph_from_bbox(
                        bbox, network_type="drive", simplify=True, retain_all=True,
                        truncate_by_edge=False,
                    )
                finally:
                    ox.settings.overpass_url = previous_endpoint
            break
        except Exception as exc:
            last_error = exc
            logger.warning("Không tải được graph từ %s", endpoint, exc_info=True)
    if graph is None:
        raise UserFacingError("Không tải được mạng đường OpenStreetMap. Dịch vụ có thể quá tải hoặc mất Internet; hãy thử lại sau hoặc giảm vùng đệm.") from last_error
    if graph.number_of_edges() == 0:
        raise UserFacingError("Không có đường ô tô trong khu vực đã chọn.")
    graph = add_travel_times(graph)

    # Cache là tùy chọn: lỗi ghi cache không làm mất kết quả tải thành công.
    temporary = cache_path.with_name(f"{cache_path.stem}-{uuid4().hex}.graphml")
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        ox.io.save_graphml(graph, temporary)
        os.replace(temporary, cache_path)
    except OSError:
        logger.warning("Không ghi được graph cache", exc_info=True)
    finally:
        temporary.unlink(missing_ok=True)
    return graph


def prefetch_road_network(bbox: tuple[float, float, float, float]) -> tuple[
        tuple[float, float, float, float], Future]:
    """Bắt đầu đọc/tải graph ở nền và dùng chung Future cho cùng một vùng."""
    aligned = cache_aligned_bbox(bbox)
    with _PREFETCH_LOCK:
        for cached_bbox, cached_future in _PREFETCH_FUTURES.items():
            if (bbox_contains(cached_bbox, aligned)
                    and not (cached_future.done() and cached_future.exception() is not None)):
                return cached_bbox, cached_future
        future = _PREFETCH_FUTURES.get(aligned)
        if future is None or (future.done() and future.exception() is not None):
            future = _PREFETCH_EXECUTOR.submit(load_road_network, aligned)
            _PREFETCH_FUTURES[aligned] = future
    return aligned, future


def snap_locations(graph: nx.MultiDiGraph, locations: list[Location]) -> tuple[list, list[float]]:
    """Snap tới nút ô tô gần nhất; từ chối điểm quá xa mạng đường hoặc trùng node."""
    nodes, distances = ox.distance.nearest_nodes(
        graph, X=[p.lon for p in locations], Y=[p.lat for p in locations], return_dist=True,
    )
    nodes, distances = list(nodes), [float(d) for d in distances]
    for location, distance in zip(locations, distances):
        if distance > MAX_SNAP_DISTANCE_M:
            raise UserFacingError(f"{location.name} cách nút đường ô tô gần nhất {distance:.0f} m. Hãy chọn điểm gần đường hơn.")
    if len(set(nodes)) != len(nodes):
        raise UserFacingError("Hai địa điểm được gắn vào cùng một nút đường ô tô. Hãy xóa một điểm hoặc chọn vị trí khác.")
    return nodes, distances
