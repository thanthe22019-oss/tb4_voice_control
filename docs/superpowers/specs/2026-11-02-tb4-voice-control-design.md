# Thiết kế hệ thống `tb4_voice_control`

## 1. Mục đích

Xây dựng một repository ROS 2 Humble độc lập, kế thừa phần bản đồ và điều
hướng ổn định từ `tb4_nav2`, để TurtleBot 4 Simulation có thể:

- phân vùng semantic thủ công hoặc bán tự động trên mọi kiểu bản đồ, kể cả
  không gian mở;
- gắn tên, alias và một goal Nav2 hợp lệ cho từng vùng;
- nhận lệnh tiếng Việt bằng giọng nói trên GPU NVIDIA;
- chuyển lệnh thành một hoặc nhiều mục tiêu và thực hiện qua Nav2;
- hiển thị trực quan toàn bộ quá trình để kiểm thử và quay video demo.

Repository mới dự kiến là `tb4_voice_control`, public trên tài khoản GitHub
đang sử dụng cho `tb4_nav2`. Repository `tb4_nav2` hiện tại phải được giữ
nguyên.

## 2. Mục tiêu và tiêu chí thành công

Phiên bản bắt buộc được xem là đạt khi:

1. Người dùng mở được `map.yaml`, nhìn thấy toàn bộ `map.pgm`, và tạo/chỉnh
   sửa/lưu tối thiểu ba polygon có nhãn.
2. Mỗi vùng có ID, tên hiển thị, alias, màu, polygon pixel và một pose đích
   `(x, y, yaw)` trong frame `map`.
3. Ứng dụng từ chối polygon hoặc goal không hợp lệ trước khi lưu.
4. `faster-whisper` nhận được tối thiểu ba mẫu câu tiếng Việt bằng GPU NVIDIA.
5. Parser hiểu lệnh đi đến một vùng và lệnh đi từ vùng A đến vùng B.
6. Nếu robot không ở vùng xuất phát của lệnh A đến B, hệ thống đi qua A trước;
   nếu robot đã ở A, hệ thống chỉ gửi B.
7. Tên vùng không tồn tại được báo trên UI và không tạo goal Nav2.
8. Nav2 tránh vật cản và trả trạng thái từng chặng cho màn hình runtime.
9. Có ảnh bản đồ phân vùng, file vùng, source public, video demo và báo cáo
   PDF 1–2 trang.

## 3. Phạm vi không làm ở phiên bản bắt buộc

- Không tự động suy luận phòng/hành lang bằng watershed hoặc mô hình học máy.
- Không dùng LLM để hiểu lệnh; parser phải xác định được và kiểm thử được.
- Không nghe liên tục; người dùng giữ nút để nói nhằm tránh kích hoạt nhầm.
- Không đưa YOLO và checkpoint `best.pt` từ bài cũ sang repository mới.
- Không hỗ trợ nhiều robot, điều hướng ngoài frame `map`, hay chỉnh sửa bản đồ
  occupancy gốc.
- Không ưu tiên lệnh nhiều waypoint trước khi toàn bộ yêu cầu bắt buộc ổn định.

## 4. Các hướng đã cân nhắc

### 4.1 Trình biên tập vùng

- **OpenCV HighGUI thuần:** ít dependency nhưng khó xây form, danh sách vùng,
  zoom/pan và chỉnh từng đỉnh.
- **PyQt5 + OpenCV — đã chọn:** PyQt5 quản lý UI, OpenCV xử lý hình học và ảnh.
  Hướng này phù hợp một editor thực tế mà vẫn giữ lõi xử lý đơn giản.
- **Web UI cục bộ:** linh hoạt nhưng làm phát sinh server và JavaScript không
  cần thiết cho mục tiêu ROS của bài.

### 4.2 Nhận dạng giọng nói

- **`faster-whisper` CUDA — đã chọn:** nhận dạng tiếng Việt tốt, chạy offline,
  tận dụng GPU và hiệu quả hơn Whisper gốc.
- **Whisper gốc:** chính xác nhưng dependency và chi phí GPU lớn hơn.
- **Vosk:** nhẹ nhưng chất lượng tiếng Việt và khả năng tận dụng GPU kém hơn.

Model mặc định là `small`. Model và thiết bị phải là cấu hình runtime để có thể
hạ xuống CPU/model nhỏ hơn khi chẩn đoán, nhưng demo chính dùng CUDA.

### 4.3 Tổ chức repository

- **Sửa trực tiếp `tb4_nav2`:** ít thao tác nhưng có nguy cơ ảnh hưởng bài cũ.
- **Tạo `tb4_voice_control` từ bản sao tối thiểu — đã chọn:** giữ map, launch và
  nền điều hướng cần thiết; loại phần YOLO không liên quan; đổi đúng tên package,
  executable và tài liệu; tạo lịch sử Git/GitHub riêng.

## 5. Kiến trúc tổng thể

Hệ thống gồm bốn khối có biên rõ ràng:

```text
Map Editor (PyQt5)
    -> regions.yaml + segmented_map.png

Voice Runtime UI (PyQt5)
    -> microphone audio
    -> Speech worker (faster-whisper CUDA)
    -> Vietnamese command parser
    -> route: [region_id, ...]
    -> ROS 2 navigation controller
    -> Nav2 NavigateToPose
    -> status back to UI
```

Map Editor là công cụ chuẩn bị dữ liệu và không cần chạy trong lúc điều hướng.
Voice Runtime UI không trực tiếp điều khiển Nav2 trong UI thread. Nhận dạng và
ROS chạy ở worker riêng, truyền kết quả về UI bằng signal để cửa sổ không bị
đóng băng.

Lõi không phụ thuộc UI gồm chuyển đổi tọa độ, kiểm tra polygon, đọc cấu hình,
chuẩn hóa tiếng Việt, phân tích lệnh và lập route. Các phần này phải kiểm thử
được mà không cần display, microphone, GPU, Gazebo hoặc Nav2 đang chạy.

## 6. Dữ liệu semantic

File `config/regions.yaml` có một schema phiên bản hóa:

```yaml
schema_version: 1
map:
  yaml: ../maps/map.yaml
  frame_id: map
regions:
  - id: zone_a
    name: Khu vực A
    aliases: [A, khu A, khu vực A]
    color: [66, 135, 245]
    polygon_pixels: [[120, 180], [240, 180], [240, 300], [120, 300]]
    goal:
      x: -3.38
      y: -0.41
      yaw: -0.31
```

Quy tắc dữ liệu:

- `id` duy nhất, ổn định và dùng trong code; `name` dùng để hiển thị.
- Alias được chuẩn hóa chữ thường, khoảng trắng và dấu câu khi so khớp; hỗ trợ
  cả cách gọi có dấu và không dấu.
- Polygon lưu theo pixel ảnh để editor có thể tải lại chính xác.
- Goal lưu theo mét/radian trong frame `map` để gửi thẳng cho Nav2.
- Chuyển đổi pixel/ROS dùng resolution và origin từ `map.yaml`, đồng thời đảo
  trục Y vì gốc ảnh nằm ở góc trên trái.
- Goal phải nằm trong polygon và trên ô free theo ngưỡng của `map.yaml`.
- Polygon cần ít nhất ba đỉnh, không tự cắt và không được trùng ID/alias với
  vùng khác.
- Hai vùng có thể dùng chung đường biên nhưng không được chồng lấn diện tích.
  Editor từ chối lưu khi phát hiện phần giao có diện tích; nhờ đó mỗi pose chỉ
  thuộc tối đa một vùng semantic.

## 7. Map Editor

Màn hình gồm toolbar bên trái, canvas bản đồ ở giữa, bảng thuộc tính bên phải
và status bar hiển thị tọa độ pixel/ROS.

Chức năng bắt buộc:

- mở `map.yaml` và tự tìm ảnh được khai báo trong đó;
- zoom, pan và vừa màn hình;
- vẽ polygon bằng click, đóng bằng Enter hoặc click lại điểm đầu;
- chọn vùng, kéo đỉnh, xóa vùng và bật/tắt lớp hiển thị;
- đặt goal bằng click và kéo hướng yaw;
- nhập ID, tên, alias, màu;
- tô polygon bán trong suốt, hiển thị tên và mũi tên goal;
- undo/redo cho các thao tác chỉnh hình học trong phiên hiện tại;
- kiểm tra lỗi trước khi lưu và đưa focus đến vùng lỗi;
- lưu/tải `regions.yaml` và xuất `segmented_map.png`.

Editor không thay đổi `map.pgm` gốc.

## 8. Nhận dạng và phân tích câu lệnh

Voice Runtime có nút giữ để nói, transcript, lệnh đã hiểu, hàng đợi các vùng và
trạng thái Nav2. Thu âm bắt đầu khi nhấn, kết thúc khi thả; audio được chuyển
cho `faster-whisper` sau đó.

Parser theo luật hỗ trợ các ý định bắt buộc:

- `GO_TO(destination)`: “đi đến A”, “đi tới phòng thí nghiệm”;
- `FROM_TO(source, destination)`: “di chuyển từ A đến B”.

Tiền xử lý gồm Unicode chuẩn, chữ thường, bỏ dấu câu, gom khoảng trắng và tạo
bản không dấu để so khớp alias. Khi nhiều alias khớp chồng lấn, ưu tiên alias
dài nhất. Parser không đoán nếu không có hoặc có nhiều vùng đích hợp lệ; UI yêu
cầu người dùng nói lại.

## 9. Điều phối Nav2

Navigation controller kế thừa các hành vi ổn định của `navigate_goals.py`:

- chờ AMCL pose, lifecycle `bt_navigator` active và action server sẵn sàng;
- gửi `NavigateToPose` theo thứ tự;
- hiển thị feedback khoảng cách, timeout, thành công, thất bại và hủy;
- dừng chuỗi ngay khi một chặng bị từ chối, timeout hoặc thất bại;
- cho phép hủy goal hiện tại từ UI.

Trong khi một route đang chạy, nút thu/nhập lệnh mới bị vô hiệu hóa. Người dùng
phải chờ route hoàn thành hoặc hủy route hiện tại trước khi ra lệnh tiếp; hệ
thống không tự xếp hàng hay thay thế route đang chạy.

Pose AMCL hiện tại được đổi sang pixel và kiểm tra point-in-polygon để biết
robot đang thuộc vùng nào. Với `FROM_TO(A, B)`, route là `[B]` nếu robot đang
trong A, ngược lại là `[A, B]`. Với `GO_TO(B)`, route là `[B]`; nếu robot đã ở
B, UI thông báo đã ở đích và không gửi goal mới.

## 10. Xử lý lỗi

- Map/YAML lỗi: không mở editor và hiển thị đường dẫn cùng nguyên nhân cụ thể.
- Vùng hoặc goal lỗi: không lưu file; đánh dấu vùng lỗi trên UI.
- Microphone không mở được: UI vẫn hoạt động và cho phép nhập câu lệnh văn bản
  để kiểm thử.
- CUDA/model lỗi: báo rõ trạng thái, không âm thầm đổi kết quả demo sang backend
  khác; chế độ CPU chỉ được dùng khi người dùng chọn cấu hình đó.
- Transcript rỗng/không hiểu: không gửi goal.
- Vùng không tồn tại hoặc mơ hồ: liệt kê tên vùng hợp lệ và không gửi goal.
- Nav2 chưa sẵn sàng, goal bị từ chối, timeout hoặc mất localization: báo trên UI
  và giữ dữ liệu câu lệnh để người dùng kiểm tra.

## 11. Kiểm thử

### Kiểm thử tự động

- Pixel ↔ ROS ở các góc, tâm và round-trip với map thật.
- Load/save schema vùng và mọi validation chính.
- Chuẩn hóa alias có dấu/không dấu, chữ hoa và dấu câu.
- Parser cho câu GO_TO, FROM_TO, vùng không tồn tại và câu mơ hồ.
- Lập route dựa trên vùng hiện tại.
- Navigation controller với adapter Nav2 giả: success, rejected, timeout, cancel.
- Smoke test tạo UI bằng Qt offscreen, không yêu cầu display.

### Kiểm thử tích hợp thủ công

- Tạo ba vùng trên bản đồ warehouse và tải lại để chỉnh sửa.
- Kiểm tra goal bằng RViz/Nav2 trước khi quay demo.
- Thu ít nhất ba câu lệnh bằng micro thật trong môi trường quay.
- Chạy các trường hợp: đi một vùng, A đến B, robot đã ở A, vùng không tồn tại,
  hủy giữa chặng và vật cản xuất hiện trên đường.

## 12. Milestone trong một tuần

### Milestone 0 — Tách repository và baseline

- Tạo `tb4_voice_control` từ phần cần thiết của `tb4_nav2`.
- Đổi tên package/entry point/tài liệu, loại YOLO và file build cũ.
- Chứng minh launch Nav2 và ba goal baseline vẫn hoạt động.
- Khởi tạo Git, tạo GitHub public và push baseline sạch.

**Điểm chặn:** chưa làm feature mới nếu baseline Nav2 không chạy.

### Milestone 1 — Mô hình vùng và hình học bản đồ

- Định nghĩa `regions.yaml`, chuyển đổi pixel/ROS và validation.
- Tạo test tự động cho schema, geometry và occupancy.
- Chuyển ba goal hiện tại thành ba vùng mẫu có goal hợp lệ.

**Bằng chứng:** test pass và CLI validation đọc được map/vùng mẫu.

### Milestone 2 — Map Editor

- Xây canvas, zoom/pan, vẽ/chọn/sửa/xóa polygon.
- Thêm form thuộc tính, đặt goal/yaw, undo/redo và validation.
- Lưu/tải YAML, xuất bản đồ tô màu có nhãn.

**Bằng chứng:** ảnh phân vùng ba vùng và video ngắn chỉnh rồi tải lại một vùng.

### Milestone 3 — Parser tiếng Việt

- Chuẩn hóa transcript, index alias, nhận GO_TO/FROM_TO.
- Xử lý vùng lạ/mơ hồ và tạo route theo vùng hiện tại.
- Test tối thiểu ba câu bắt buộc cùng các biến thể có/không dấu.

**Bằng chứng:** test parser pass, không cần microphone hay ROS.

### Milestone 4 — Speech GPU và Voice Runtime UI

- Cài `faster-whisper` trong virtual environment riêng.
- Thu âm push-to-talk, chạy model `small` bằng CUDA.
- Hiển thị transcript, intent, route, lỗi và hỗ trợ nhập text để chẩn đoán.

**Bằng chứng:** GPU được sử dụng và ba file/câu tiếng Việt nhận dạng đúng tên
vùng mong đợi.

### Milestone 5 — Tích hợp Nav2 end-to-end

- Nối route với navigation controller và feedback UI.
- Kiểm tra AMCL, trạng thái Nav2, timeout, cancel và lỗi từng chặng.
- Chạy GO_TO, FROM_TO và vùng không tồn tại trong simulation.

**Bằng chứng:** robot đến đúng vùng và UI phản ánh đúng trạng thái từng chặng.

### Milestone 6 — Hoàn thiện nội dung nộp

- README cài đặt/build/chạy/demo; script setup môi trường speech.
- Chụp ảnh và quay video luồng giọng nói → parser → Nav2.
- Viết báo cáo PDF 1–2 trang và kiểm tra repository public từ môi trường sạch.

### Milestone 7 — Mở rộng sau khi ổn định

- Hỗ trợ câu nhiều waypoint như “từ A qua C rồi đến B”.
- Hiển thị đường đi dự kiến trên UI/RViz nếu còn thời gian.

Milestone này không được phép làm chậm hoặc làm mất ổn định Milestone 0–6.

## 13. Deliverables dự kiến

- Repository GitHub public `tb4_voice_control`.
- Source ROS 2, Map Editor và Voice Runtime UI.
- `maps/map.pgm`, `maps/map.yaml`, `config/regions.yaml`.
- `artifacts/segmented_map.png` và dữ liệu kiểm thử giọng nói phù hợp để công
  khai; không commit bản ghi riêng tư không cần thiết.
- README và hướng dẫn demo.
- Video demo cuối cùng.
- Báo cáo PDF 1–2 trang.

## 14. Các quyết định người triển khai có thể tự chọn

- Bố cục class/file cụ thể miễn giữ các biên module ở mục 5.
- Thư viện thu microphone tương thích Ubuntu 22.04 và virtual environment.
- Màu mặc định của vùng và phím tắt UI.
- Tham số timeout hợp lý, với điều kiện chúng nằm trong file cấu hình và được
  ghi trong README.

