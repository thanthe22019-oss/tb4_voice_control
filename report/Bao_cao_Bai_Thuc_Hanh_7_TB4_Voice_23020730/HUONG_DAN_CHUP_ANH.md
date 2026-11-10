# Hướng dẫn chụp ảnh minh chứng thực tế cho báo cáo Bài thực hành 7

## Chuẩn bị repository và môi trường (thực hiện trước ảnh 01)

Mở terminal trên desktop và chuyển tới thư mục gốc bản sao repository do bạn chọn (thư mục có `setup.py`, `maps/`, `config/` và `scripts/`). Sau đó lấy đường dẫn hiện tại, kiểm tra ROS và biên dịch trước khi nạp workspace. Chỉ tiếp tục bước sau nếu lệnh kiểm tra/biên dịch trước đó thành công; nếu thiếu ROS hoặc các gói mô phỏng, cài đặt theo `README.md` trước.

```bash
export REPO_ROOT="$(pwd -P)"
test -f "$REPO_ROOT/setup.py" && test -f "$REPO_ROOT/launch/voice_navigation.launch.py"
export REPORT_DIR="$REPO_ROOT/report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730"
mkdir -p "$REPORT_DIR/images"
test -f /opt/ros/humble/setup.bash
source /opt/ros/humble/setup.bash
command -v colcon
ros2 pkg prefix turtlebot4_ignition_bringup
ros2 pkg prefix nav2_bringup
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
test -f "$REPO_ROOT/install/setup.bash"
source "$REPO_ROOT/install/setup.bash"
unset QT_QPA_PLATFORM
```

Giữ terminal này và dùng lần lượt các lệnh bên dưới từ `$REPO_ROOT`. Hoàn tất Map Editor ở ảnh 01--02, đóng cửa sổ Editor, rồi khởi chạy mô phỏng/Nav2/Voice UI đúng một lần ở ảnh 03. Dùng lại duy nhất cửa sổ Voice UI đó cho ảnh 04--09; giữ tiến trình launch chạy đến khi chụp xong. Nếu đang có phiên mô phỏng/Nav2 hoặc Voice UI cũ, kết thúc phiên đó trước khi bắt đầu ảnh 03 để tránh hai bộ điều khiển cùng gửi goal.

> **Lưu ý bảo mật:** Trên Ubuntu, dùng `Shift + PrtSc` để chọn vùng chụp. **Tuyệt đối không chụp cửa sổ terminal đang hiển thị giá trị thật của `GEMINI_API_KEY`**, mật khẩu hay thông báo cá nhân. Ảnh `images/segmented_map.png` đã có sẵn từ `artifacts/segmented_map.png`, không cần chụp lại trừ khi bạn chỉnh sửa lại `config/regions.yaml`.

---

## 1. Ảnh bản đồ Occupancy Grid gốc (`01_original_occupancy_map.png`)

- **Tên file bắt buộc:** `01_original_occupancy_map.png`
- **Cách thực hiện:**
  Mở bản đồ gốc `maps/map.pgm` cùng nội dung `maps/map.yaml`, hoặc mở trong Map Editor với các hộp kiểm vùng (`Regions`) tạm bỏ chọn để thấy rõ nền Occupancy Grid gốc:

```bash
cd "$REPO_ROOT"
ros2 run tb4_voice_control map_editor maps/map.yaml
```

- **Bằng chứng cần thấy trong ảnh:** Toàn bộ bản đồ xám `788 x 1101` px thể hiện rõ vùng không gian tự do (màu sáng), tường/kệ hàng (màu đen) và vùng chưa biết (màu xám), kèm thanh trạng thái Pixel/ROS hoặc cửa sổ terminal hiển thị nội dung `maps/map.yaml`.

---

## 2. Ảnh giao diện Map Editor sau khi chỉnh sửa, lưu và tải lại (`02_map_editor_ui.png`)

- **Tên file bắt buộc:** `02_map_editor_ui.png`
- **Cách thực hiện:**
  Đóng Map Editor sau khi chụp ảnh 01, rồi mở cấu hình vùng:

```bash
ros2 run tb4_voice_control map_editor config/regions.yaml
```

  1. Chọn một vùng (ví dụ `Khu vực B (zone_b)`), thử kéo nhẹ một đỉnh hoặc đặt lại goal hợp lệ, nhấn **Save** (`Ctrl+S`), đóng cửa sổ rồi chạy lại lệnh trên để mở lại `config/regions.yaml`.
  2. Nhấp chọn `Khu vực B (zone_b)` để bảng thuộc tính bên phải hiện rõ `ID: zone_b`, `Name: Khu vực B`, `Aliases: B, khu B, khu vực B, phòng thí nghiệm`, `RGB color: 52, 168, 83`.
- **Bằng chứng cần thấy trong ảnh:**
  - Khung bản đồ hiển thị đủ 3 vùng tô màu (`Khu vực A`, `Khu vực B`, `Khu vực C`), các nút tròn đỉnh đa giác và mũi tên hướng đích;
  - Danh sách `Regions` có đủ 3 vùng được tích chọn;
  - Khung `Validation` trống hoàn toàn (không có lỗi) và nút `Save` / `Export Image` đang sáng;
  - Thanh trạng thái dưới đáy hiển thị tọa độ `Pixel: ... ROS: ... m`.

---

## 3. Ảnh giao diện Voice Control UI ở trạng thái sẵn sàng (`03_voice_control_ui.png`)

- **Tên file bắt buộc:** `03_voice_control_ui.png`
- **Cách thực hiện:**
  Sau khi chụp ảnh 02 và đóng Map Editor, chạy một phiên tích hợp duy nhất trong terminal đã chuẩn bị. Kịch bản thiết lập môi trường speech chỉ chuẩn bị phụ thuộc, không mở Voice UI. Nhập khóa qua lời nhắc ẩn, rồi khởi chạy:

```bash
cd "$REPO_ROOT"
./scripts/setup_speech_venv.sh
read -rsp 'GEMINI_API_KEY: ' GEMINI_API_KEY
export GEMINI_API_KEY
clear
ros2 launch tb4_voice_control voice_navigation.launch.py \
  start_nav2:=true start_voice_ui:=true \
  regions_file:="$REPO_ROOT/config/regions.yaml"
```

  Lệnh tích hợp mở Gazebo, Nav2, RViz2 và một Voice UI. Trong RViz2, thực hiện undock (nếu cần), đặt **2D Pose Estimate** khớp vị trí robot và chờ AMCL + `bt_navigator` active trước khi gửi lệnh. Không mở thêm Voice UI hoặc chạy lại launch ở các mục sau. Chỉ chụp trạng thái sẵn sàng sau khi hệ thống đã khởi động.

- **Bằng chứng cần thấy trong ảnh:**
  - Cửa sổ `TurtleBot 4 — Điều hướng bằng giọng nói`;
  - Nhãn `Nhận dạng: Gemini API — gemini-3.5-transcribe`;
  - Nhãn `Khu vực hợp lệ: Khu vực A, Khu vực B, Khu vực C`;
  - Nút `Giữ để nói` đang bật, nút `Hủy lộ trình` đang khóa (khi chưa chạy), ô nhập văn bản và nút `Gửi lệnh văn bản`.

---

## 4. Ảnh thực thi câu lệnh giọng nói 1: “Đi đến khu vực A” (`04_voice_command_zone_a.png`)

- **Tên file bắt buộc:** `04_voice_command_zone_a.png`
- **Cách thực hiện:**
  1. Dùng lại Voice UI cùng mô phỏng/Nav2 đang chạy từ ảnh 03.
  2. Nhấn giữ nút **Giữ để nói**, đọc rõ: **“Đi đến khu vực A”**, sau đó thả nút.
  3. Chờ Gemini trả transcript và robot di chuyển tới đích `zone_a` ($x \approx -3.38\,\text{m}, y \approx -0.41\,\text{m}$).
- **Bằng chứng cần thấy trong ảnh:**
  - Cửa sổ Voice Control UI hiển thị `Transcript: Đi đến khu vực A`, `Intent: GO_TO — đi đến Khu vực A`, `Hàng đợi: Khu vực A`, `Chặng hiện tại: 1/1: Khu vực A` và `Kết quả: Điều hướng thành công`;
  - Đặt cạnh cửa sổ RViz2/Gazebo cho thấy robot đã dừng tại `Khu vực A`.

---

## 5. Ảnh thực thi câu lệnh giọng nói 2 (alias): “Đi đến phòng thí nghiệm” (`05_voice_command_alias_lab.png`)

- **Tên file bắt buộc:** `05_voice_command_alias_lab.png`
- **Cách thực hiện:**
  Nhấn giữ nút **Giữ để nói**, đọc rõ: **“Đi đến phòng thí nghiệm”**, sau đó thả nút.
- **Bằng chứng cần thấy trong ảnh:**
  - Cửa sổ Voice Control UI hiển thị `Transcript: Đi đến phòng thí nghiệm`;
  - Trường `Intent` hiển thị `GO_TO — đi đến Khu vực B` (chứng minh alias `phòng thí nghiệm` đã được phân giải thành `zone_b`);
  - Trường `Kết quả` hiển thị `Điều hướng thành công` kèm hình RViz2/Gazebo cho thấy robot đã đến `Khu vực B` ($x \approx 2.35\,\text{m}, y \approx 2.36\,\text{m}$).

---

## 6. Ảnh xử lý câu lệnh có vùng không tồn tại (`06_invalid_region_handling.png`)

- **Tên file bắt buộc:** `06_invalid_region_handling.png`
- **Cách thực hiện:**
  Nhấn giữ nút **Giữ để nói** và nói **“Đi đến khu vực Z”** (hoặc **“Đi đến phòng họp”**), hoặc nhập câu đó vào ô văn bản để kiểm tra.
- **Bằng chứng cần thấy trong ảnh:**
  - Giao diện Voice Control UI hiển thị `Kết quả: Có lỗi — chưa gửi thêm goal`;
  - Dòng `Lỗi` màu đỏ hiển thị `[unknown_region] Unknown destination: ... Khu vực hợp lệ: Khu vực A, Khu vực B, Khu vực C.`;
  - Cửa sổ RViz2 / log terminal bên cạnh xác nhận robot đứng yên và không có goal `NavigateToPose` mới nào được gửi.

---

## 7. Ảnh RViz2 và Gazebo trong quá trình điều hướng đơn chặng (`07_rviz_single_route.png`)

- **Tên file bắt buộc:** `07_rviz_single_route.png`
- **Cách thực hiện:**
  Khi robot đang di chuyển thực hiện một lệnh `GO_TO` (ví dụ từ `Khu vực B` về `Khu vực A` hoặc sang `Khu vực C`), chụp màn hình khi đường đi toàn cục (`global path`) đang hiển thị rõ trên RViz2.
- **Bằng chứng cần thấy trong ảnh:**
  - Cửa sổ RViz2 hiển thị bản đồ `/map`, đám mây hạt AMCL hội tụ quanh robot, đường quy hoạch toàn cục (`global path`), bản đồ chi phí (`global/local costmap`) và mô hình robot đang bám đường;
  - Cửa sổ Gazebo hoặc Voice Control UI hiển thị trạng thái `Robot đang di chuyển` kèm khoảng cách còn lại (`còn ... m — ... s`).

---

## 8. Ảnh lộ trình đa chặng (`FROM_TO`), khóa lệnh mới và hủy lộ trình (`08_multi_leg_route_and_cancel.png`)

- **Tên file bắt buộc:** `08_multi_leg_route_and_cancel.png`
- **Cách thực hiện:**
  1. Đưa robot ra ngoài `Khu vực A` (ví dụ đang đứng ở `Khu vực C`).
  2. Nói câu lệnh thứ ba: **“Di chuyển từ khu vực A đến khu vực B”**.
  3. Quan sát trên Voice Control UI: `Intent: FROM_TO — từ Khu vực A đến Khu vực B`, `Hàng đợi: Khu vực A → Khu vực B`, `Chặng hiện tại: 1/2: Khu vực A` rồi tự động chuyển sang `2/2: Khu vực B`, đồng thời nút `Giữ để nói` và `Gửi lệnh văn bản` bị khóa mở mờ (`disabled`), nút `Hủy lộ trình` sáng.
  4. Thực hiện thêm lượt kiểm tra khi robot đang ở sẵn trong `Khu vực A` (chỉ sinh 1 chặng `Khu vực B`) và một lượt nhấn **Hủy lộ trình** để thấy trạng thái `Đã hủy lộ trình`.
- **Bằng chứng cần thấy trong ảnh:**
  - Giao diện Voice Control UI thể hiện rõ `Intent: FROM_TO — từ Khu vực A đến Khu vực B`, hàng đợi lộ trình đa chặng (`Khu vực A → Khu vực B`), trạng thái khóa các nút nhập lệnh mới hoặc trạng thái sau khi nhấn `Hủy lộ trình`.

---

## 9. Ảnh Nav2 tái lập đường đi và tránh vật cản (`09_obstacle_avoidance.png`)

- **Tên file bắt buộc:** `09_obstacle_avoidance.png`
- **Cách thực hiện:**
  1. Trong Ignition Gazebo, chèn một vật cản (ví dụ hình hộp `Box` hoặc `Cylinder`) chắn ngang hành lang trên lộ trình từ vùng hiện tại tới vùng đích.
  2. Gửi lệnh giọng nói điều hướng qua hành lang đó.
  3. Khi LiDAR `/scan` quét thấy vật cản, chụp màn hình lúc Nav2 cập nhật `local costmap` và vẽ lại đường đi vòng qua vật cản.
- **Bằng chứng cần thấy trong ảnh:**
  - Cửa sổ Gazebo có vật cản mới đặt trên đường đi;
  - Cửa sổ RViz2 hiển thị vùng inflation/occupied mới trên costmap và đường đi mới của robot vòng qua vật cản mà không va chạm.

---

## 10. Kiểm tra danh sách ảnh và biên dịch lại báo cáo

Sau khi lưu các ảnh vào `$REPORT_DIR/images/`, kiểm tra bằng lệnh:

```bash
find "$REPORT_DIR/images" -maxdepth 1 -type f -name '*.png' -printf '%f\n' | sort
```

Danh sách đầy đủ gồm 10 file `.png` (`segmented_map.png` có sẵn + 9 ảnh chụp mới `01_...` đến `09_...`). Sau đó biên dịch lại `main.tex` 2 lần để toàn bộ ảnh tự động hiển thị trong PDF.
