# Ma trận kiểm thử và nghiệm thu

Trạng thái dùng hai nhóm tách biệt:

- `AUTOMATED PASS`: được chứng minh bằng pytest/colcon trên checkout hiện tại;
- `MANUAL/HARDWARE PENDING`: chưa có bằng chứng runtime, không được suy ra từ test giả.

## Kiểm thử tự động

| Hạng mục | Bằng chứng | Trạng thái |
|---|---|---|
| Geometry, vùng, parser, executor, UI offscreen | `pytest -q`: 227 pass, 1 skip | AUTOMATED PASS (2026-11-03) |
| Build và ament tests | 1 package built; 228 tests, 0 error/failure, 1 skip | AUTOMATED PASS (2026-11-03) |
| Installed assets + sáu entry point | manifest + installed share inspection | AUTOMATED PASS (2026-11-03) |
| CLI vùng/ảnh/voice help | 6/6 `--help`; validation + render | AUTOMATED PASS (2026-11-03) |

## Nghiệm thu phần cứng và simulation

| # | Kịch bản | Bằng chứng bắt buộc | Trạng thái hiện tại |
|---:|---|---|---|
| 1 | Editor sửa/lưu/reload 3 vùng | screenshot + YAML/ảnh xuất | MANUAL/HARDWARE PENDING |
| 2 | “Đi đến khu vực A” tới A | transcript + Nav2 result + RViz | MANUAL/HARDWARE PENDING |
| 3 | “Đi đến phòng thí nghiệm” tới vùng alias | transcript + result | MANUAL/HARDWARE PENDING |
| 4 | FROM_TO ngoài A đi A rồi B | log hai chặng + RViz | MANUAL/HARDWARE PENDING |
| 5 | FROM_TO khi ở A chỉ đi B | log đúng một chặng | MANUAL/HARDWARE PENDING |
| 6 | Vùng không tồn tại không gửi goal | UI error + action log | MANUAL/HARDWARE PENDING |
| 7 | Khóa lệnh mới và Cancel dừng route | video/UI + cancel result | MANUAL/HARDWARE PENDING |
| 8 | Nav2 tránh vật cản | RViz/path + video | MANUAL/HARDWARE PENDING |
| 9 | Whisper `small` CUDA/float16 nhận 3 câu | `nvidia-smi` + model log + transcript | MANUAL/HARDWARE PENDING — driver không hoạt động |
| 10 | Micro push-to-talk | device list + ba lần thu | MANUAL/HARDWARE PENDING — không thấy soundcard |
| 11 | GitHub public + video | URL public/release | MANUAL/HARDWARE PENDING — auth/network |

Báo cáo học thuật HTML/PDF: **DEFERRED / OUT OF CURRENT SCOPE** do yêu cầu nội
dung đã thay đổi; không được suy diễn là đã hoàn tất từ các test runtime.

Chi tiết môi trường hiện tại và quy tắc bổ sung evidence ở `evidence/README.md`.
