from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CACHE_DIR = PROJECT_ROOT / ".cache"
BUNDLED_GRAPH_PATH = PROJECT_ROOT / "data" / "hanoi_urban_drive.graphml"
BUNDLED_GRAPH_FAST_PATH = PROJECT_ROOT / "data" / "hanoi_urban_drive.pkl"
BUNDLED_GRAPH_METADATA_PATH = PROJECT_ROOT / "data" / "hanoi_urban_drive.meta.json"
HANOI_PBF_PATH = CACHE_DIR / "osm" / "vietnam-latest.osm.pbf"
# Vùng định tuyến ngoại tuyến đã xác minh trên graph đóng gói. Đây là khu vực
# đô thị phục vụ ứng dụng, không phải toàn bộ địa giới hành chính Hà Nội.
BUNDLED_ROUTING_BBOX = (105.70, 20.94, 105.8945, 21.08)
MAX_DESTINATIONS = 10
DUPLICATE_RADIUS_M = 50
MAX_SNAP_DISTANCE_M = 1500
# Giới hạn truy vấn Overpass động. BBox lớn tải cả vùng trống giữa các điểm và có
# thể mất nhiều phút; tuyến rộng hơn cần graph ngoại tuyến mở rộng.
MAX_DYNAMIC_BBOX_SIDE_KM = 35
MAX_DYNAMIC_BBOX_AREA_KM2 = 700
ROAD_FUTURE_WAIT_SECONDS = 30
HANOI_CENTER = (21.0285, 105.8542)
# Chỉ dùng để loại nhanh; polygon hành chính OSM mới quyết định trong/ngoài.
HANOI_ENVELOPE = (105.20, 20.50, 106.10, 21.45)
HANOI_QUERY = {"city": "Hà Nội", "country": "Việt Nam"}
# 2 km đủ cho phần lớn tuyến nội đô và giảm đáng kể dữ liệu tải lần đầu.
# Người dùng vẫn có thể tăng trong phần cài đặt nâng cao khi cần xét đường vòng.
DEFAULT_MARGIN_KM = 2
DEFAULT_SPEED_KPH = 30
# Giả định mô hình, không phải bảng giới hạn tốc độ pháp lý.
ROAD_SPEEDS = {
    "motorway": 80, "motorway_link": 40,
    "trunk": 60, "trunk_link": 35,
    "primary": 50, "primary_link": 30,
    "secondary": 40, "secondary_link": 30,
    "tertiary": 35, "tertiary_link": 25,
    "residential": 25, "living_street": 15,
    "service": 15, "unclassified": 30,
}
