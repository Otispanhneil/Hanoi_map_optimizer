"""Tìm địa chỉ và kiểm tra ranh giới Hà Nội qua OSM/Nominatim."""
import os
from threading import Lock
from time import monotonic, sleep

import osmnx as ox
import streamlit as st
from shapely.geometry import Point

from src.constants import CACHE_DIR, HANOI_QUERY
from src.utils import Location, UserFacingError, validate_coordinate

# Các thiết lập này dùng chung cho một tiến trình Streamlit.
ox.settings.use_cache = True
ox.settings.cache_folder = str(CACHE_DIR / "http")
ox.settings.requests_timeout = 60
ox.settings.http_user_agent = os.getenv("OSM_USER_AGENT", "HanoiRouteOptimizer/1.0 (educational local application)")
ox.settings.nominatim_url = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/")
ox.settings.overpass_url = os.getenv("OVERPASS_URL", "https://overpass-api.de/api")
_geocode_lock = Lock()
_last_request = 0.0


def _nominatim_call(function, *args, **kwargs):
    """Tuần tự hóa yêu cầu và giới hạn tối đa 1 request/giây mỗi tiến trình."""
    global _last_request
    with _geocode_lock:
        sleep(max(0, 1.1 - (monotonic() - _last_request)))
        try:
            return function(*args, **kwargs)
        finally:
            _last_request = monotonic()


@st.cache_data(show_spinner=False, ttl=7 * 86400)
def get_hanoi_boundary():
    """Polygon hành chính thực tế; không coi bounding box là ranh giới Hà Nội."""
    try:
        frame = _nominatim_call(ox.geocoder.geocode_to_gdf, HANOI_QUERY)
        polygon = frame.geometry.iloc[0]
        # Tránh dùng nhầm một địa danh nhỏ trùng tên.
        if polygon.geom_type not in {"Polygon", "MultiPolygon"} or polygon.area < 0.1:
            raise ValueError("Unexpected Hanoi boundary")
        return polygon
    except Exception as exc:
        raise UserFacingError("Chưa tải được ranh giới Hà Nội. Hãy kiểm tra Internet và thử lại.") from exc


def ensure_in_hanoi(location: Location) -> None:
    validate_coordinate(location)
    if not get_hanoi_boundary().covers(Point(location.lon, location.lat)):
        raise UserFacingError(f"{location.name}: địa điểm nằm ngoài ranh giới Hà Nội.")


@st.cache_data(show_spinner=False, ttl=86400, max_entries=256)
def search_location(query: str) -> Location:
    """Tìm kiếm khi người dùng bấm nút, không gửi request theo mỗi phím gõ."""
    query = query.strip()
    if len(query) < 3:
        raise UserFacingError("Vui lòng nhập tên hoặc địa chỉ có ít nhất 3 ký tự.")
    try:
        lat, lon = _nominatim_call(ox.geocoder.geocode, f"{query}, Hà Nội, Việt Nam")
    except Exception as exc:
        raise UserFacingError("Không tìm được địa chỉ hoặc dịch vụ tìm kiếm đang gián đoạn. Hãy nhập địa chỉ cụ thể hơn và thử lại.") from exc
    location = Location(query, float(lat), float(lon))
    ensure_in_hanoi(location)
    return location
