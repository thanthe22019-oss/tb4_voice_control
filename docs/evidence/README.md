# Evidence index

Thư mục này chỉ chứa log công khai, không chứa audio riêng tư, model Whisper,
screenshot hoặc video. Audit phần cứng: **2026-11-02, Asia/Ho_Chi_Minh**;
proof tự động: **2026-11-03**.

## Audit môi trường hiện tại

| Thành phần | Kết quả | Phân loại |
|---|---|---|
| ROS 2/TurtleBot 4/Nav2 packages | Package có mặt; runtime chưa chạy | MANUAL PENDING |
| NVIDIA | `nvidia-smi` exit 9, driver không giao tiếp được | HARDWARE BLOCKED |
| Microphone | `arecord -l`: không có soundcard | HARDWARE BLOCKED |
| Display | `DISPLAY=:1`; Qt offscreen test dùng được | GUI runtime chưa xác minh |
| GitHub | `gh` auth không hợp lệ, không có remote | EXTERNAL BLOCKED |

Thông báo NVIDIA quan sát được:

```text
NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver.
Make sure that the latest NVIDIA driver is installed and running.
```

Không có screenshot/log giả được tạo để lấp các mục blocked. Sau khi phần cứng
sẵn sàng, thêm file theo mẫu `YYYYMMDD-HHMM-<scenario>.log|png`, bỏ thông tin
nhạy cảm, cập nhật `../TEST_MATRIX.md`, rồi chạy lại toàn bộ proof.

## Bằng chứng tự động

Kết quả đã chạy nằm trong [`automated-proof-2026-11-03.txt`](automated-proof-2026-11-03.txt):
pytest, colcon build/test/test-result, installed layout, sáu entry point, CLI
validation/render và launch no-op không khởi động Nav2/UI.

Báo cáo học thuật HTML/PDF được hoãn vì yêu cầu nội dung thay đổi; nó không phải
artifact hoặc acceptance gate của lần đóng gói runtime này.
