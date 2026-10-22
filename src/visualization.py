from html import escape
from math import cos, log2, radians

import folium

from src.constants import HANOI_CENTER
from src.route_optimizer import RouteResult
from src.utils import Location


def create_base_map() -> folium.Map:
    """Tạo phần nền bất biến để Streamlit không remount Leaflet khi rerun."""
    route_map = folium.Map(
        location=HANOI_CENTER,
        zoom_start=12,
        tiles=None,
        control_scale=True,
        zoom_control=True,
    )
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        name="Đường phố",
        overlay=False,
        control=True,
        show=True,
        max_zoom=19,
    ).add_to(route_map)
    folium.TileLayer(
        tiles=("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        attr=("Tiles &copy; Esri — Source: Esri, Maxar, Earthstar Geographics, "
              "and the GIS User Community"),
        name="Vệ tinh",
        overlay=False,
        control=True,
        show=False,
        max_zoom=19,
    ).add_to(route_map)
    folium.LayerControl(position="topright", collapsed=True).add_to(route_map)
    return route_map


def create_map_features(start: Location | None, destinations: list[Location],
                        result: RouteResult | None = None) -> folium.FeatureGroup:
    """Tạo marker và tuyến dưới dạng layer có thể cập nhật động."""
    features = folium.FeatureGroup(name="Lộ trình", overlay=True, control=False)
    points = ([start] if start else []) + destinations
    numbers = {}
    if result:
        for number, index in enumerate(result.order, start=1):
            numbers.setdefault(index, number)
    for index, location in enumerate(points):
        is_start = start is not None and index == 0
        label = "Xuất phát" if is_start else "Điểm cần ghé"
        if result and result.route_mode != "closed" and index == result.order[-1]:
            label = "Kết thúc"
        color = "#0d9488" if is_start else ("#d97706" if label == "Kết thúc" else "#2563eb")
        number = numbers.get(index, "S" if is_start else index + (0 if start else 1))
        icon = folium.DivIcon(html=f'<div style="background:{color};color:white;border:3px solid white;border-radius:50%;width:32px;height:32px;text-align:center;line-height:27px;font-weight:bold;box-shadow:0 2px 6px #555">{number}</div>', icon_size=(32, 32), icon_anchor=(16, 16))
        folium.Marker((location.lat, location.lon), icon=icon,
                      tooltip=f"{number}. {escape(location.name)}",
                      popup=folium.Popup(f"<b>{escape(location.name)}</b><br>{label}", max_width=280)).add_to(features)
    if result:
        # MultiPolyline giảm số layer JS và giữ nguyên các đoạn geometry đường.
        folium.PolyLine(result.road_coordinates, color="#2563eb", weight=5, opacity=0.85,
                        tooltip="Lộ trình ô tô tối ưu").add_to(features)
        for index, coordinate in enumerate(result.snapped_coordinates):
            folium.CircleMarker(coordinate, radius=3, color="#475569", fill=True,
                                tooltip=f"Nút đường: {escape(result.locations[index].name)}").add_to(features)
    return features


def calculate_map_view(start: Location | None, destinations: list[Location],
                       result: RouteResult | None = None) -> tuple[tuple[float, float], int]:
    """Tính center/zoom để cập nhật viewport mà không reload bản đồ."""
    coordinates = [(p.lat, p.lon) for p in ([start] if start else []) + destinations]
    if result:
        coordinates.extend(point for segment in result.road_coordinates for point in segment)
    if not coordinates:
        return HANOI_CENTER, 12
    if len(coordinates) == 1:
        return coordinates[0], 15

    lats, lons = zip(*coordinates)
    center = ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)
    # Quy đổi độ kinh theo vĩ độ để khung nhìn hợp lý quanh Hà Nội.
    span = max(max(lats) - min(lats), (max(lons) - min(lons)) * cos(radians(center[0])))
    zoom = max(9, min(17, round(8.8 - log2(max(span, 0.001)))))
    return center, zoom


def create_map(start: Location | None, destinations: list[Location],
               result: RouteResult | None = None) -> folium.Map:
    """Tạo bản đồ hoàn chỉnh cho xuất HTML và kiểm thử độc lập."""
    route_map = create_base_map()
    create_map_features(start, destinations, result).add_to(route_map)
    points = [(p.lat, p.lon) for p in ([start] if start else []) + destinations]
    if result:
        points.extend(point for segment in result.road_coordinates for point in segment)
    if len(points) > 1:
        route_map.fit_bounds(points, padding=(35, 35), max_zoom=15)
    elif points:
        route_map.location = points[0]
    return route_map
