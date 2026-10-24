# Biên bản kiểm tra

> Xác minh lại bản tích hợp ngày 23/10/2026: graph gốc đã phục hồi và kiểm tra SHA-256,
> **112/112 test đạt**; pipeline thật và chuyển chế độ trên trình duyệt đều đã kiểm tra.
> Xem số liệu và giới hạn hiện tại tại [CHASE_VALIDATION.md](CHASE_VALIDATION.md).
> Nội dung bên dưới là biên bản gốc, không phải tất cả các thao tác đều được chạy lại ở lượt xác minh này.

Ngày kiểm tra: **23/10/2026**. Môi trường Windows, Python **3.11.9**, dependency chi tiết trong `requirements-lock.txt`.

## Đã xác nhận

- Kiểm tra syntax bằng `compileall`: đạt.
- Import toàn bộ module ứng dụng: đạt.
- `pip check`: không có dependency bị thiếu/xung đột.
- Đã tạo graph từ Geofabrik PBF: **350.930 nút, 864.982 cạnh**, phủ bbox **105,20–106,10 / 20,50–21,45** và kiểm tra liên thông hai chiều giữa nội đô, Hòa Lạc, Sơn Tây, Sóc Sơn cùng 13/13 địa điểm phổ biến mà không gọi Overpass.
- `scripts/preload_hanoi_pbf.py` đọc PBF cục bộ, rút gọn thuộc tính runtime, xác minh graph rồi ghi GraphML/Pickle/metadata. Ứng dụng nạp Pickle vào RAM đúng một lần trước khi cho phép tương tác.
- **47 test offline**: tất cả đạt sau khi tổ chức lại sidebar thành ba khối thao tác. Bộ test bao gồm so Held–Karp với vét cạn cho điểm cuối tự do, điểm cuối cố định và Closed TSP; kiểm tra Dijkstra dừng theo tập đích, Nearest Neighbor, 2-opt, đường một chiều, cạnh song song, geometry, tổng chi phí, dữ liệu lỗi, snap, tốc độ, polygon, bbox cache ổn định, tự vô hiệu cache khi thay graph, reset tên/click sau khi xóa điểm, ẩn tùy chọn vùng đệm, chia tile preload, metadata, rút gọn graph PBF, giới hạn vùng quá rộng, graph đóng gói và tương tác Streamlit AppTest.
- Bộ nạp graph nhận biết tệp con trỏ Git LFS và hướng dẫn chạy `git lfs pull`; nếu Pickle hỏng nhưng GraphML hợp lệ, ứng dụng tự chuyển sang GraphML. Cả hai nhánh lỗi/phục hồi đều có test hồi quy.
- Phần chi tiết thuật toán hiển thị quá trình truy vết thứ tự tối ưu theo từng chặng, chi phí chặng và chi phí lũy kế; nội dung giải thích rõ Held–Karp tối ưu toàn cục thay vì chọn tham lam từng bước.
- Khởi động máy chủ Streamlit tại `127.0.0.1:8501`: đạt; endpoint `/_stcore/health` trả `ok`. Máy chủ kiểm thử đã dừng để người dùng có thể tự chạy bằng lệnh trong README.
- Tải polygon Hà Nội từ Nominatim: đạt; kiểm tra **13/13 địa điểm phổ biến** nằm trong polygon này.
- Tải graph ô tô thực quanh Hồ Hoàn Kiếm và Nhà hát Lớn: **1.488 nút, 3.376 cạnh**.
- Snap → Dijkstra → Held–Karp → geometry Folium: chạy thành công trên graph thật cho cả `length` và `travel_time`.
- Tuyến mẫu một điểm ghé: **1.361,75 m**, **86,50 giây ước tính**. Hai mục tiêu cho cùng tuyến ở cặp điểm này; đây không phải kết luận rằng hai mục tiêu luôn tương đương.
- Ghi và đọc lại GraphML: đạt. Lượt đọc cache chạy lại được hai mục tiêu, không tải lại graph.
- Thử thêm điểm thứ ba trên graph thật đã cache: đầu vào `[Hồ Hoàn Kiếm, Nhà hát Lớn, Tràng Tiền]` được sắp lại thành `[Hồ Hoàn Kiếm, Tràng Tiền, Nhà hát Lớn]`, không thêm chặng quay về start.

Graph nhị phân Hà Nội mở rộng mất khoảng **6,15 giây** để đọc lần đầu. Chi phí này được thực hiện một lần trước khi cho phép tương tác. Bốn lượt thêm điểm liên tiếp sau khởi động đo được **0,043–0,047 giây/lượt** ở phía Streamlit. Dijkstra đa đích dừng ngay khi đã chốt đủ địa điểm; benchmark 5 điểm Hà Đông–Quốc Oai–Hòa Lạc–Chương Mỹ–Sơn Tây giảm từ **22,44 giây xuống 1,58 giây**. Benchmark 11 điểm trải rộng toàn Hà Nội mất **7,54 giây**; Held–Karp chỉ chiếm khoảng **0,008 giây**.

Streamlit AppTest dùng đúng graph PBF, không mock dịch vụ mạng, đã trả tuyến 5 điểm dài **60,28 km** mà không có error/exception. Trang chuẩn bị graph trước khi hiển thị đầy đủ; nút tối ưu không còn phải chờ tác vụ nạp graph nền.

Lần kiểm tra final bằng `scripts/smoke_offline.py` nạp graph **350.930 nút / 864.982 cạnh** trong **6,605 giây**, snap năm địa điểm với khoảng cách lớn nhất **217,85 m**. Dijkstra mất **0,629 giây** khi tối ưu quãng đường và **0,564 giây** khi tối ưu thời gian; Held–Karp tương ứng chỉ mất **0,062 ms** và **0,052 ms**. Tổng chi phí của cả hai kết quả khớp với tổng các chặng đã dựng. Streamlit AppTest với `HANOI_PRELOAD_MAP=1` cũng khởi động thành công, không có exception hoặc thông báo lỗi.

Đã tái hiện lỗi phiên Streamlit giữ graph đô thị cũ trong RAM trong khi metadata đã chuyển sang bbox toàn Hà Nội. Khóa cache phiên bản theo tệp đã được bổ sung; khi Pickle/GraphML/metadata thay đổi, graph được nạp lại tự động một lần. Các tọa độ đại diện quanh marker Hòa Lạc trong ảnh snap vào graph mới ở khoảng **16–77 m**, thay vì 10.775 m như graph cũ.

Lượt Streamlit AppTest bật graph đóng gói, chọn Hồ Hoàn Kiếm → Nhà hát Lớn rồi bấm tối ưu hoàn tất thao tác bấm trong khoảng **1,19 giây**, trả tuyến **1,362 km**, không có exception/error và không gọi dịch vụ mạng.

## Giới hạn xác minh

- Overpass từng timeout khi tạo profile `west`; graph PBF hiện tại đã thay thế nhu cầu Overpass cho mọi điểm trong bbox Hà Nội đóng gói.
- PBF nguồn khoảng **331 MB** nằm trong `.cache/osm` và không cần khi chạy ứng dụng. GraphML khoảng **312 MB**; Pickle runtime khoảng **161 MB**. Khi đưa lên Git hosting cần Git LFS hoặc phát hành các tệp dữ liệu dưới dạng artifact riêng.
- Tìm tên địa chỉ qua Nominatim chưa hoàn tất trong kiểm tra dịch vụ thật: kết nối bị đóng với `ConnectionResetError / WinError 10054`. Ranh giới Nominatim và tải đường Overpass đã thành công. UI xử lý lỗi dịch vụ bằng thông báo tiếng Việt; script smoke trả exit code 1 khi phần tìm địa chỉ thất bại, dù tính tuyến đã đạt.
- Không có trình duyệt kết nối khả dụng trong môi trường kiểm tra nên chưa kiểm tra ảnh chụp giao diện. Luồng giao diện đã kiểm tra bằng Streamlit AppTest; HTML Folium đã render thành công.
- Graph động ngoài phạm vi đóng gói dùng vùng đệm cố định 2 km. Thời gian di chuyển là mô hình ước tính, không phải realtime.

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app.py src data tests scripts
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts\smoke_offline.py
.\.venv\Scripts\python.exe scripts/smoke_live.py
```

Script cuối cần Internet cho các dữ liệu chưa cache. Khi dịch vụ tìm địa chỉ hoạt động trở lại, chạy lại để xác nhận toàn bộ tích hợp.
