"""Các heuristic đơn giản để so sánh với nghiệm tối ưu Held–Karp."""
from collections.abc import Sequence
from math import isfinite

from src.utils import UserFacingError


def route_cost(order: Sequence[int], matrix: Sequence[Sequence[float]]) -> float:
    return sum(float(matrix[a][b]) for a, b in zip(order, order[1:]))


def nearest_neighbor(cost_matrix: Sequence[Sequence[float]], start_index: int = 0,
                     end_index: int | None = None,
                     return_to_start: bool = False) -> tuple[list[int], float]:
    """Chọn điểm chưa ghé gần nhất; giữ điểm cuối cố định đến bước cuối."""
    size = len(cost_matrix)
    if size == 1:
        return [start_index], 0.0
    reserved_end = end_index
    unvisited = set(range(size)) - {start_index}
    if reserved_end is not None:
        unvisited.remove(reserved_end)
    order = [start_index]
    while unvisited:
        current = order[-1]
        candidate = min(unvisited, key=lambda node: float(cost_matrix[current][node]))
        if not isfinite(float(cost_matrix[current][candidate])):
            raise UserFacingError("Nearest Neighbor không tìm được hành trình hợp lệ.")
        order.append(candidate)
        unvisited.remove(candidate)
    if reserved_end is not None:
        order.append(reserved_end)
    if return_to_start:
        order.append(start_index)
    cost = route_cost(order, cost_matrix)
    if not isfinite(cost):
        raise UserFacingError("Nearest Neighbor không tìm được hành trình hợp lệ.")
    return order, cost


def two_opt(order: Sequence[int], cost_matrix: Sequence[Sequence[float]],
            fixed_end: bool = False, return_to_start: bool = False) -> tuple[list[int], float]:
    """Đảo từng đoạn và nhận thay đổi tốt hơn; hỗ trợ ma trận có hướng."""
    best = list(order)
    best_cost = route_cost(best, cost_matrix)
    # Không đổi start; với fixed/closed cũng không đổi phần tử cuối.
    stop = len(best) - 1 if (fixed_end or return_to_start) else len(best)
    improved = True
    while improved:
        improved = False
        for left in range(1, stop - 1):
            for right in range(left + 1, stop):
                candidate = best[:left] + list(reversed(best[left:right + 1])) + best[right + 1:]
                candidate_cost = route_cost(candidate, cost_matrix)
                if candidate_cost < best_cost:
                    best, best_cost = candidate, candidate_cost
                    improved = True
                    break
            if improved:
                break
    return best, best_cost
