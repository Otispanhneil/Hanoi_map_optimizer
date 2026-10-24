# Bắt tôi nếu có thể — đồ án Thuật toán ứng dụng

## Chạy và chơi

Tại thư mục dự án, môi trường Python 3.11 `.venv` đã được chuẩn bị:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8502
```

Mở http://localhost:8502: giao diện tối ưu lộ trình cũ là màn hình mặc định.
Dùng **Lộ trình / Trốn tìm** ở đầu sidebar để chuyển cùng phiên; không mở tab hoặc app riêng.
Các điểm, tiêu chí, điểm kết thúc và kết quả tối ưu vẫn còn khi quay lại.
Ván trốn tìm đang dở cũng được giữ khi sang chế độ lộ trình rồi quay lại.
Liên kết `?mode=chase` mở trực tiếp trò chơi. `chase_app.py` là điểm vào tương thích,
dùng chung router nhưng mặc định vào trốn tìm.
Chế độ tối ưu hành trình cũ vẫn cần graph Hà Nội lớn hoặc cache/tải OSM qua Internet.
Nếu thiếu graph đóng gói, ứng dụng hiện cảnh báo và vẫn cho dùng giao diện; không thay
graph ô tô bằng graph hai chiều của trò chơi.

1. Chọn sân, chiến thuật, mã bố trí và luật ở sidebar; bấm **Bắt đầu ván mới**.
2. Chạm chấm xanh để chọn điểm dừng hoặc dùng danh sách. Chờ bản đồ hiện hoàn chỉnh trước khi click.
3. Bấm **Đi nước này**. Chọn đứng yên cũng tiêu tốn một lượt.
4. Tới một lối thoát trống trước giới hạn lượt để thắng.
5. Bật **Xem máy đang suy nghĩ gì** để xem vùng nghi ngờ và mục tiêu các đội.
6. **Phát lại ván** chỉ xem lịch sử, không làm thay đổi ván đang chơi. Tắt để tiếp tục.
7. Mở **Nhật ký & tải ván chơi** để tải JSON. JSON là nhật ký để phân tích, chưa có chức năng nhập lại.

Thiết lập chỉ áp dụng khi bắt đầu ván mới. Ván cũ được giữ nếu cấu hình mới không tạo được sân.
Mặc định hai bên có ngân sách 160 m/lượt, tiết lộ mỗi 3 lượt, tối đa 18 lượt.
Giảm tốc đội truy tìm xuống 80–120 m để dễ hơn; tăng tần suất tiết lộ để khó hơn.

## Luật chính xác

- Sân là đồ thị có hướng, trọng số chiều dài dương. Nước đi là đường ngắn nhất tới một nút trong ngân sách mét.
- Bạn di chuyển trước. Nếu dừng tại nút có đội truy tìm thì bị bắt ngay.
- Nếu không bị bắt và dừng tại lối thoát thì thắng ngay, trước bước của máy.
- Nếu đến lượt tiết lộ, vị trí mới được đưa vào quan sát trước khi máy quyết định.
- Hai đội tính nước đi từ cùng một quan sát, rồi di chuyển đồng thời; được cùng dừng tại một nút.
- Nếu một đội dừng tại vị trí của bạn thì bạn bị bắt. Nếu không, hết lượt cuối mà chưa thoát là thua.
- Tới lối thoát trống ở lượt cuối vẫn thắng. Bắt được người ở lượt cuối được ghi là bị bắt, không phải hết giờ.
- Chỉ xét bắt ở các điểm dừng. Đi ngang một đội hoặc hai đường đi cắt nhau giữa lượt không tính bắt.
- Máy biết vị trí xuất phát, bản đồ, lối thoát, vị trí các đội, luật và dấu vết định kỳ. Máy không thấy nước đi bí mật.

## Thuật toán và mô hình thông tin

`src/chase.py` không phụ thuộc Streamlit. `hunter_decision(arena, observation, strategy)`
chỉ nhận `Observation`; kiểu dữ liệu này không chứa vị trí thật hay đường đi bí mật của người trốn.
`State` giữ vị trí thật để bộ máy trò chơi kiểm tra thắng/thua, tách khỏi đầu vào chiến thuật.

Gọi `d(u,v)` là khoảng cách đường ngắn nhất trên graph; không có đường thì là vô cực.
Tái sử dụng Dijkstra heap của `src/shortest_path.py`, chạy từ từng nút một lần khi tạo sân,
lưu khoảng cách và đường đi cho các lượt sau. Giới hạn sân 600 nút để tránh mở rộng all-pairs quá lớn.
Thời gian tiền xử lý có cận `O(V(V+E) log V)`; lưu toàn bộ đường đi có thể tốn tới `O(V^3)` bộ nhớ.

Nếu `B` là tập vị trí còn khả dĩ, bước dự đoán là:

```text
B_pred = {v : tồn tại u thuộc B, d(u,v) <= ngân sách của người trốn}
```

Nếu có tiết lộ, thay tập dự đoán bằng đúng nút được quan sát. Việc sống sót loại các nút
đang có đội truy tìm, cả trước và sau bước di chuyển của máy. Đây là tập khả dĩ bảo thủ,
không phải xác suất và không suy ra rằng người chơi hành động tối ưu.

**Bất biến:** khi ván còn diễn ra, vị trí thật thuộc vùng nghi ngờ. Lập luận quy nạp dựa vào
nước đi hợp lệ, graph tĩnh, cùng ngân sách, quan sát chính xác và luật bắt tại điểm dừng.
Không áp dụng lập luận này cho GPS nhiễu, quan sát trễ, đường thay đổi hoặc bắt giữa cạnh.
Bộ test kiểm tra bất biến bằng nhiều ván ngẫu nhiên trên cả hai sân.

Ba chiến thuật:

| Mã | Quyết định | Giới hạn |
|---|---|---|
| `trail` | Đi theo đường ngắn nhất tới dấu vết gần nhất, dừng trong ngân sách | Có thể đuổi dấu cũ hoặc đứng tại dấu cũ |
| `search` | Mỗi đội chọn nút tới được có mức bao phủ vùng nghi ngờ lớn nhất | Hai đội có thể chọn cùng chỗ |
| `contain` | Chấm điểm cặp nước đi theo bao phủ chung và tiếp cận lối thoát | Heuristic, không phải minimax hay nghiệm tối ưu toàn cục |

Với `b` là ngân sách đội truy tìm, mức tiếp cận `p` từ `m` là `q(m,p)=1/(1+d(m,p)/b)`;
nếu không tới được thì bằng 0. `search` tối đa trung bình `q` trên tập nghi ngờ.
`contain` tối đa trung bình `max(q(m1,p),q(m2,p))` trên tập nghi ngờ, cộng 0,35 lần
đại lượng tương tự trên các lối thoát. Mỗi đội dùng tối đa 8 ứng viên bao phủ tốt nhất,
bổ sung các nước đi hướng tới lối thoát, rồi liệt kê các cặp ứng viên.
Hệ số 0,35 là lựa chọn thiết kế chưa được tối ưu thực nghiệm. Điểm bao phủ là proxy,
không phải xác suất bắt hay bảo đảm chiến thắng.

## Dữ liệu và khả năng tái lập

- **Ô lưới mô phỏng:** 81 nút, 288 cạnh, tọa độ đặt tại Hà Nội; không phải đường thực tế.
- **Sân Phố cổ:** `data/chase_hanoi.graphml`, 358 nút, 1.184 cạnh, geometry OSM.
  Nguồn là các phần tử XML đã tải đầy đủ trong một tệp Git LFS bị gián đoạn có sẵn tại máy.
  Chỉ giữ một thành phần liên thông trong vùng nhỏ; một số đường có thể thiếu.
  Mạng nguồn là graph ô tô, được biến thành hai chiều để chơi; không phải mạng đi bộ hoàn chỉnh.
  Các cạnh dài được chia thành các đoạn tối đa 90 m, giữ tổng chiều dài và geometry.
  Đây là ràng buộc sân chơi, không phải bằng chứng về giao thông thực tế.
- Ghi công: © OpenStreetMap contributors, ODbL 1.0. Tham khảo https://www.openstreetmap.org/copyright.
- Nền tile trực tuyến mặc định tắt. Game vẽ geometry cục bộ nên chơi được mà không tải tile.
  Chưa xác minh khả năng mở ứng dụng trên máy hoàn toàn ngắt mạng từ lần đầu vì thư viện giao diện có tài nguyên web.

Làm mới graph nhỏ từ dịch vụ OSM khi mạng hoạt động:

```powershell
.\.venv\Scripts\python.exe scripts/prepare_chase_map.py
```

Script kiểm tra graph trước khi thay tệp đích bằng thao tác nguyên tử. Nếu nguồn không hoạt động,
graph đang có vẫn được giữ. Khi chỉ có GraphML cục bộ, có thể trích bằng:

```powershell
.\.venv\Scripts\python.exe scripts/extract_chase_map.py DUONG_DAN_GRAPHML
```

Chỉ dùng `--allow-truncated` khi cố ý phục hồi các phần tử đầy đủ từ nguồn bị cắt;
metadata và giao diện sẽ đánh dấu nguồn không đầy đủ. Không khôi phục hay sửa Git index để tạo sân.

## Demo bảo vệ 3 phút

1. Chọn sân Phố cổ, seed 7, chiến thuật phối hợp và luật mặc định; bắt đầu ván mới.
2. Chỉ rõ bạn, hai đội, ba lối thoát. Tắt/bật lớp suy luận để thấy máy biết gì.
3. Chọn một chấm xanh, xác nhận. Giải thích khoảng cách theo đường, không phải số cạnh.
4. Sau vài lượt, chỉ ra vùng nghi ngờ mở rộng rồi co lại khi tiết lộ.
5. Phát lại lượt 0 và lượt hiện tại; tải nhật ký JSON.
6. Mở bảng benchmark trong `CHASE_VALIDATION.md`: so sánh cùng seeds, cùng luật;
   giải thích rằng chiến thuật phức tạp hơn chưa chắc tốt hơn trên mọi đối thủ.

Chỉ tuyên bố đây là triển khai và so sánh các chiến thuật suy luận/bao phủ trên graph.
Không tuyên bố thuật toán truy đuổi mới, bảo đảm bắt, hoặc hiệu quả truy đuổi ngoài thực tế.
