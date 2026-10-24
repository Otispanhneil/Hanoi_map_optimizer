"""Streamlit presentation; the game and policies remain independently testable."""
from dataclasses import asdict
import json
from time import perf_counter

import folium
import streamlit as st
from streamlit_folium import st_folium

from src.chase import Rules, step
from src.chase_maps import MAP_PATH, load_arena, scenario
from src.shortest_path import path_edges


LABELS = {"Đuổi dấu vết": "trail", "Tìm kiếm vùng nghi ngờ": "search", "Phối hợp chặn lối thoát": "contain"}
STATUSES = {"playing": "ĐANG TRUY ĐUỔI", "escaped": "BẠN ĐÃ THOÁT", "caught": "BẠN ĐÃ BỊ BẮT", "timeout": "HẾT GIỜ — BẠN THUA"}


@st.cache_resource(show_spinner=False)
def cached_arena(source, version):
    return load_arena(source)


def node_label(arena, node):
    names = [str(data["name"]) for _, _, data in arena.graph.edges(node, data=True) if data.get("name")]
    return f"N{arena.rank[node] + 1:03d}" + (f" · {names[0]}" if names else "")


def game_map(arena, state, explain=True, reachable=True, tiles=True):
    graph = arena.graph
    def coordinate(node):
        return (graph.nodes[node]["y"], graph.nodes[node]["x"])
    center = coordinate(state.runner)
    canvas = folium.Map(location=center, zoom_start=16, tiles="OpenStreetMap" if tiles else None,
                        control_scale=True)
    streets = []
    for u, v, data in graph.edges(data=True):
        geometry = data.get("geometry")
        streets.append([(y, x) for x, y in geometry.coords] if geometry is not None
                       else [coordinate(u), coordinate(v)])
    folium.PolyLine(streets, color="#64748b", weight=3, opacity=.55).add_to(canvas)
    if explain:
        for node in state.observation.belief:
            folium.CircleMarker(coordinate(node), radius=7, color="#f59e0b", weight=1,
                                fill=True, fill_opacity=.35, tooltip="Máy nghi ngờ: " + node_label(arena, node)).add_to(canvas)
    if reachable and state.status == "playing":
        for node in arena.reachable(state.runner, state.observation.rules.runner_budget):
            folium.CircleMarker(coordinate(node), radius=5, color="#14b8a6", fill=True,
                                fill_opacity=.7, tooltip="Có thể tới: " + node_label(arena, node)).add_to(canvas)
    for path, color in [(state.runner_path, "#0d9488"),
                        *((path, "#e11d48") for path in state.hunter_paths)]:
        if len(path) > 1:
            lines = []
            for u, v, _, data in path_edges(graph, path, "length"):
                geometry = data.get("geometry")
                lines.append([(y, x) for x, y in geometry.coords] if geometry is not None
                             else [coordinate(u), coordinate(v)])
            folium.PolyLine(lines, color=color, weight=6, opacity=.9).add_to(canvas)
    markers = [(state.runner, "BẠN", "#0d9488"),
               *((node, f"ĐỘI {i + 1}", "#e11d48") for i, node in enumerate(state.observation.hunters)),
               *((node, f"THOÁT {i + 1}", "#2563eb") for i, node in enumerate(state.observation.exits))]
    for node, label, color in markers:
        folium.Marker(coordinate(node), tooltip=f"{label}: {node_label(arena, node)}",
                      icon=folium.DivIcon(html=f'<div style="background:{color};color:white;border:2px solid white;'
                          'border-radius:8px;padding:5px 8px;font:bold 11px sans-serif;white-space:nowrap;'
                          f'width:max-content">{label}</div>')).add_to(canvas)
    canvas.fit_bounds([coordinate(n) for n in graph], padding=(20, 20))
    return canvas


def handle_map_click():
    event = st.session_state.get("chase_map", {}).get("last_object_clicked")
    if not event or event == st.session_state.get("chase_last_click"):
        return
    st.session_state.chase_last_click = event
    if st.session_state.chase_state.status != "playing" or st.session_state.get("chase_replay", False):
        return
    arena, state = st.session_state.chase_arena, st.session_state.chase_state
    from src.utils import Location, distance_m
    click = Location("Click", event["lat"], event["lng"])
    def separation(node):
        data = arena.graph.nodes[node]
        return distance_m(click, Location("Node", data["y"], data["x"]))
    options = arena.reachable(state.runner, state.observation.rules.runner_budget)
    node = min(options, key=separation)
    if separation(node) <= 35:
        st.session_state.chase_destination = node
        st.session_state.chase_notice = "Đã chọn " + node_label(arena, node) + ". Bấm Đi nước này để xác nhận."
    else:
        st.session_state.chase_notice = "Hãy chọn một chấm xanh trong phạm vi di chuyển."


def render_chase():
    st.markdown("""<style>
    .block-container {max-width:1400px;padding-top:1rem}
    h1 {font-size:2.2rem !important}
    [data-testid=stMetric] {border:1px solid #dbe4eb;border-radius:10px;padding:8px}
    [data-testid=stMetricValue] {font-size:1.4rem}
    </style>""", unsafe_allow_html=True)
    st.title("BẮT TÔI NẾU CÓ THỂ")
    st.caption("HÀ NỘI / TRỐN TÌM THEO LƯỢT / ĐẤU TRÍ VỚI THUẬT TOÁN")
    with st.sidebar:
        st.header("Phòng điều khiển")
        with st.form("chase_settings"):
            source_label = st.selectbox("Sân chơi", ["Phố cổ Hà Nội · OSM", "Ô lưới mô phỏng"] if MAP_PATH.exists()
                                       else ["Ô lưới mô phỏng", "Phố cổ Hà Nội · OSM"])
            strategy_label = st.selectbox("Chiến thuật máy", list(LABELS), index=2)
            seed = st.number_input("Mã bố trí (seed)", min_value=0, max_value=99999, value=7, step=1)
            runner_budget = st.slider("Bạn đi tối đa mỗi lượt (m)", 80, 180, 160, 20)
            hunter_budget = st.slider("Mỗi đội đi tối đa (m)", 80, 180, 160, 20)
            reveal = st.slider("Tiết lộ vị trí mỗi … lượt", 2, 6, 3)
            turns = st.slider("Giới hạn lượt", 8, 30, 18)
            start = st.form_submit_button("Bắt đầu ván mới", type="primary", width="stretch")
        st.caption("Thiết lập chỉ có hiệu lực khi bắt đầu ván mới.")
        explain = st.toggle("Xem máy đang suy nghĩ gì", value=True)
        tiles = st.toggle("Nền bản đồ trực tuyến", value=False)
        st.caption("Mạng đường vẫn hiển thị và chơi được khi tắt nền trực tuyến.")
        with st.expander("Luật chơi & giới hạn", expanded=False):
            st.write("Bạn đi trước, rồi hai đội di chuyển đồng thời. Được đứng yên. "
                     "Chỉ kiểm tra bắt tại điểm dừng; đi ngang hoặc cắt nhau giữa đường không tính bắt. "
                     "Vào chỗ đội đang đứng thì bị bắt, kể cả đó là lối thoát. "
                     "Tới lối thoát trống thì thắng ngay trước khi đội di chuyển. "
                     "Không thoát trước hết lượt thì thua; vẫn được thoát ở lượt cuối.")
            st.write("Máy biết điểm xuất phát, lối thoát và dấu vết định kỳ. "
                     "Nước đi bí mật không được truyền cho chiến thuật máy. "
                     "Vùng vàng là tập vị trí có thể xảy ra, không phải phân bố xác suất. "
                     "Hai đội được phép cùng dừng tại một nút.")
            st.write("Đây là trò chơi đi bộ trên graph giới hạn, không phải mô phỏng truy đuổi thực tế. "
                     "Chiến thuật phối hợp là heuristic, không có bảo đảm bắt được người chơi.")

    if start or "chase_state" not in st.session_state:
        try:
            source = "osm" if source_label.startswith("Phố") else "demo"
            version = MAP_PATH.stat().st_mtime_ns if source == "osm" and MAP_PATH.exists() else 0
            with st.spinner("Chuẩn bị sân chơi và khoảng cách Dijkstra…"):
                arena = cached_arena(source, version)
                state = scenario(arena, Rules(runner_budget, hunter_budget, reveal, turns), int(seed))
            st.session_state.update(chase_arena=arena, chase_state=state, chase_history=[state],
                                    chase_strategy=LABELS[strategy_label], chase_source=source,
                                    chase_seed=int(seed), chase_last_click=None, chase_destination=None,
                                    chase_elapsed=0.0, chase_replay=False)
        except (ValueError, OSError) as exc:
            st.error(str(exc))
            if "chase_state" not in st.session_state:
                return

    arena, state = st.session_state.chase_arena, st.session_state.chase_state
    st.caption(str(arena.graph.graph.get("source", "Mạng đường")) +
               f" · {len(arena.nodes)} nút · {arena.graph.number_of_edges()} cạnh · " +
               next(k for k, v in LABELS.items() if v == st.session_state.chase_strategy))
    if st.session_state.chase_source == "osm":
        st.caption("© OpenStreetMap contributors · ODbL 1.0 · Mạng hai chiều dùng cho trò chơi; biên sân bị cắt.")
        if arena.graph.graph.get("partial_source") == "True":
            st.caption("Sân trích từ các phần tử OSM đã tải đầy đủ của tệp nguồn bị gián đoạn; có thể thiếu đường. "
                       "Chiều đi được điều chỉnh cho trò chơi, không dùng làm chỉ dẫn giao thông.")
    if st.session_state.chase_source == "demo":
        st.info("Sân ô lưới là dữ liệu mô phỏng đặt tại Hà Nội, không đại diện đường phố thực tế.")
    obs = state.observation
    a, b, c, d = st.columns(4)
    a.metric("Lượt", f"{obs.turn} / {obs.rules.max_turns}")
    b.metric("Vị trí máy còn nghi ngờ", len(obs.belief))
    c.metric("Dấu vết gần nhất", f"Lượt {obs.last_seen_turn}")
    d.metric("Tính nước máy vừa rồi", f"{st.session_state.chase_elapsed * 1000:.1f} ms")

    if state.status != "playing":
        (st.success if state.status == "escaped" else st.error)(STATUSES[state.status])
    else:
        st.markdown("**Chạm chấm xanh để chọn điểm dừng, hoặc chọn trong danh sách.**")
    replay = st.checkbox("Phát lại ván", key="chase_replay")
    shown = state
    if replay and len(st.session_state.chase_history) > 1:
        index = st.slider("Xem lượt", 0, len(st.session_state.chase_history) - 1,
                          len(st.session_state.chase_history) - 1)
        shown = st.session_state.chase_history[index]
    if not replay:
        options = list(arena.reachable(state.runner, obs.rules.runner_budget)) if state.status == "playing" else []
        options.sort(key=lambda n: (arena.distance(state.runner, n), arena.rank[n]))
        if st.session_state.get("chase_destination") not in options:
            st.session_state.chase_destination = None
        left, right = st.columns([4, 1])
        with left:
            selected = st.selectbox("Điểm dừng tiếp theo", options, index=None, key="chase_destination",
                                    format_func=lambda n: f"{node_label(arena, n)} · {arena.distance(state.runner, n):.0f} m"
                                    + (" · ĐỨNG YÊN" if n == state.runner else "")
                                    + (" · LỐI THOÁT" if n in obs.exits else "")
                                    + (" · CÓ ĐỘI TRUY TÌM" if n in obs.hunters else ""),
                                    disabled=state.status != "playing", placeholder="Chọn chấm xanh hoặc điểm dừng…")
        with right:
            st.write("")
            if st.button("Đi nước này", type="primary", disabled=selected is None or state.status != "playing",
                         width="stretch"):
                started = perf_counter()
                try:
                    updated = step(arena, state, selected, st.session_state.chase_strategy)
                    st.session_state.chase_elapsed = perf_counter() - started
                    st.session_state.chase_state = updated
                    st.session_state.chase_history.append(updated)
                    st.session_state.chase_last_click = None
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    if notice := st.session_state.pop("chase_notice", None):
        st.info(notice)
    st_folium(game_map(arena, shown, explain, not replay, tiles), height=570,
              use_container_width=True, key="chase_map", returned_objects=["last_object_clicked"],
              on_change=handle_map_click)
    st.caption("Xanh ngọc: bạn / điểm có thể tới · Đỏ: đội truy tìm · Xanh lam: lối thoát · Vàng: vùng máy nghi ngờ")
    if explain:
        st.write("**Suy luận của máy:** " + shown.explanation)
        st.write("Dấu vết gần nhất: " + node_label(arena, shown.observation.last_seen))
        if shown.targets:
            st.write("Mục tiêu các đội: " + " / ".join(node_label(arena, n) for n in shown.targets))
    with st.expander("Nhật ký & tải ván chơi"):
        st.dataframe([{"Lượt": s.observation.turn, "Bạn": node_label(arena, s.runner),
                       "Đội": " / ".join(node_label(arena, n) for n in s.observation.hunters),
                       "Vùng nghi ngờ": len(s.observation.belief), "Kết quả": STATUSES[s.status]}
                      for s in st.session_state.chase_history], hide_index=True, width="stretch")
        payload = {"schema": 1, "source": st.session_state.chase_source,
                   "seed": st.session_state.chase_seed, "strategy": st.session_state.chase_strategy,
                   "history": [asdict(s) for s in st.session_state.chase_history]}
        st.download_button("Tải nhật ký JSON", json.dumps(payload, ensure_ascii=False,
                           default=lambda value: sorted(value, key=str), indent=2),
                           file_name="hanoi-chase.json", mime="application/json")
