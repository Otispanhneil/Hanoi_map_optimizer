"""Held–Karp tự triển khai cho các biến thể TSP trên ma trận có hướng."""
from collections.abc import Sequence
from math import inf, isfinite, isnan

from src.constants import MAX_DESTINATIONS
from src.utils import UserFacingError


def solve_tsp(cost_matrix: Sequence[Sequence[float]], start_index: int = 0,
              end_index: int | None = None,
              return_to_start: bool = False) -> tuple[list[int], float]:
    """Giải TSP với start cố định và một trong ba kiểu điểm kết thúc.

    +inf biểu diễn cặp không có đường. Không sửa ma trận đầu vào.
    Thời gian O(n² 2ⁿ), bộ nhớ O(n 2ⁿ), n là số điểm cần ghé.
    """
    size = len(cost_matrix)
    if size == 0 or any(len(row) != size for row in cost_matrix):
        raise ValueError("Ma trận chi phí phải vuông và không rỗng.")
    if not isinstance(start_index, int) or not 0 <= start_index < size:
        raise ValueError("Chỉ số điểm xuất phát không hợp lệ.")
    if end_index is not None and (not isinstance(end_index, int) or not 0 <= end_index < size):
        raise ValueError("Chỉ số điểm kết thúc không hợp lệ.")
    if end_index == start_index:
        raise ValueError("Điểm kết thúc cố định phải khác điểm xuất phát.")
    if return_to_start and end_index is not None:
        raise ValueError("Không thể vừa chọn điểm cuối vừa yêu cầu quay về điểm đầu.")
    if size - 1 > MAX_DESTINATIONS:
        raise ValueError("Held–Karp hỗ trợ tối đa 10 điểm cần ghé.")
    costs = [[float(value) for value in row] for row in cost_matrix]
    if any(isnan(value) or value < 0 for row in costs for value in row):
        raise ValueError("Chi phí phải không âm, không được là NaN.")
    if size == 1:
        return [start_index], 0.0

    destinations = [i for i in range(size) if i != start_index]
    n = len(destinations)
    # dp[mask][j]: chi phí nhỏ nhất từ start, ghé đúng tập mask,
    # rồi dừng tại destinations[j]. Bit j tương ứng điểm cần ghé thứ j.
    dp = [[inf] * n for _ in range(1 << n)]
    parent = [[-1] * n for _ in range(1 << n)]
    # Base case: đi trực tiếp từ start tới một điểm.
    for j, destination in enumerate(destinations):
        dp[1 << j][j] = costs[start_index][destination]

    for mask in range(1, 1 << n):
        for j in range(n):
            if not mask & (1 << j) or not isfinite(dp[mask][j]):
                continue
            for k in range(n):
                if mask & (1 << k):
                    continue
                next_mask = mask | (1 << k)
                candidate = dp[mask][j] + costs[destinations[j]][destinations[k]]
                # Transition: nối thêm một điểm chưa ghé vào cuối tuyến.
                if candidate < dp[next_mask][k]:
                    dp[next_mask][k] = candidate
                    parent[next_mask][k] = j

    full_mask = (1 << n) - 1
    if return_to_start:
        # Closed TSP: chọn điểm cuối tạm thời rồi cộng cạnh quay về start.
        last = min(range(n), key=lambda j: dp[full_mask][j] + costs[destinations[j]][start_index])
        optimal_cost = dp[full_mask][last] + costs[destinations[last]][start_index]
    elif end_index is not None:
        # Fixed end: trạng thái cuối bắt buộc nằm tại end_index.
        last = destinations.index(end_index)
        optimal_cost = dp[full_mask][last]
    else:
        # Free end: lấy min trên mọi điểm cuối, KHÔNG cộng cạnh về start.
        last = min(range(n), key=lambda j: dp[full_mask][j])
        optimal_cost = dp[full_mask][last]
    if not isfinite(optimal_cost):
        raise UserFacingError("Không có lộ trình ô tô đi qua tất cả điểm đã chọn. Hãy tăng vùng đệm hoặc đổi địa điểm.")

    # Backtracking: lần theo parent và xóa bit của điểm cuối hiện tại.
    reversed_order = []
    mask = full_mask
    while last != -1:
        reversed_order.append(destinations[last])
        previous = parent[mask][last]
        mask ^= 1 << last
        last = previous
    order = [start_index, *reversed(reversed_order)]
    if return_to_start:
        order.append(start_index)
    return order, optimal_cost


def solve_open_tsp(
    cost_matrix: Sequence[Sequence[float]], start_index: int = 0
) -> tuple[list[int], float]:
    """Giữ interface ban đầu: start cố định, end tự do, không quay về."""
    return solve_tsp(cost_matrix, start_index=start_index)
