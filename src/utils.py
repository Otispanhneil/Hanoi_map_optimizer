from dataclasses import dataclass
from math import asin, cos, isfinite, radians, sin, sqrt
from collections.abc import Sequence

from src.constants import DUPLICATE_RADIUS_M, HANOI_ENVELOPE, MAX_DESTINATIONS


class UserFacingError(ValueError):
    """Lỗi dự kiến, có thông báo có thể hiển thị trực tiếp trên giao diện."""


@dataclass(frozen=True)
class Location:
    name: str
    lat: float
    lon: float


def distance_m(a: Location, b: Location) -> float:
    """Khoảng cách Haversine, dùng kiểm tra trùng và khoảng cách snap."""
    dlat, dlon = radians(b.lat - a.lat), radians(b.lon - a.lon)
    value = sin(dlat / 2) ** 2 + cos(radians(a.lat)) * cos(radians(b.lat)) * sin(dlon / 2) ** 2
    return 6371009 * 2 * asin(sqrt(min(1, max(0, value))))


def validate_coordinate(location: Location) -> None:
    west, south, east, north = HANOI_ENVELOPE
    if not (isfinite(location.lat) and isfinite(location.lon)):
        raise UserFacingError("Tọa độ địa điểm không hợp lệ.")
    if not (south <= location.lat <= north and west <= location.lon <= east):
        raise UserFacingError(f"{location.name}: địa điểm nằm ngoài Hà Nội.")


def ensure_distinct(location: Location, others: Sequence[Location]) -> None:
    for other in others:
        if distance_m(location, other) < DUPLICATE_RADIUS_M:
            raise UserFacingError(f"Điểm này trùng hoặc cách {other.name} dưới {DUPLICATE_RADIUS_M} m.")


def validate_selection(start: Location | None, destinations: Sequence[Location]) -> None:
    """Kiểm tra đầu vào cục bộ trước khi thực hiện bất kỳ yêu cầu mạng nào."""
    if start is None:
        raise UserFacingError("Vui lòng chọn điểm xuất phát.")
    if not destinations:
        raise UserFacingError("Vui lòng thêm ít nhất một điểm cần ghé.")
    if len(destinations) > MAX_DESTINATIONS:
        raise UserFacingError(f"Chỉ được chọn tối đa {MAX_DESTINATIONS} điểm cần ghé.")
    seen = []
    for location in [start, *destinations]:
        validate_coordinate(location)
        ensure_distinct(location, seen)
        seen.append(location)
