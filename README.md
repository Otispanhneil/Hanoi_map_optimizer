# HANOI ROUTE OPTIMIZER

## Một ứng dụng, hai chế độ

Màn hình chính vẫn là giao diện tối ưu lộ trình bên dưới. Sidebar có hai nút
**Lộ trình / Trốn tìm** để chuyển trong cùng phiên. Các điểm, thiết lập và kết quả
lộ trình được giữ khi sang chơi; tiến độ ván chơi được giữ khi quay về lộ trình.

### Phần mở rộng: Bắt tôi nếu có thể

Trò chơi trốn tìm theo lượt trên bản đồ Hà Nội, hai đội truy tìm, ba lối thoát,
ba chiến thuật máy, vùng nghi ngờ, phát lại và tải nhật ký.

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

Mặc định mở **Lộ trình**. Chọn **Trốn tìm** hoặc mở `?mode=chase` để chơi.
`chase_app.py` chỉ là điểm vào tương thích, mở cùng ứng dụng với chế độ trốn tìm trước.
Không cần graph Hà Nội lớn để chơi.
Xem [hướng dẫn và thuật toán](CHASE_GUIDE.md), [kết quả kiểm thử](CHASE_VALIDATION.md).
Sân OSM đi kèm là một phần mạng đường được trích từ dữ liệu tải dở, được điều chỉnh
thành hai chiều cho trò chơi; không phải mạng giao thông/đi bộ đầy đủ.

**Tối ưu lộ trình đi qua nhiều địa điểm tại Hà Nội**, phục vụ bài tập lớn môn Thuật toán ứng dụng.

Ứng dụng Python/Streamlit chọn một điểm xuất phát và 1–10 điểm cần ghé, rồi tìm thứ tự ghé tối ưu cho ô tô. Mặc định điểm cuối được chọn tự động; người dùng có thể chọn một điểm cuối cố định hoặc yêu cầu quay về điểm xuất phát. Có hai mục tiêu: tổng quãng đường hoặc tổng thời gian di chuyển ước tính.

## Cài đặt và chạy trên Windows 11

Khuyến nghị **Python 3.11 64-bit** (phiên bản đã kiểm tra). Các dependency trực tiếp được chốt trong `requirements.txt`; `scikit-learn` phục vụ tìm nút gần nhất trên graph tọa độ địa lý của OSMnx.

Mở PowerShell tại thư mục dự án:

```powershell
git lfs install
git clone <URL_REPOSITORY>
cd Hanoi_map_optimizer
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Nếu PowerShell không cho phép activate, có thể dùng trực tiếp Python trong môi trường ảo, không cần đổi execution policy:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Truy cập `http://localhost:8501`. Lần mở đầu tiên chuẩn bị graph Hà Nội trong RAM trước khi cho phép tương tác; các lượt thêm/xóa điểm sau đó không phải đọc lại graph. Trên macOS/Linux dùng `python3 -m venv .venv` rồi `source .venv/bin/activate`.

Ứng dụng đã đi kèm graph mạng đường Hà Nội mở rộng trong `data/`, vì vậy thao tác tối ưu không gọi Overpass. Tệp PBF nguồn chỉ cần khi muốn làm mới dữ liệu:

Hai tệp graph lớn trong `data/` được quản lý bằng **Git LFS**. Cài [Git LFS](https://git-lfs.com/) trước khi clone; nếu đã clone mà chỉ nhận được tệp con trỏ, chạy `git lfs pull` trong thư mục dự án.

```powershell
New-Item -ItemType Directory -Force .cache\osm
curl.exe -L --output .cache\osm\vietnam-latest.osm.pbf https://download.geofabrik.de/asia/vietnam-latest.osm.pbf
.\.venv\Scripts\python.exe scripts/preload_hanoi_pbf.py
```

Script đọc PBF cục bộ, chỉ trích mạng đường ô tô trong bbox Hà Nội, kiểm tra liên thông nội đô–Hòa Lạc–Sơn Tây–Sóc Sơn rồi mới thay gói đang chạy. Có thể đặt biến môi trường `HANOI_PRELOAD_MAP=0` nếu cần tắt việc nạp graph đóng gói.

Script Overpass theo tile vẫn được giữ làm phương án phụ cho riêng hành lang **nội đô – Hòa Lạc**:

```powershell
.\.venv\Scripts\python.exe scripts/preload_hanoi.py --profile west
```

Profile này chia vùng lớn thành các ô nhỏ có phần chồng mép và cache từng ô. Do Overpass công khai có thể timeout, cách PBF phía trên là lựa chọn mặc định để triển khai ổn định.

## Sử dụng

1. Chọn một địa điểm phổ biến và bấm **Đặt điểm xuất phát**, hoặc tìm địa chỉ rồi dùng kết quả làm điểm xuất phát.
2. Nếu chưa chọn điểm xuất phát, click đầu tiên trên bản đồ sẽ trở thành **điểm số 1 – điểm xuất phát**. Các click tiếp theo được thêm vào danh sách điểm cần ghé. Bạn cũng có thể chọn từ danh sách hoặc tìm tên/địa chỉ. Nút ✕ cạnh điểm xuất phát hoặc từng điểm ghé dùng để xóa điểm đã chọn nhầm. Sau khi xóa, các điểm tùy chọn còn lại được đánh số lại liên tục; xóa hết sẽ đưa bộ đếm về đầu.
3. Chọn **Quãng đường** hoặc **Thời gian di chuyển**.
4. Bấm **TỐI ƯU LỘ TRÌNH**. Các điểm trong bbox Hà Nội dùng ngay graph cục bộ và không chờ Overpass. Điểm nằm ngoài vùng này mới cần đọc cache động hoặc tải OSM.
5. Xem tổng km, phút ước tính, số điểm ghé, thời gian thuật toán, thứ tự ghé, từng chặng và ma trận chi phí.

Trong mục thu gọn **Điểm kết thúc**, có ba chế độ:

- **Tự động:** Open TSP, thuật toán tự chọn điểm cuối.
- **Do tôi chọn:** người dùng chọn một điểm trong danh sách làm điểm cuối bắt buộc.
- **Quay về điểm xuất phát:** Closed TSP, thêm chặng cuối trở về điểm bắt đầu.

Mục **Chi tiết thuật toán** so sánh Held–Karp với Nearest Neighbor và Nearest Neighbor + 2-opt. Held–Karp vẫn là tuyến được vẽ; hai heuristic chỉ dùng để minh họa đánh đổi giữa tốc độ và chất lượng nghiệm. Mục **Tải kết quả** xuất thứ tự CSV hoặc bản đồ HTML độc lập.

Nút lớp bản đồ ở góc trên bên phải cho phép chuyển giữa **Đường phố** (OpenStreetMap) và **Vệ tinh** (Esri World Imagery). Lớp đường phố được chọn mặc định.

Giao diện dùng bố cục bản đồ toàn màn hình: bảng điều khiển luôn mở và cố định ở bên trái, bản đồ chiếm toàn bộ vùng còn lại. Sidebar được chia thành ba khối **Điểm xuất phát**, **Điểm cần ghé** và **Thiết lập lộ trình**; bộ đếm, danh sách điểm và nút xóa nằm ngay trong khối tương ứng. Nút tối ưu được giữ ở cuối sidebar để luôn dễ truy cập. Sau khi tối ưu, cuộn xuống dưới bản đồ để xem thống kê, so sánh thuật toán và tải kết quả.

Khi click để thêm điểm, Streamlit vẫn chạy lại script để xử lý sự kiện nhưng component Leaflet được giữ nguyên. Nền và tile bản đồ không bị dựng lại; ứng dụng chỉ cập nhật marker, polyline, tâm và mức zoom qua layer động.

Marker xanh ngọc là xuất phát; marker cam là kết thúc; số marker sau tối ưu trùng với bảng thứ tự (bắt đầu từ 1). Đường xanh theo geometry các cạnh OSM. Chấm nhỏ xám biểu diễn nút đường đã snap. Địa điểm có tên chung như Hồ Tây, Long Biên là vị trí đại diện, không phải toàn bộ khu vực; kiểm tra marker trước khi chạy.

## Kiến trúc

```text
Input → Coordinates → Kiểm tra polygon Hà Nội → Driving road network
      → Snap nearest node → Dijkstra → Cost Matrix
      → Held–Karp → Truy vết thứ tự và cạnh đường → Folium → Kết quả
```

```text
hanoi-route-optimizer/
├── app.py                     # UI, trạng thái phiên và thông báo tiếng Việt
├── requirements.txt           # Dependency trực tiếp đã chốt phiên bản
├── requirements-lock.txt      # Toàn bộ môi trường đã kiểm thử trên Python 3.11
├── README.md
├── .streamlit/config.toml      # Theme và ẩn chi tiết lỗi trong UI
├── src/
│   ├── constants.py            # Giới hạn và giả định tốc độ
│   ├── utils.py                # Location, kiểm tra đầu vào, Haversine
│   ├── geocoding.py            # Nominatim và ranh giới hành chính
│   ├── map_service.py          # Graph, cache, speed, travel time, snap
│   ├── shortest_path.py        # Dijkstra, cost matrix, chọn cạnh song song
│   ├── tsp.py                  # Held–Karp tự viết, bitmask và parent
│   ├── heuristics.py           # Nearest Neighbor và cải thiện 2-opt
│   ├── route_optimizer.py      # Kết nối thuật toán, geometry và thống kê
│   └── visualization.py        # Bản đồ Folium
├── data/
│   ├── popular_locations.py     # Các địa điểm gợi ý
│   ├── hanoi_urban_drive.graphml # Mạng đường Hà Nội đóng gói sẵn
│   ├── hanoi_urban_drive.pkl     # Bản đã lọc để nạp nhanh khi chạy
│   └── hanoi_urban_drive.meta.json # Profile và phạm vi graph hiện hành
├── scripts/
│   ├── preload_hanoi.py        # Tạo graph urban/west trước khi triển khai
│   ├── preload_hanoi_pbf.py    # Tạo graph toàn Hà Nội từ PBF cục bộ
│   ├── smoke_offline.py        # Kiểm tra pipeline bằng graph đóng gói
│   ├── smoke_live.py           # Kiểm tra tích hợp dịch vụ OSM thực (tùy chọn)
│   ├── benchmark_tsp.py        # So sánh Held–Karp với NN/2-opt theo số điểm
│   ├── benchmark_chase.py      # Benchmark 360 ván trò chơi truy tìm
│   └── make_report_figures.py  # Sinh biểu đồ cho báo cáo từ JSON benchmark
├── output/                    # Kết quả benchmark dạng JSON và ảnh kiểm tra
├── report/                    # Báo cáo LaTeX (main.pdf là bản biên dịch)
└── tests/                     # Unit test và Streamlit AppTest offline
```

Stack: Python, Streamlit, OSMnx, NetworkX, Folium, streamlit-folium, Pandas, NumPy và scikit-learn. Shapely kiểm tra polygon/geometry; GeoPandas được OSMnx cài cùng. Không dùng API tối ưu tuyến có sẵn.

## Dijkstra và ma trận chi phí

`src/shortest_path.py` **tự cài đặt Dijkstra bằng heap nhị phân** trên cấu trúc `MultiDiGraph` của NetworkX. Đồ thị giữ chiều đường và nhiều cạnh giữa hai nút; với các cạnh song song, thuật toán lấy cạnh có trọng số nhỏ nhất theo đúng mục tiêu đang chọn. Trọng số `length` có đơn vị mét; `travel_time` có đơn vị giây. Không dùng A* hoặc hàm shortest-path có sẵn của NetworkX.

Chạy Dijkstra một lần từ mỗi địa điểm và dừng sớm ngay khi đã chốt đủ các nút đích, sau đó truy vết đường đi cho các cặp địa điểm. Với `m = n + 1` địa điểm, cận trên của phần tìm khoảng cách là `O(m (V + E) log V)` trên heap nhị phân. Ma trận không nhất thiết đối xứng. Cặp không có đường là `+∞`; không loại cả bài toán chỉ vì có một cặp không tới được, bởi Open TSP vẫn có thể có nghiệm.

Khi dựng tuyến, chọn cạnh song song có trọng số nhỏ nhất **theo đúng tiêu chí đang tối ưu**. Tổng quãng đường, tổng thời gian và geometry đều lấy từ cùng các cạnh đó, không trộn tuyến ngắn nhất và tuyến nhanh nhất.

## Held–Karp Dynamic Programming

Interface mặc định:

```python
order, cost = solve_open_tsp(cost_matrix, start_index=0)
```

Interface tổng quát:

```python
order, cost = solve_tsp(
    cost_matrix,
    start_index=0,
    end_index=None,          # đặt chỉ số nếu muốn fixed end
    return_to_start=False,   # True cho Closed TSP
)
```

Với `n` điểm ghé (không gồm start), mỗi điểm tương ứng một bit. `dp[mask][j]` là chi phí nhỏ nhất đi từ start, ghé đúng tập `mask` và dừng tại điểm `j`.

- **Khởi tạo:** `dp[1 << j][j] = cost[start][j]`.
- **Chuyển trạng thái:** với `k` chưa thuộc `mask`, cập nhật `dp[mask | (1 << k)][k]` bằng giá trị nhỏ nhất của `dp[mask][j] + cost[j][k]`.
- **Điểm cuối tự do:** `min_j dp[(1 << n) - 1][j]`. Không cộng chi phí về start.
- **Điểm cuối cố định:** chọn trạng thái đầy đủ kết thúc đúng tại `end_index`.
- **Closed TSP:** chọn `min_j(dp[full][j] + cost[j][start])`, rồi thêm start vào cuối thứ tự.
- **Truy vết:** lưu `parent[mask][k]`, lần ngược từ điểm cuối tối ưu, xóa từng bit, đảo danh sách rồi thêm start ở đầu.
- **Thời gian:** `O(n² × 2ⁿ)`; **bộ nhớ:** `O(n × 2ⁿ)`.

Với 10 điểm ghé, mỗi bảng có 1.024 × 10 ô. Solver xử lý ma trận có hướng, chi phí bằng 0, nhiều nghiệm bằng nhau và cặp không có đường. Có thể chọn start khác 0. Nếu chỉ có start, solver trả `[start], 0`; UI yêu cầu ít nhất một điểm ghé.

### Heuristic dùng để so sánh

**Nearest Neighbor** bắt đầu tại start và liên tục chọn điểm chưa ghé có chi phí nhỏ nhất. Với điểm cuối cố định, điểm đó được giữ lại đến bước cuối. Độ phức tạp `O(n²)`.

**2-opt** bắt đầu từ kết quả Nearest Neighbor, thử đảo các đoạn của thứ tự ghé và chỉ nhận thay đổi làm giảm tổng chi phí. Vì ma trận đường có hướng, chương trình tính lại chi phí đầy đủ sau mỗi phép đảo. Với tối đa 10 điểm, cách viết rõ ràng này đủ nhanh và dễ giải thích. Heuristic không thay thế Held–Karp và không đảm bảo nghiệm tối ưu.

Tính tối ưu áp dụng cho thứ tự ghé trên ma trận và graph đã tải. Mỗi địa điểm xuất hiện một lần trong danh sách TSP, nhưng đường thực tế có thể đi ngang địa điểm khác trước lượt ghé hoặc đi lại qua giao lộ. Bài toán không cấm lặp nút trên road network.

## Dữ liệu mạng đường, tốc độ và giới hạn

- `data/hanoi_urban_drive.graphml` là dữ liệu nguồn; `data/hanoi_urban_drive.pkl` là thành phần liên thông mạnh đã rút gọn thuộc tính để nạp nhanh. Ứng dụng chuẩn bị bản nhanh một lần khi khởi động, nên các lượt click sau đó không tranh CPU với quá trình giải nén graph và bước tối ưu không phụ thuộc Overpass.
- `data/hanoi_urban_drive.meta.json` ghi nguồn, profile và bbox thực tế. Graph hiện tại được tạo từ PBF và phủ bbox kinh độ **105,20–106,10**, vĩ độ **20,50–21,45**, gồm nội đô, Hòa Lạc, Sơn Tây và Sóc Sơn.
- Với graph động, ứng dụng từ chối sớm bbox có cạnh trên **35 km** hoặc diện tích trên **700 km²**. Truy vấn lớn hơn thường tải cả vùng trống giữa các điểm và dễ làm Overpass timeout. Giao diện trả thông báo cụ thể thay vì chờ không giới hạn.
- Graph động ngoài phạm vi đóng gói dùng vùng đệm cố định **2 km** quanh các điểm. Tùy chọn này được giữ trong mã để giao diện gọn và kết quả nhất quán. Trước khi tải động, từng địa điểm vẫn được kiểm tra bằng polygon hành chính Hà Nội lấy từ Nominatim.
- `graph_from_bbox(..., network_type="drive", retain_all=True)` của OSMnx 2.0.6 tải mạng ô tô. BBox tạo truy vấn Overpass đơn giản hơn polygon hành chính nhiều đỉnh và giảm dữ liệu lần đầu. Ở sát ranh giới, vùng đệm có thể chứa một phần đường lân cận nhưng mọi địa điểm đầu vào vẫn phải nằm trong Hà Nội.
- Với graph động ngoài phạm vi đóng gói, đường vòng nằm ngoài bbox có đệm cố định sẽ không được xét. Các điểm trong bbox Hà Nội dùng graph PBF đầy đủ đã chuẩn bị sẵn.
- `add_edge_speeds` dùng `maxspeed` khi hợp lệ, bổ sung tốc độ theo loại đường trong `ROAD_SPEEDS`, loại không biết mặc định 30 km/h. `add_edge_travel_times` tính `length / (speed_kph / 3.6)`.
- Tốc độ fallback là giả định mô hình học thuật, không phải bảng giới hạn tốc độ pháp lý. Thời gian không tính giao thông realtime, đèn đỏ, rẽ, đỗ xe hoặc dừng ghé.
- Snap vào nút ô tô gần nhất; từ chối điểm cách nút quá 1.500 m và hai điểm cùng snap vào một node. Không mô hình hóa đường nối từ cửa địa điểm tới nút đường. Khoảng cách snap hiện trong kết quả.
- Điểm cách nhau dưới 50 m bị coi là trùng/quá gần. Tọa độ gợi ý chỉ mang tính tham khảo, nên đối chiếu cổng ô tô thực tế. Dữ liệu OSM có thể thiếu hoặc chưa phản ánh hạn chế rẽ; đây là công cụ học thuật, không thay thế chỉ dẫn giao thông thực tế.

## Cache, Internet và xử lý lỗi

- `st.cache_resource`: giữ graph đóng gói và tối đa 4 graph động trong RAM; graph được dùng chỉ đọc sau khi tải.
- Khóa cache graph đóng gói gồm thời gian sửa và kích thước của Pickle, GraphML và metadata. Khi thay gói dữ liệu, phiên Streamlit đang mở tự nạp graph mới một lần thay vì tiếp tục giữ graph cũ trong RAM.
- Trong cùng phiên, nếu vùng điểm mới nằm hoàn toàn trong graph vừa tải, ứng dụng dùng lại graph đó ngay cả khi danh sách điểm đã thay đổi.
- `.cache/graphs/*.graphml`: cache graph có cả tốc độ và thời gian, ghi qua tệp tạm rồi thay thế nguyên tử. Bbox được mở ra theo lưới ổn định khoảng 1,1 km để các lựa chọn gần nhau dùng chung cache; khóa chứa bbox, phiên bản OSMnx và bảng tốc độ.
- `.cache/http/`: cache HTTP OSMnx, gồm kết quả geocoding/ranh giới. `st.cache_data` cache tìm kiếm và polygon giữa các lần rerun.
- Khi tải graph mới, ứng dụng có hai endpoint Overpass công khai và tự chuyển endpoint nếu máy chủ đầu tiên không phản hồi.
- `scripts/preload_hanoi_pbf.py` tạo graph chính từ PBF mà không gọi Overpass. `scripts/preload_hanoi.py` theo tile chỉ là phương án phụ. Các điểm nằm ngoài bbox đóng gói vẫn cần Internet ở lần đầu.
- Cache đĩa giữ tới khi người dùng xóa; dữ liệu có thể cũ. Muốn tải mới, dừng ứng dụng, xóa `.cache` trong **thư mục dự án**, rồi khởi động lại.
- Nếu mất mạng, graph/ranh giới đã cache có thể tái sử dụng; tìm kiếm mới, khu vực mới và tile nền vẫn cần Internet. Đây không phải ứng dụng bản đồ offline hoàn toàn.
- Dịch vụ tìm địa chỉ chỉ gọi khi bấm nút; không autocomplete theo từng ký tự. Có khóa dùng chung tiến trình và khoảng nghỉ để giới hạn tối đa một yêu cầu Nominatim mỗi giây. Không bật reverse geocoding tự động để giữ thao tác click ổn định.
- Có timeout yêu cầu mạng 60 giây; OSMnx có thể chờ hoặc thử lại khi Overpass quá tải, nên tổng thời gian tải có thể dài hơn. UI hiển thị tiến trình. Các lỗi dịch vụ được đổi thành thông báo tiếng Việt, chi tiết kỹ thuật ghi ở terminal.
- Giới hạn chờ **30 giây** chỉ áp dụng cho graph động ngoài phạm vi dữ liệu Hà Nội đóng gói. Trong phạm vi Hà Nội, ứng dụng luôn dùng graph đã có trong RAM.

Ứng dụng mặc định dành cho chạy cục bộ một tiến trình. Nếu triển khai nhiều worker/người dùng, cần dịch vụ geocoding phù hợp và giới hạn tần suất dùng chung. Có thể cấu hình endpoint bằng biến môi trường:

```powershell
$env:NOMINATIM_URL = "https://nominatim.openstreetmap.org/"
$env:OVERPASS_URL = "https://overpass-api.de/api"
$env:OSM_USER_AGENT = "HanoiRouteOptimizer/1.0 (contact: your-email@example.com)"
```

## Kiểm thử và benchmark

Kết quả kiểm tra thực tế và các giới hạn xác minh được ghi trong [VALIDATION.md](VALIDATION.md).

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py src data tests scripts
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\smoke_offline.py
```

`smoke_offline.py` nạp đúng graph đi kèm, snap năm địa điểm phổ biến, chạy toàn bộ pipeline cho cả quãng đường và thời gian, rồi kiểm tra tổng chi phí có khớp với các chặng đã dựng hay không. Script không gọi dịch vụ mạng.

Benchmark tầng thứ tự ghé (so sánh nghiệm chính xác với hai heuristic, 4–11 điểm, ba kiểu kết thúc):

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_tsp.py --weight length
.\.venv\Scripts\python.exe scripts\benchmark_tsp.py --weight travel_time `
  --output output\routing\benchmark-tsp-time.json
```

Kết quả ghi vào `output/routing/`. Trên bộ 11 địa điểm mẫu, Held–Karp giữ dưới 7,2 ms ở giới hạn 10 điểm ghé; Nearest Neighbor lệch tới 19,53% và thêm 2-opt còn lệch tới 3,97% so với nghiệm tối ưu — con số đo được cho việc đánh đổi bảo đảm tối ưu lấy tốc độ.

Các test offline kiểm tra Held–Karp với vét cạn cho free end, fixed end và Closed TSP; ma trận ngẫu nhiên có hướng 2–6 node và mọi start; 10 điểm ghé; Nearest Neighbor; 2-opt; đường một chiều; cạnh song song; dữ liệu lỗi; tọa độ; snap; tốc độ fallback; geometry và thống kê. Streamlit AppTest kiểm tra mở app, thêm/xóa/trùng điểm, tính tuyến bằng graph thử nghiệm và xóa kết quả cũ khi đổi tiêu chí. Bộ test cũng xác nhận thông báo khi thiếu Git LFS và khả năng tự dùng GraphML nếu tệp Pickle bị hỏng.

Kiểm tra tích hợp thật (cần Internet, gọi Nominatim/Overpass và ghi cache):

```powershell
.\.venv\Scripts\python.exe scripts/smoke_live.py
```

UI đo riêng Dijkstra và Held–Karp bằng `perf_counter`; tải mạng, kiểm tra polygon và snap được ghi riêng. Khi báo cáo benchmark, ghi phiên bản Python, số nút/cạnh graph, số điểm ghé và mục tiêu. Không lấy thời gian tải OSM làm thời gian của Held–Karp.

## Tài liệu tham khảo

- [OSMnx: API và cách sử dụng](https://osmnx.readthedocs.io/en/stable/user-reference.html)
- [OSMnx 2.0.6 đã dùng trong dự án](https://pypi.org/project/osmnx/2.0.6/)
- [NetworkX: single_source_dijkstra](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.shortest_paths.weighted.single_source_dijkstra.html)
- [Streamlit](https://docs.streamlit.io/) và [streamlit-folium](https://github.com/randyzwitch/streamlit-folium)
- [Chính sách Nominatim](https://operations.osmfoundation.org/policies/nominatim/)
- [Bản quyền dữ liệu OpenStreetMap](https://www.openstreetmap.org/copyright)
