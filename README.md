# tb4_voice_control

`tb4_voice_control` là gói ROS 2 Humble cho TurtleBot 4 Simulation, kết hợp
trình phân vùng bản đồ thủ công, nhận dạng tiếng Việt qua Gemini API và điều
hướng semantic qua Nav2. Bản đồ occupancy gốc không
bị thay đổi; polygon, tên/alias và goal được lưu riêng trong
`config/regions.yaml`.

## Điều kiện tiên quyết

- Ubuntu 22.04, ROS 2 Humble, `colcon`, Nav2 và TurtleBot 4 Simulator;
- Python 3.10 với PyQt5, OpenCV, NumPy, Pillow và PyYAML từ Ubuntu/ROS;
- micro đầu vào cho push-to-talk;
- Internet, Gemini API key có giới hạn quyền và quota khả dụng.

Kiểm tra môi trường trước khi demo:

```bash
source /opt/ros/humble/setup.bash
arecord -l
ros2 pkg prefix turtlebot4_ignition_bringup
ros2 pkg prefix nav2_bringup
```

## Build và kiểm thử

```bash
source /opt/ros/humble/setup.bash
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM=offscreen  # chỉ cần cho test Qt không có màn hình
pytest -q
colcon build --base-paths . --packages-select tb4_voice_control --symlink-install
colcon test --base-paths . --packages-select tb4_voice_control \
  --event-handlers console_direct+
colcon test-result --verbose
source install/setup.bash
```

Luôn source `/opt/ros/humble/setup.bash` rồi `install/setup.bash` trong terminal
mới. Dùng cùng `ROS_DOMAIN_ID` và `RMW_IMPLEMENTATION` ở mọi terminal.

## Map Editor

Mở editor bằng file vùng mẫu hoặc trực tiếp bằng `map.yaml`:

```bash
ros2 run tb4_voice_control map_editor config/regions.yaml
# hoặc
ros2 run tb4_voice_control map_editor maps/map.yaml
```

Vẽ polygon bằng click, Enter để đóng; chọn/kéo đỉnh để chỉnh; đặt goal và hướng
yaw trên canvas. Editor kiểm tra polygon tự cắt/chồng lấn, alias trùng, goal
ngoài vùng hoặc trên ô không free trước khi lưu. Xuất ảnh nộp bài bằng:

```bash
ros2 run tb4_voice_control render_segmented_map \
  config/regions.yaml artifacts/segmented_map.png
ros2 run tb4_voice_control validate_regions config/regions.yaml
```

## Thiết lập nhận dạng Gemini API

Speech dependency được cách ly trong `.venv-speech`, không đưa vào rosdep:

```bash
./scripts/setup_speech_venv.sh
export GEMINI_API_KEY='YOUR_RESTRICTED_KEY'
source install/setup.bash
./scripts/run_voice_control.sh --help
./scripts/run_voice_control.sh
```

Script in phiên bản `google-genai`, `numpy`, `sounddevice`, thiết bị micro và
chỉ trạng thái có/không có key. Key chỉ export trong shell hiện tại; không ghi
key vào repository hoặc chia sẻ trong chat. Âm thanh micro được gửi tới Google;
cần Internet và quota cho mỗi lần nhận dạng. Cấu hình mặc định dùng
`gemini-3.8-flash`, tiếng Việt, mono 16 kHz và tối đa 15 giây. `numpy<2` giữ
tương thích ABI với OpenCV/ROS. `--help` hoặc mở UI chưa chứng minh nhận dạng.

Để dọn dependency cũ, tự đổi tên `.venv-speech` rồi chạy lại setup để tạo venv
mới; sau khi xác nhận venv mới hoạt động, tự xóa bản cũ nếu muốn. Setup không
tự gỡ package bổ sung. Không commit venv hoặc bản ghi âm.

## Khởi động Nav2

Một lệnh có thể mở simulator/Nav2 warehouse và Voice Runtime UI:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 launch tb4_voice_control voice_navigation.launch.py
```

Nếu simulator/Nav2 đã chạy ở terminal khác, tránh khởi động bản thứ hai:

```bash
ros2 launch tb4_voice_control voice_navigation.launch.py \
  start_nav2:=false start_voice_ui:=true use_sim_time:=true
```

Chỉ chạy Nav2 để kiểm tra baseline:

```bash
ros2 launch tb4_voice_control voice_navigation.launch.py \
  start_nav2:=true start_voice_ui:=false
```

Các argument khác gồm `world`, `map`, `rviz`, `regions_file` và
`voice_config`. Với robot thật/Nav2 dùng wall clock, đặt `start_nav2:=false
use_sim_time:=false`. Sau khi simulation mở: undock, đặt **2D Pose Estimate**
đúng trong RViz và chờ AMCL cùng `bt_navigator` active.

## Demo bằng giọng nói

Giữ nút **Giữ để nói**, nói rồi thả. Ba lệnh bắt buộc:

- “Đi đến khu vực A.”
- “Đi đến phòng thí nghiệm.”
- “Di chuyển từ khu vực A đến khu vực B.”

UI hiển thị transcript, intent, lộ trình, chặng và feedback Nav2. Khi đang đi,
nút nói và nhập text bị khóa; **Hủy lộ trình** dừng chuỗi hiện tại. Nhập text
vẫn dùng được để tách lỗi parser khỏi lỗi micro/Gemini. Quy trình quay và danh
sách cảnh cần lưu nằm ở [docs/DEMO.md](docs/DEMO.md); trạng thái bằng chứng nằm
ở [docs/TEST_MATRIX.md](docs/TEST_MATRIX.md).

## Xử lý lỗi

| Triệu chứng | Kiểm tra / khắc phục |
|---|---|
| Gemini lỗi hoặc không nhận dạng | Kiểm tra key đã export trong shell, Internet và quota; không chia sẻ giá trị key. |
| Không có input device | Chạy `arecord -l`, kiểm tra quyền/thiết bị; vẫn dùng ô nhập text để test parser/Nav2. |
| Thiếu `.venv-speech` | Chạy `./scripts/setup_speech_venv.sh`; không cài speech package vào Python ROS hệ thống. |
| Wrapper không tìm thấy workspace | Chạy từ workspace colcon chuẩn, hoặc đặt `TB4_VOICE_CONTROL_ROOT=/đường/dẫn/repo`. |
| Nav2 chưa sẵn sàng | Undock, đặt initial pose, kiểm tra `ros2 lifecycle get /bt_navigator` và `/navigate_to_pose`. |
| Vùng không tồn tại/mơ hồ | Kiểm tra tên hợp lệ trên UI và alias trong `regions.yaml`; không goal nào được gửi. |
| Map/vùng không hợp lệ | Chạy `validate_regions`; giữ `map.yaml` và `map.pgm` cạnh nhau. |
| UI không mở | Kiểm tra `DISPLAY`, PyQt5; chỉ đặt `QT_QPA_PLATFORM=offscreen` khi chạy test tự động. |

## Cấu trúc repository

```text
artifacts/                 segmented_map.png
config/                    regions.yaml, voice.yaml, goals.yaml
docs/                      hướng dẫn demo, test matrix và evidence công khai
launch/                    Nav2/SLAM baseline và voice_navigation.launch.py
maps/                      Occupancy Grid gốc (.yaml + .pgm)
scripts/                   tạo speech venv và chạy Voice Runtime UI
tb4_voice_control/         geometry, editor, parser, speech, runtime, Nav2
test/                      kiểm thử pytest/ament không cần GPU hay micro
```

## Trạng thái bàn giao

Kiểm thử tự động và các artifact cục bộ được lưu kèm mã nguồn. Kiểm thử Gemini
với key thật, micro, TurtleBot 4 Simulation end-to-end, video và GitHub public chỉ
được đánh dấu đạt sau khi chạy trên đúng phần cứng/dịch vụ; xem test matrix để
phân biệt rõ `AUTOMATED PASS` và `MANUAL/HARDWARE PENDING`. Báo cáo học thuật
HTML/PDF đang được hoãn vì yêu cầu nội dung đã thay đổi và không thuộc phạm vi
đóng gói runtime hiện tại.

Mã nguồn này được tách từ baseline `tb4_nav2` tại commit
`3625002e8059ae84ce604ee4039ae7b0cb3c22bd`; repository gốc không bị sửa.
Giấy phép Apache-2.0 nằm trong `LICENSE`.
