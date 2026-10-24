"""Sinh các hình biểu đồ cho báo cáo LaTeX từ JSON benchmark đã lưu.

Cần matplotlib (không nằm trong requirements.txt của ứng dụng):
    python -m pip install matplotlib
    python scripts/make_report_figures.py
"""
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "report" / "images"

# Bảng màu phân loại đã kiểm định cho nền sáng (3 slot đầu: xanh, cam, lục lam).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SOFT = "#52514e"
GRID = "#dcdbd6"

HUNTER_LABELS = {"trail": "Đuổi dấu vết", "search": "Tìm kiếm độc lập",
                 "contain": "Phối hợp chặn lối thoát"}
RUNNER_LABELS = {"random": "Ngẫu nhiên", "nearest_exit": "Gần lối thoát",
                 "evasive": "Né tránh"}
MODE_LABELS = {"open": "Tuyến mở", "fixed_end": "Điểm cuối cố định",
               "closed": "Chu trình"}


def style_axes(axes, ylabel: str) -> None:
    axes.set_facecolor(SURFACE)
    axes.set_axisbelow(True)
    axes.yaxis.grid(True, color=GRID, linewidth=0.7)
    axes.xaxis.grid(False)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(GRID)
    axes.tick_params(colors=INK_SOFT, length=0, labelsize=9)
    axes.set_ylabel(ylabel, color=INK_SOFT, fontsize=9)


def capture_figure(demo: dict, osm: dict) -> Path:
    runners = list(RUNNER_LABELS)
    hunters = list(HUNTER_LABELS)
    figure, panels = plt.subplots(1, 2, figsize=(9.2, 3.5), sharey=True)
    figure.patch.set_facecolor(SURFACE)
    datasets = [("Sân lưới mô phỏng (81 nút)", demo), ("Sân OSM cục bộ (358 nút)", osm)]
    width = 0.26
    for panel, (title, payload) in zip(panels, datasets):
        lookup = {(row["runner"], row["hunter"]): row for row in payload["results"]}
        for index, hunter in enumerate(hunters):
            offsets = [position + (index - 1) * width for position in range(len(runners))]
            values = [lookup[(runner, hunter)]["caught"] for runner in runners]
            bars = panel.bar(offsets, values, width - 0.02, label=HUNTER_LABELS[hunter],
                             color=SERIES[index], edgecolor=SURFACE, linewidth=1.0)
            # Nhãn trực tiếp: bù cảnh báo tương phản của slot lục lam và thay bảng số.
            panel.bar_label(bars, padding=2, fontsize=8, color=INK_SOFT)
        style_axes(panel, "Số ván bắt được (trên 20 ván)")
        panel.set_xticks(range(len(runners)))
        panel.set_xticklabels([RUNNER_LABELS[runner] for runner in runners], fontsize=9)
        panel.set_ylim(0, 23)
        panel.set_title(title, color=INK, fontsize=10, pad=8)
    panels[1].set_ylabel("")
    handles, labels = panels[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, frameon=False,
                  fontsize=9, labelcolor=INK_SOFT, bbox_to_anchor=(0.5, 0.005))
    figure.tight_layout(rect=(0, 0.1, 1, 1))
    target = IMAGES / "benchmark-capture.png"
    figure.savefig(target, dpi=220, facecolor=SURFACE)
    plt.close(figure)
    return target


def scaling_figure(payload: dict) -> Path:
    rows = payload["results"]
    points = sorted({row["points"] for row in rows})
    figure, (left, right) = plt.subplots(1, 2, figsize=(9.2, 3.4))
    figure.patch.set_facecolor(SURFACE)

    for index, mode in enumerate(MODE_LABELS):
        series = [next(row["held_karp_mean_ms"] for row in rows
                       if row["points"] == size and row["route_mode"] == mode)
                  for size in points]
        left.plot(points, series, marker="o", markersize=5, linewidth=2,
                  color=SERIES[index], label=MODE_LABELS[mode],
                  markeredgecolor=SURFACE, markeredgewidth=1.0)
    left.set_yscale("log")
    left.yaxis.set_major_locator(LogLocator(base=10.0))
    style_axes(left, "Thời gian Held–Karp (ms, thang log)")
    left.set_xlabel("Số điểm trong ma trận chi phí", color=INK_SOFT, fontsize=9)
    left.set_xticks(points)
    left.set_title("Thời gian chạy tăng theo $2^n$", color=INK, fontsize=10, pad=8)
    left.legend(frameon=False, fontsize=8.5, labelcolor=INK_SOFT, loc="upper left")

    def gap_mean(size: int, key: str) -> float:
        values = [row[key] for row in rows if row["points"] == size and key in row]
        return sum(values) / len(values) if values else 0.0

    width = 0.36
    offsets = range(len(points))
    for index, (key, label) in enumerate((("nn_gap_percent", "Nearest neighbor"),
                                          ("two_opt_gap_percent", "Nearest neighbor + 2-opt"))):
        positions = [position + (index - 0.5) * width for position in offsets]
        values = [gap_mean(size, key) for size in points]
        bars = right.bar(positions, values, width - 0.03, label=label,
                         color=SERIES[index], edgecolor=SURFACE, linewidth=1.0)
        # Bỏ nhãn 0 để hai cột cùng bằng 0 không chồng chữ lên nhau.
        right.bar_label(bars, labels=[f"{value:.1f}" if value else "" for value in values],
                        padding=2, fontsize=7.5, color=INK_SOFT)
    style_axes(right, "Khoảng cách so với tối ưu (%)")
    right.set_xlabel("Số điểm trong ma trận chi phí", color=INK_SOFT, fontsize=9)
    right.set_xticks(list(offsets))
    right.set_xticklabels(points, fontsize=9)
    right.set_ylim(0, max(gap_mean(size, "nn_gap_percent") for size in points) * 1.22)
    right.set_title("Heuristic đắt hơn nghiệm chính xác bao nhiêu", color=INK,
                    fontsize=10, pad=8)
    right.legend(frameon=False, fontsize=8.5, labelcolor=INK_SOFT, loc="upper left")

    figure.tight_layout()
    target = IMAGES / "tsp-scaling.png"
    figure.savefig(target, dpi=220, facecolor=SURFACE)
    plt.close(figure)
    return target


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    IMAGES.mkdir(parents=True, exist_ok=True)
    written = [
        capture_figure(load("output/chase/benchmark-demo.json"),
                       load("output/chase/benchmark-osm.json")),
        scaling_figure(load("output/routing/benchmark-tsp.json")),
    ]
    for path in written:
        print(f"đã ghi {path.relative_to(ROOT)}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
