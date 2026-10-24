# Kiểm thử chế độ trốn tìm — 23/10/2026

Môi trường: Windows, Python 3.11.9 trong `.venv`, dependencies trực tiếp theo `requirements.txt`.
Kết quả dưới đây là các lượt thực thi trong phiên phát triển này, tách khỏi biên bản cũ `VALIDATION.md`.

## Xác minh lại sau khi phục hồi dữ liệu gốc

Ngày 23/10/2026: **112/112 test đạt**, không skip và không còn lỗi thiếu graph.
Chạy `python -m unittest discover -s tests -q` trong `.venv`: 112 test / 76,945 giây / `OK`.
Các warning từ test dữ liệu hỏng là nhánh lỗi được kiểm tra chủ động, không phải test thất bại.

Hai tệp được tải bằng `git lfs fetch`, đối chiếu kích thước và SHA-256 với con trỏ ở HEAD,
rồi sao chép vào các đường dẫn đang thiếu. Không checkout, reset hay sửa Git index.

| Tệp | Số byte | SHA-256 |
|---|---:|---|
| `data/hanoi_urban_drive.pkl` | 161453151 | `64d686df135c70203e2f845679665697507bbe7a6349b35395582daccfd5ec3e` |
| `data/hanoi_urban_drive.graphml` | 311694800 | `34eb8dc1afee2e2517f9d3e8ed556518e19ba49b8b6641bf5262fa98df9da5b3` |

`scripts/smoke_offline.py` chạy trên graph thật **350.930 nút / 864.982 cạnh**, năm địa điểm
Phenikaa, Mỹ Đình, Cầu Giấy, Hồ Tây, Hồ Hoàn Kiếm. Khoảng snap lớn nhất 217,85 m.

| Mục tiêu | Chi phí | Tổng km | Thời gian ước tính |
|---|---:|---:|---:|
| Quãng đường | 26276,364 m | 26,276 | 32,59 phút |
| Thời gian | 1795,878 giây | 27,049 | 29,93 phút |

Cả hai kết quả có tổng chi phí khớp tổng các chặng. Thứ tự ghé đều `[0, 1, 2, 4, 3]`;
hai mục tiêu có thể chọn đường khác nhau giữa cùng cặp điểm. Không phải dữ liệu giao thông realtime.

Trình duyệt thật tính tuyến Hồ Hoàn Kiếm → Nhà hát Lớn, hiển thị **1,36 km / 1,4 phút**.
Sau Lộ trình → Trốn tìm → Lộ trình, đối chiếu cả bốn metric trước/sau đều giống nhau
(`1.36 km`, `1.4 phút`, `1`, `10.1 ms`). Ảnh: `output/playwright/verified-real-route.png`.
Đã chơi một lượt trên sân trốn tìm trong lượt kiểm tra trình duyệt này.
`pip check` và `compileall` tiếp tục đạt. Lỗi console quan sát được đều từ tile OSM bên ngoài;
không xem đó là bằng chứng nền bản đồ trực tuyến hoạt động.

## Kết quả tự động

**65 test cho phần mở rộng và tích hợp: đạt**, chạy bằng:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_chase tests.test_chase_app tests.test_chase_maps tests.test_app_modes -q
```

Bao gồm:

- Ngân sách âm, 0, vô cực, NaN, sai kiểu; chu kỳ và số lượt không nguyên; tọa độ/chiều dài không hợp lệ.
- Graph quá lớn, sai loại; cạnh song song; đường một chiều; nút không tới được; một đội bị cô lập.
- Đối chiếu Dijkstra với NetworkX trên 12 graph có hướng ngẫu nhiên, nhiều cạnh song song, mọi nguồn.
- Nước đi đúng bằng ngân sách, vượt ngân sách, đứng yên; không dịch chuyển vượt mét.
- Đi vào đội; đội tới bắt; thoát trước bước máy; lối thoát có đội; đi ngang đội giữa đường.
- Thoát và bị bắt ở lượt cuối; hết giờ; không cho đi tiếp sau khi kết thúc; nước sai không sửa state.
- Vùng nghi ngờ mở rộng, loại vị trí theo quan sát âm, tiết lộ trước quyết định máy.
- Hai nước đi ẩn khác nhau tạo đầu vào chiến thuật giống nhau khi chưa được tiết lộ.
- Cấu trúc Observation không chứa vị trí thật hoặc đường đi bí mật; quyết định máy tất định và hợp lệ.
- 48 ván ngẫu nhiên trên ô lưới và 15 ván trên sân OSM kiểm tra bất biến ở từng lượt.
- Seed tái lập; ba lối thoát tách biệt; cấu hình không thể bố trí; các lựa chọn ngân sách trên sân OSM.
- Chia cạnh giữ chi phí, chiều đi, khả năng đi ngược khi nguồn có hai chiều.
- XML đủ/thiếu, từ chối nguồn bị cắt nếu không cho phép rõ ràng; metadata nguồn không đầy đủ.
- UI mở không cần mạng, chọn nước, đi, chơi lại, cấu hình chỉ áp dụng khi restart,
  lỗi thiếu graph không phá ván cũ, trạng thái kết thúc, replay không sửa ván thật.
- Đi nước qua AppTest tới đủ ba kết quả thắng, bị bắt, hết giờ; lỗi tải ở mọi endpoint không ghi đè graph đang có.
- Callback click: chọn đúng nút, từ chối xa, bỏ click lặp, không chọn khi replay hoặc ván kết thúc.
- Mở `app.py?mode=chase` không đụng bộ nạp graph Hà Nội lớn.

`pip check` đạt. `compileall` đạt cho entrypoints, src, scripts và tests.
Chạy toàn bộ repo sau khi phục hồi dữ liệu: **112 test đều đạt**.
Lượt trước khi phục hồi có 111/112 đạt; lỗi thiếu graph đã được xác minh lại và hết lỗi.

### Tích hợp với đề tài cũ

Bảy test trong `tests/test_app_modes.py` kiểm tra màn hình mặc định là giao diện lộ trình,
deep link, mode không hợp lệ, chuyển qua lại ba lần giữ kết quả tuyến theo thời gian/Closed TSP,
giữ điểm cuối cố định, giữ ván chơi, đổi tiêu chí vẫn xóa kết quả cũ đúng lúc và
thiếu graph lớn vẫn hiển thị giao diện cùng điều hướng. Pipeline lộ trình trong test dùng
graph thử có hướng, không coi đó là xác minh graph Hà Nội lớn.
Sau chỉnh sửa cuối về giá trị mặc định của toggle, 23 test UI gốc/UI game/tích hợp đều đạt.
Trình duyệt thật đã chọn Hồ Hoàn Kiếm làm điểm xuất phát, chuyển sang Trốn tìm rồi trở lại;
điểm xuất phát vẫn còn và giao diện lộ trình cũ hiển thị đúng.
Ảnh: `output/playwright/integrated-route.png`, `output/playwright/integrated-chase.png`.

## Benchmark đã chạy

Mỗi sân: 20 seeds × 3 bot chạy trốn × 3 chiến thuật truy tìm = **180 ván**; tổng **360 ván**.
Luật: hai bên 160 m/lượt, tiết lộ mỗi 3 lượt, tối đa 18 lượt.
Kiểm tra vị trí thật thuộc belief và giới hạn di chuyển trong từng bước benchmark.

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_chase.py --source demo --seeds 20 --output output/chase/benchmark-demo.json
.\.venv\Scripts\python.exe scripts/benchmark_chase.py --source osm --seeds 20 --output output/chase/benchmark-osm.json
```

Sân OSM, số ván trong mỗi ô = **thoát / bị bắt / hết giờ**, tổng mỗi ô là 20:

| Bot người trốn | Đuổi dấu vết | Tìm vùng nghi ngờ | Phối hợp chặn |
|---|---|---|---|
| Ngẫu nhiên, tránh đứng vào đội | 0 / 20 / 0 | 0 / 20 / 0 | 0 / 19 / 1 |
| Đi về lối thoát gần nhất | 16 / 4 / 0 | 15 / 5 / 0 | 16 / 4 / 0 |
| Né đội theo heuristic | 15 / 1 / 4 | 15 / 1 / 4 | 13 / 2 / 5 |

Sân OSM: trung bình một bước game trong từng nhóm khoảng 1,50–3,67 ms;
bước lớn nhất quan sát được 24,853 ms. Đây là thời gian bước engine, gồm cập nhật belief
và quyết định máy; không gồm khởi tạo graph hoặc render UI. Không phải cam kết độ trễ.

**Không có bằng chứng chiến thuật phối hợp luôn thắng hai chiến thuật còn lại.**
Đối thủ, bố trí, ngân sách và quy tắc bắt tại điểm dừng đều ảnh hưởng kết quả.
Benchmark dùng bot có luật cố định, chưa phải đánh giá người chơi hay một bộ giải tối ưu.
JSON ghi toàn bộ kết quả từng nhóm và timings thực đo.

## Trình duyệt thật

Đã mở Streamlit trên Chromium qua Playwright tại `127.0.0.1:8502`:

- Render sân ô lưới và sân OSM với geometry cục bộ.
- Chọn từ dropdown, xác nhận nước đi, cập nhật lượt và đội.
- Click điểm xanh trên sân OSM chọn đúng nút; callback dùng `last_object_clicked`.
- Mở nhật ký, tải thành công `hanoi-chase.json` qua trình duyệt.
- Bật phát lại: hiện thanh chọn lượt và bỏ điều khiển nước đi; AppTest kiểm tra xem lượt cũ không sửa state thật.
- Ảnh kiểm tra trong `output/playwright/`.
- Khi tắt nền tile, không thấy console error ở các bước kiểm tra; vẫn có warning từ iframe/Streamlit.
- Khi bật nền tile, môi trường trả `ERR_CONNECTION_REFUSED` với tile.openstreetmap.org.
  Vì vậy nền trực tuyến mặc định tắt; geometry sân được vẽ từ tệp cục bộ.

## Giới hạn và phần cũ của repo

- Graph Hà Nội lớn `hanoi_urban_drive.graphml/.pkl` thiếu trong working tree lúc đầu;
  hiện đã phục hồi đúng tệp theo SHA-256. Test cũ `test_bundled_graph_routes_all_popular_locations`
  đã chạy thành công trên graph gốc, không thay bằng mock hoặc graph nhỏ.
- Các yêu cầu tải graph mới qua OSM API/Overpass đã bị từ chối kết nối hoặc timeout.
  Sân OSM giao kèm được phục hồi từ các phần tử đầy đủ của tệp tải dở và có metadata `partial_source=True`.
- Chưa thử tải đồng thời nhiều người dùng, phiên chơi qua mạng, trình duyệt di động hoặc mất mạng hoàn toàn từ lần mở đầu.
- Không triển khai bắt giữa cạnh, mô hình vận tốc liên tục, GPS, minimax hay bảo đảm thắng.
- Git index đã có các thay đổi từ trước; không commit, reset, checkout hoặc sửa staged changes.
