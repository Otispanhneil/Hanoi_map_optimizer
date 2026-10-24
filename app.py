"""Giao diện Streamlit tiếng Việt cho Hanoi Route Optimizer."""
import logging
import os
from concurrent.futures import TimeoutError as FutureTimeoutError
from html import escape
from time import perf_counter

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

from data.popular_locations import POPULAR_LOCATIONS
from src.constants import DEFAULT_MARGIN_KM, MAX_DESTINATIONS, ROAD_FUTURE_WAIT_SECONDS
from src.geocoding import ensure_in_hanoi, search_location
from src.map_service import (
    bbox_contains,
    bbox_dimensions_km,
    bundled_area_contains,
    bundled_graph_version,
    cache_aligned_bbox,
    load_bundled_road_network,
    load_road_network,
    prefetch_road_network,
    dynamic_bbox_supported,
    selected_bbox,
    snap_locations,
)
from src.route_optimizer import optimize_route
from src.utils import Location, UserFacingError, ensure_distinct, validate_selection
from src.visualization import calculate_map_view, create_base_map, create_map, create_map_features

logger = logging.getLogger(__name__)


def apply_page_style() -> None:
    """CSS gọn như một ứng dụng bản đồ, ưu tiên diện tích cho bản đồ."""
    st.markdown(
        """
        <style>
        html, body, .stApp { margin: 0; background: #f7f8fa; }
        [data-testid="stHeader"] { display: none; }
        [data-testid="stToolbar"], footer { visibility: hidden; height: 0; }
        .block-container {
            max-width: none;
            padding: 0 !important;
            margin: 0 !important;
        }
        section[data-testid="stSidebar"] {
            min-width: 360px !important;
            width: 360px !important;
            max-width: 360px !important;
            transform: none !important;
            margin-left: 0 !important;
        }
        [data-testid="stSidebarCollapseButton"] {
            display: none !important;
        }
        [data-testid="stSidebar"] > div:first-child {
            background: #ffffff;
            border-right: 1px solid #e5e7eb;
            padding: 1.1rem .95rem 1.4rem;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .72rem; }
        [data-testid="stSidebar"] .st-key-start_card,
        [data-testid="stSidebar"] .st-key-destinations_card,
        [data-testid="stSidebar"] .st-key-routing_card {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            margin: .22rem 0 .42rem;
            padding: 1.05rem .95rem;
            box-shadow: 0 1px 2px rgba(15, 23, 42, .035);
        }
        [data-testid="stSidebar"] .st-key-start_card { margin-top: .35rem; }
        [data-testid="stSidebar"] .st-key-routing_card { margin-bottom: .5rem; }
        [data-testid="stSidebar"] .st-key-start_card [data-testid="stVerticalBlock"],
        [data-testid="stSidebar"] .st-key-destinations_card [data-testid="stVerticalBlock"],
        [data-testid="stSidebar"] .st-key-routing_card [data-testid="stVerticalBlock"] {
            gap: .74rem;
        }
        [data-testid="stSidebar"] .stButton button {
            border-radius: 10px;
            min-height: 2.35rem;
            font-weight: 600;
        }
        [data-testid="stSidebar"] div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] .stTextInput input { border-radius: 10px; }
        [data-testid="stSidebar"] [data-testid="stExpander"] {
            border-color: #e2e8f0;
            border-radius: 10px;
            box-shadow: none;
        }
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] .stCaption p { font-size: .76rem; }
        [data-testid="stSidebar"] .stRadio [role="radiogroup"] {
            gap: .45rem;
        }
        [data-testid="stSidebar"] .stRadio label {
            flex: 1;
            min-height: 2.15rem;
            padding: .35rem .45rem;
            border: 1px solid #e2e8f0;
            border-radius: 9px;
            background: #f8fafc;
        }
        [data-testid="stSidebar"] .st-key-optimize_action {
            position: sticky;
            z-index: 4;
            bottom: -.2rem;
            margin: .35rem -.15rem 0;
            padding: .85rem .15rem .1rem;
            background: linear-gradient(to bottom, rgba(255,255,255,0), #ffffff 28%);
        }
        [data-testid="stSidebar"] .st-key-optimize_action button {
            min-height: 2.75rem;
            border: 0;
            border-radius: 11px;
            box-shadow: 0 7px 16px rgba(13, 148, 136, .20);
            letter-spacing: .015em;
        }
        [data-testid="stMetric"] {
            background: white;
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: .75rem 1rem;
            box-shadow: 0 1px 2px rgba(0,0,0,.04);
        }
        [data-testid="stMetricLabel"] { color: #6b7280; }
        [data-testid="stMetricValue"] { font-size: 1.35rem; }
        .map-title {
            display:flex; align-items:center; gap:.65rem;
            margin:0 0 .4rem; padding:0 0 1rem;
            border-bottom:1px solid #e5e7eb;
        }
        .map-logo {
            width:36px; height:36px; border-radius:10px; background:#2563eb;
            color:white; display:flex; align-items:center; justify-content:center;
            font-size:20px; box-shadow:0 2px 5px rgba(37,99,235,.25);
        }
        .map-heading { font-size:1.15rem; font-weight:700; color:#111827; line-height:1.2; }
        .sidebar-section-head {
            display:flex; align-items:center; gap:.58rem; min-height:1.8rem;
            margin-bottom:.24rem;
        }
        .sidebar-step {
            width:24px; height:24px; flex:0 0 24px; border-radius:8px;
            display:flex; align-items:center; justify-content:center;
            background:#e7f6f3; color:#0f766e; font-size:.72rem; font-weight:800;
        }
        .sidebar-section-title { color:#172b4d; font-size:.88rem; font-weight:750; }
        .sidebar-count {
            margin-left:auto; padding:.18rem .48rem; border-radius:999px;
            background:#f1f5f9; color:#64748b; font-size:.68rem; font-weight:700;
        }
        .selected-location {
            display:flex; align-items:center; gap:.55rem; min-height:2.35rem;
            padding:.48rem .6rem; border:1px solid #cfe6e2; border-radius:10px;
            background:#f0fdfa;
        }
        .location-marker {
            display:flex; align-items:center; justify-content:center;
            width:24px; height:24px; flex:0 0 24px; border-radius:50%;
            background:#0d9488; color:#fff; font-size:.68rem; font-weight:800;
        }
        .location-marker.destination { background:#2563eb; }
        .location-name {
            min-width:0; overflow:hidden; color:#26364f; font-size:.78rem;
            font-weight:600; line-height:1.25; text-overflow:ellipsis; white-space:nowrap;
        }
        .empty-location {
            padding:.1rem .05rem; color:#8491a5; font-size:.72rem; line-height:1.4;
        }
        .ready-line {
            display:flex; align-items:center; justify-content:center; gap:.38rem;
            margin-bottom:.2rem; color:#64748b; font-size:.7rem;
        }
        .ready-dot { width:6px; height:6px; border-radius:50%; background:#0d9488; }
        .route-label { font-size:1rem; font-weight:700; margin:.9rem 0 .45rem; color:#111827; }
        div[data-testid="stAlert"] { border-radius: 10px; padding: .65rem .85rem; }
        .st-key-map_shell {
            margin: 0 !important;
            padding: 0 !important;
            line-height: 0;
        }
        .st-key-map_shell [data-testid="stCustomComponentV1"] {
            margin: 0 !important;
            padding: 0 !important;
        }
        .st-key-map_shell iframe {
            display: block;
            width: 100% !important;
            border: 0 !important;
            border-radius: 0 !important;
            box-shadow: none !important;
        }
        .st-key-results_panel {
            padding: .35rem 1.5rem 2rem;
            background: #f7f8fa;
        }
        @media (max-width: 768px) {
            section[data-testid="stSidebar"] {
                min-width: min(360px, 90vw) !important;
                width: 90vw !important;
                max-width: 90vw !important;
            }
            .st-key-results_panel { padding-left: .75rem; padding-right: .75rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def initialize_state() -> None:
    defaults = {"start": None, "destinations": [], "result": None,
                "result_signature": None, "search_result": None,
                "custom_count": 0, "last_click": None, "notice": None,
                "map_error": None, "road_graph": None, "road_bbox": None,
                "road_future": None, "road_prefetch_bbox": None,
                "bundled_graph": None, "bundled_version": None, "enable_map_click": True}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def selection_changed() -> None:
    st.session_state.result = None


def normalize_custom_names() -> None:
    """Đánh số liên tục các điểm click còn tồn tại và đồng bộ bộ đếm."""
    prefix = "Điểm tùy chọn "
    number = 0

    def normalized(location: Location | None) -> Location | None:
        nonlocal number
        if location is None or not location.name.startswith(prefix):
            return location
        number += 1
        return Location(f"{prefix}{number}", location.lat, location.lon)

    st.session_state.start = normalized(st.session_state.start)
    st.session_state.destinations = [normalized(point) for point in st.session_state.destinations]
    st.session_state.custom_count = number


def clear_start() -> None:
    st.session_state.start = None
    st.session_state.last_click = None
    normalize_custom_names()
    selection_changed()


def set_start(location: Location) -> None:
    ensure_distinct(location, st.session_state.destinations)
    st.session_state.start = location
    normalize_custom_names()
    selection_changed()


def add_destination(location: Location, verify_boundary: bool = False) -> None:
    if len(st.session_state.destinations) >= MAX_DESTINATIONS:
        raise UserFacingError("Bạn đã chọn đủ 10 điểm cần ghé. Hãy xóa một điểm trước khi thêm.")
    others = list(st.session_state.destinations)
    if st.session_state.start:
        others.append(st.session_state.start)
    ensure_distinct(location, others)
    if verify_boundary:
        ensure_in_hanoi(location)
    st.session_state.destinations = [*st.session_state.destinations, location]
    selection_changed()


def report_error(error: Exception) -> None:
    if isinstance(error, UserFacingError):
        st.error(str(error))
    else:
        logger.exception("Lỗi xử lý ứng dụng", exc_info=error)
        st.error("Chưa thể xử lý thao tác này. Hãy kiểm tra kết nối và thử lại. Chi tiết lỗi được ghi trong terminal.")


def handle_map_change() -> None:
    """Xử lý click trước lượt rerun, tránh gọi st.rerun lần thứ hai."""
    event = st.session_state.get("route_map") or {}
    clicked = event.get("last_clicked")
    if not clicked or not st.session_state.get("enable_map_click", True):
        return
    click_key = (round(float(clicked["lat"]), 7), round(float(clicked["lng"]), 7))
    if click_key == st.session_state.last_click:
        return
    st.session_state.last_click = click_key
    try:
        number = st.session_state.custom_count + 1
        point = Location(f"Điểm tùy chọn {number}", clicked["lat"], clicked["lng"])
        if not bundled_area_contains([point]):
            ensure_in_hanoi(point)
        if st.session_state.start is None:
            set_start(point)
            notice = f"Đã chọn {point.name} làm điểm xuất phát."
        else:
            add_destination(point)
            notice = f"Đã thêm {point.name} vào các điểm cần ghé."
        st.session_state.custom_count = number
        st.session_state.notice = notice
        st.session_state.map_error = None
    except UserFacingError as exc:
        st.session_state.map_error = str(exc)
    except Exception as exc:
        logger.exception("Lỗi xử lý click bản đồ", exc_info=exc)
        st.session_state.map_error = "Chưa thể thêm điểm này. Hãy kiểm tra kết nối và thử lại."


def show_result(result) -> None:
    st.markdown('<div class="route-label">Tóm tắt lộ trình</div>', unsafe_allow_html=True)
    columns = st.columns(4)
    columns[0].metric("Quãng đường", f"{result.distance_m / 1000:.2f} km")
    columns[1].metric("Thời gian", f"{result.travel_time_s / 60:.1f} phút")
    columns[2].metric("Điểm ghé", len(result.locations) - 1)
    columns[3].metric("Xử lý", f"{(result.dijkstra_seconds + result.tsp_seconds) * 1000:.1f} ms")
    rows = []
    for position, index in enumerate(result.order, start=1):
        if position == 1:
            role = "Xuất phát"
        elif result.route_mode == "closed" and position == len(result.order):
            role = "Trở về"
        elif position == len(result.order):
            role = "Kết thúc"
        else:
            role = "Ghé thăm"
        rows.append({"Thứ tự": position, "Địa điểm": result.locations[index].name, "Vai trò": role})
    with st.expander("Thứ tự các điểm", expanded=True):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    with st.expander("Chi tiết thuật toán"):
        legs = [{"Từ": leg["from"], "Đến": leg["to"],
                 "Quãng đường (km)": round(leg["distance_m"] / 1000, 3),
                 "Ước tính (phút)": round(leg["travel_time_s"] / 60, 2)} for leg in result.legs]
        st.markdown("**Cách hình thành lộ trình tối ưu**")
        st.caption(
            "Held–Karp đánh giá các trạng thái gồm tập điểm đã ghé và điểm kết thúc. "
            "Bảng dưới là thứ tự được truy vết từ trạng thái có tổng chi phí nhỏ nhất, "
            "không phải lựa chọn tham lam ở từng bước."
        )
        cumulative_cost = 0.0
        trace_rows = []
        for step, (leg, source, target) in enumerate(
            zip(result.legs, result.order, result.order[1:]), start=1
        ):
            leg_cost = leg["distance_m"] if result.weight == "length" else leg["travel_time_s"]
            cumulative_cost += leg_cost
            trace_rows.append({
                "Bước": step,
                "Từ": result.locations[source].name,
                "Điểm tiếp theo": result.locations[target].name,
                "Chi phí chặng": round(leg_cost, 1),
                "Chi phí lũy kế": round(cumulative_cost, 1),
            })
        st.dataframe(pd.DataFrame(trace_rows), hide_index=True, width="stretch")
        st.caption(
            "Đơn vị chi phí: mét" if result.weight == "length"
            else "Đơn vị chi phí: giây di chuyển ước tính"
        )

        st.markdown("**Chi tiết từng chặng**")
        st.dataframe(pd.DataFrame(legs), hide_index=True, width="stretch")
        st.caption(f"Dijkstra: {result.dijkstra_seconds * 1000:.2f} ms · Held–Karp: {result.tsp_seconds * 1000:.2f} ms · Chuẩn bị dữ liệu: {st.session_state.get('preparation_seconds', 0):.2f} giây")
        cost_unit = "m" if result.weight == "length" else "giây"
        comparison_rows = [{
            "Thuật toán": item["algorithm"],
            f"Chi phí ({cost_unit})": round(item["cost"], 2),
            "Thời gian (ms)": round(item["runtime_ms"], 3),
            "Lệch tối ưu (%)": round(item["gap_percent"], 2),
        } for item in result.comparisons]
        st.markdown("**So sánh thuật toán**")
        st.dataframe(pd.DataFrame(comparison_rows), hide_index=True, width="stretch")
        names = [p.name for p in result.locations]
        unit = "mét" if result.weight == "length" else "giây"
        st.caption(f"Ma trận chi phí ({unit})")
        st.dataframe(pd.DataFrame(result.cost_matrix, index=names, columns=names).round(1), width="stretch")
        st.dataframe(pd.DataFrame({"Địa điểm": names, "Khoảng cách đến nút đường (m)": [round(d) for d in result.snap_distances]}), hide_index=True, width="stretch")
    with st.expander("Tải kết quả"):
        route_csv = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
        export_map = create_map(result.locations[0], result.locations[1:], result)
        map_html = export_map.get_root().render().encode("utf-8")
        download_columns = st.columns(2)
        download_columns[0].download_button(
            "Tải thứ tự CSV", route_csv, "lo-trinh-ha-noi.csv", "text/csv",
            width="stretch",
        )
        download_columns[1].download_button(
            "Tải bản đồ HTML", map_html, "ban-do-lo-trinh.html", "text/html",
            width="stretch",
        )


def switch_mode(mode: str) -> None:
    st.session_state.workspace_mode = mode
    st.query_params["mode"] = mode


def main(default_mode: str = "route") -> None:
    st.set_page_config(
        page_title="Tối ưu lộ trình Hà Nội", page_icon="🗺️",
        layout="wide", initial_sidebar_state="expanded",
    )
    # Keep route widgets alive while the other mode is rendered.
    for key in ("routing_criterion", "routing_end_mode", "routing_end_choice", "enable_map_click"):
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]
    mode = st.query_params.get("mode", st.session_state.get("workspace_mode", default_mode))
    if mode not in {"route", "chase"}:
        mode = "route"
    st.session_state.workspace_mode = mode
    with st.sidebar.container(key="app_navigation"):
        st.caption("HANOI MAP LAB · THUẬT TOÁN ỨNG DỤNG")
        route_tab, chase_tab = st.columns(2)
        route_tab.button("Lộ trình", key="mode_route", width="stretch",
                         type="primary" if mode == "route" else "secondary",
                         on_click=switch_mode, args=("route",))
        chase_tab.button("Trốn tìm", key="mode_chase", width="stretch",
                         type="primary" if mode == "chase" else "secondary",
                         on_click=switch_mode, args=("chase",))
    if mode == "chase":
        from src.chase_ui import render_chase
        render_chase()
        return
    initialize_state()
    apply_page_style()
    bundled_enabled = os.getenv("HANOI_PRELOAD_MAP", "1") != "0"

    # Nạp graph đúng một lần trước khi cho phép tương tác. Unpickle graph lớn trong
    # thread nền vẫn tranh CPU/GIL với các lượt click đầu tiên và làm chúng có vẻ
    # như đang tải lại bản đồ. Sau bước này mọi rerun chỉ lấy lại resource từ RAM.
    if bundled_enabled:
        current_bundled_version = bundled_graph_version()
        if (st.session_state.bundled_graph is None
                or st.session_state.bundled_version != current_bundled_version):
            try:
                with st.spinner("Đang chuẩn bị mạng đường Hà Nội…"):
                    st.session_state.bundled_graph = load_bundled_road_network()
                    st.session_state.bundled_version = current_bundled_version
            except UserFacingError as exc:
                bundled_enabled = False
                st.sidebar.warning(f"{exc} Giao diện vẫn dùng được; tính lộ trình sẽ cần cache hoặc tải OSM qua Internet.")

    with st.sidebar:
        st.markdown(
            '<div class="map-title"><div class="map-logo">⌖</div>'
            '<div><div class="map-heading">Tối ưu lộ trình Hà Nội</div></div></div>',
            unsafe_allow_html=True,
        )
        with st.container(key="start_card"):
            st.markdown(
                '<div class="sidebar-section-head"><span class="sidebar-step">1</span>'
                '<span class="sidebar-section-title">Điểm xuất phát</span></div>',
                unsafe_allow_html=True,
            )
            choice = st.selectbox(
                "Địa điểm xuất phát phổ biến", range(len(POPULAR_LOCATIONS)),
                format_func=lambda i: POPULAR_LOCATIONS[i].name, index=None,
                placeholder="Chọn địa điểm", label_visibility="collapsed",
            )
            if st.button("Đặt điểm xuất phát", width="stretch"):
                try:
                    if choice is None:
                        raise UserFacingError("Vui lòng chọn một địa điểm xuất phát.")
                    set_start(POPULAR_LOCATIONS[choice])
                except Exception as exc:
                    report_error(exc)
            if st.session_state.start:
                start_label, start_action = st.columns([6, 1], vertical_alignment="center")
                start_label.markdown(
                    '<div class="selected-location"><span class="location-marker">S</span>'
                    f'<span class="location-name">{escape(st.session_state.start.name)}</span></div>',
                    unsafe_allow_html=True,
                )
                if start_action.button("×", key="remove_start", help="Xóa điểm xuất phát"):
                    clear_start()
                    st.session_state.notice = "Đã xóa điểm xuất phát."
                    st.rerun()
            else:
                st.markdown(
                    '<div class="empty-location">Chọn trong danh sách hoặc click trực tiếp trên bản đồ.</div>',
                    unsafe_allow_html=True,
                )

        with st.container(key="destinations_card"):
            st.markdown(
                '<div class="sidebar-section-head"><span class="sidebar-step">2</span>'
                '<span class="sidebar-section-title">Điểm cần ghé</span>'
                f'<span class="sidebar-count">{len(st.session_state.destinations)}/{MAX_DESTINATIONS}</span></div>',
                unsafe_allow_html=True,
            )
            destination_choice = st.selectbox(
                "Địa điểm phổ biến", range(len(POPULAR_LOCATIONS)),
                format_func=lambda i: POPULAR_LOCATIONS[i].name, index=None,
                placeholder="Thêm địa điểm", label_visibility="collapsed",
            )
            if st.button("Thêm điểm đã chọn", width="stretch"):
                try:
                    if destination_choice is None:
                        raise UserFacingError("Vui lòng chọn một điểm cần ghé.")
                    add_destination(POPULAR_LOCATIONS[destination_choice])
                except Exception as exc:
                    report_error(exc)

            with st.expander("Tìm theo tên hoặc địa chỉ"):
                with st.form("search_form"):
                    query = st.text_input(
                        "Tên địa điểm hoặc địa chỉ tại Hà Nội",
                        placeholder="Ví dụ: 1 Đại Cồ Việt",
                        label_visibility="collapsed",
                    )
                    search_clicked = st.form_submit_button("Tìm địa điểm", width="stretch")
                if search_clicked:
                    st.session_state.search_result = None
                    try:
                        with st.spinner("Đang tìm địa chỉ…"):
                            st.session_state.search_result = search_location(query)
                    except Exception as exc:
                        report_error(exc)
                found = st.session_state.search_result
                if found:
                    st.write(f"{found.name} ({found.lat:.5f}, {found.lon:.5f})")
                    if st.button("Dùng làm điểm xuất phát", width="stretch"):
                        try:
                            set_start(found)
                            st.rerun()
                        except Exception as exc:
                            report_error(exc)
                    if st.button("Thêm vào điểm cần ghé", width="stretch"):
                        try:
                            add_destination(found)
                        except Exception as exc:
                            report_error(exc)

            if not st.session_state.destinations:
                st.markdown(
                    '<div class="empty-location">Chưa có điểm cần ghé.</div>',
                    unsafe_allow_html=True,
                )
            for index, location in enumerate(st.session_state.destinations):
                label, action = st.columns([6, 1], vertical_alignment="center")
                label.markdown(
                    '<div class="selected-location"><span class="location-marker destination">'
                    f'{index + 1}</span><span class="location-name">{escape(location.name)}</span></div>',
                    unsafe_allow_html=True,
                )
                if action.button("×", key=f"remove_{index}", help=f"Xóa {location.name}"):
                    st.session_state.destinations = [
                        point for item_index, point in enumerate(st.session_state.destinations)
                        if item_index != index
                    ]
                    st.session_state.last_click = None
                    normalize_custom_names()
                    selection_changed()
                    st.rerun()
            if st.session_state.destinations and st.button(
                "Xóa tất cả điểm cần ghé", width="stretch",
            ):
                st.session_state.destinations = []
                st.session_state.last_click = None
                normalize_custom_names()
                selection_changed()
                st.rerun()

        with st.container(key="routing_card"):
            st.markdown(
                '<div class="sidebar-section-head"><span class="sidebar-step">3</span>'
                '<span class="sidebar-section-title">Thiết lập lộ trình</span></div>',
                unsafe_allow_html=True,
            )
            criterion = st.radio(
                "Tối thiểu hóa", ["Quãng đường", "Thời gian di chuyển"],
                horizontal=True, label_visibility="collapsed",
                key="routing_criterion",
            )
            weight = "length" if criterion == "Quãng đường" else "travel_time"
            with st.expander("Điểm kết thúc"):
                route_mode_label = st.selectbox(
                    "Điểm kết thúc",
                    ["Tự động", "Do tôi chọn", "Quay về điểm xuất phát"],
                    label_visibility="collapsed",
                    key="routing_end_mode",
                )
                route_mode = {
                    "Tự động": "open",
                    "Do tôi chọn": "fixed_end",
                    "Quay về điểm xuất phát": "closed",
                }[route_mode_label]
                end_destination = None
                if route_mode == "fixed_end":
                    if st.session_state.get("routing_end_choice") not in range(len(st.session_state.destinations)):
                        st.session_state.routing_end_choice = None
                    end_destination = st.selectbox(
                        "Chọn điểm kết thúc",
                        range(len(st.session_state.destinations)),
                        format_func=[point.name for point in st.session_state.destinations].__getitem__,
                        index=None,
                        placeholder="Chọn trong các điểm cần ghé",
                        disabled=not st.session_state.destinations,
                        key="routing_end_choice",
                    )
            st.toggle("Chọn điểm bằng click bản đồ", key="enable_map_click")

        margin = DEFAULT_MARGIN_KM
        with st.container(key="optimize_action"):
            selected_count = int(st.session_state.start is not None) + len(st.session_state.destinations)
            st.markdown(
                '<div class="ready-line"><span class="ready-dot"></span>'
                f'<span>{selected_count} điểm trong hành trình</span></div>',
                unsafe_allow_html=True,
            )
            optimize_clicked = st.button("TỐI ƯU LỘ TRÌNH", type="primary", width="stretch")

    end_index = end_destination + 1 if end_destination is not None else None
    signature = (st.session_state.start, tuple(st.session_state.destinations), weight,
                 margin, route_mode, end_index)
    if st.session_state.result is not None and signature != st.session_state.result_signature:
        selection_changed()

    # Tải graph ở nền trong lúc người dùng kiểm tra lựa chọn và thiết lập hành trình.
    # Khi bấm tối ưu, phần lớn thời gian chờ mạng đã được xử lý trước đó.
    if st.session_state.start is not None and st.session_state.destinations:
        preview_locations = [st.session_state.start, *st.session_state.destinations]
        if not (bundled_enabled and bundled_area_contains(preview_locations)):
            preview_bbox = cache_aligned_bbox(selected_bbox(preview_locations, margin))
            if dynamic_bbox_supported(preview_bbox):
                current_future = st.session_state.road_future
                prefetch_failed = (current_future is not None and current_future.done()
                                   and current_future.exception() is not None)
                if (st.session_state.road_prefetch_bbox != preview_bbox
                        or current_future is None or prefetch_failed):
                    prefetch_bbox, road_future = prefetch_road_network(preview_bbox)
                    st.session_state.road_prefetch_bbox = prefetch_bbox
                    st.session_state.road_future = road_future

    if optimize_clicked:
        st.session_state.result = None
        try:
            validate_selection(st.session_state.start, st.session_state.destinations)
            if route_mode == "fixed_end" and end_index is None:
                raise UserFacingError("Vui lòng chọn điểm kết thúc cho hành trình.")
            locations = [st.session_state.start, *st.session_state.destinations]
            use_bundled_graph = bundled_enabled and bundled_area_contains(locations)
            with st.sidebar:
                with st.status("Đang chuẩn bị mạng đường ô tô…", expanded=True) as status:
                    started = perf_counter()
                    requested_bbox = cache_aligned_bbox(selected_bbox(locations, margin))
                    if not use_bundled_graph and not dynamic_bbox_supported(requested_bbox):
                        width_km, height_km = bbox_dimensions_km(requested_bbox)
                        raise UserFacingError(
                            f"Các điểm đang trải trên vùng khoảng {width_km:.0f} × {height_km:.0f} km, "
                            "quá rộng để tải tự động từ OpenStreetMap. Hãy dùng các điểm trong vùng "
                            "đô thị đã đóng gói hoặc cài graph Hà Nội mở rộng trước khi tối ưu."
                        )
                    if not use_bundled_graph:
                        st.write("Kiểm tra các địa điểm trong ranh giới Hà Nội.")
                        for location in locations:
                            ensure_in_hanoi(location)
                    cached_bbox = st.session_state.road_bbox
                    if use_bundled_graph:
                        st.write("Dùng mạng đường Hà Nội có sẵn trên máy.")
                        graph = (st.session_state.bundled_graph
                                 if st.session_state.bundled_graph is not None
                                 else load_bundled_road_network())
                    elif (st.session_state.road_graph is not None and cached_bbox is not None
                            and bbox_contains(cached_bbox, requested_bbox)):
                        st.write("Tái sử dụng mạng đường đã có trong phiên.")
                        graph = st.session_state.road_graph
                    else:
                        prefetched_bbox = st.session_state.road_prefetch_bbox
                        road_future = st.session_state.road_future
                        if (road_future is not None and prefetched_bbox is not None
                                and bbox_contains(prefetched_bbox, requested_bbox)):
                            if road_future.done():
                                st.write("Dùng mạng đường đã được chuẩn bị ở nền.")
                            else:
                                st.write(f"Mạng đường đang tải ở nền; chờ tối đa {ROAD_FUTURE_WAIT_SECONDS} giây.")
                            try:
                                graph = road_future.result(timeout=ROAD_FUTURE_WAIT_SECONDS)
                            except FutureTimeoutError as exc:
                                raise UserFacingError(
                                    "Mạng đường chưa tải xong. Tác vụ vẫn tiếp tục ở nền; "
                                    "hãy chờ một lúc rồi bấm tối ưu lại."
                                ) from exc
                        else:
                            st.write("Đọc cache hoặc tải vùng đường cần thiết từ OpenStreetMap.")
                            graph = load_road_network(requested_bbox)
                        st.session_state.road_graph = graph
                        st.session_state.road_bbox = prefetched_bbox if (
                            road_future is not None and prefetched_bbox is not None
                            and bbox_contains(prefetched_bbox, requested_bbox)
                        ) else requested_bbox
                    nodes, distances = snap_locations(graph, locations)
                    st.session_state.preparation_seconds = perf_counter() - started
                    st.write("Dijkstra → Ma trận chi phí → Held–Karp → Khôi phục tuyến đường.")
                    result = optimize_route(
                        graph, locations, nodes, weight, distances,
                        route_mode=route_mode, end_index=end_index,
                    )
                    st.session_state.result = result
                    st.session_state.result_signature = signature
                    status.update(label="Đã tìm được lộ trình tối ưu", state="complete", expanded=False)
        except Exception as exc:
            with st.sidebar:
                report_error(exc)

    result = st.session_state.result
    if st.session_state.notice:
        with st.sidebar:
            st.success(st.session_state.pop("notice"))
    if st.session_state.map_error:
        with st.sidebar:
            st.error(st.session_state.pop("map_error"))
    route_map = create_base_map()
    features = create_map_features(st.session_state.start, st.session_state.destinations, result)
    map_center, map_zoom = calculate_map_view(
        st.session_state.start, st.session_state.destinations, result
    )
    with st.container(key="map_shell"):
        st_folium(
            route_map,
            height=1000,
            use_container_width=True,
            key="route_map",
            returned_objects=["last_clicked"],
            center=map_center,
            zoom=map_zoom,
            feature_group_to_add=features,
            on_change=handle_map_change,
        )
    if result:
        with st.container(key="results_panel"):
            show_result(result)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        report_error(exc)
