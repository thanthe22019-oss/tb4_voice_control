# Kịch bản demo Bài thực hành 7

Tài liệu này là checklist quay video, không thay thế bằng chứng runtime. Không
commit file ghi âm riêng tư hoặc video dung lượng lớn; đăng video bằng liên kết
ngoài repository khi hoàn tất.

## Chuẩn bị

1. Chạy `nvidia-smi`, `arecord -l` và lưu màn hình kết quả.
2. Source ROS/workspace, mở `voice_navigation.launch.py` đúng một lần.
3. Undock robot, đặt initial pose trong RViz, chờ AMCL/Nav2 active.
4. Mở `config/regions.yaml` bằng Map Editor, chỉ ra ba vùng và ba goal.
5. Đảm bảo UI báo `CUDA — small (float16)`; model đã tải trước khi quay.

## Shot list

- Sửa một đỉnh/goal, lưu, đóng rồi tải lại; xuất `segmented_map.png`.
- Giữ nút và nói “Đi đến khu vực A”; quay transcript, route và robot đến A.
- Nói “Đi đến phòng thí nghiệm”; quay alias được resolve và robot đến B.
- Từ ngoài A nói “Di chuyển từ khu vực A đến khu vực B”; quay đủ A → B.
- Khi robot đang ở A, lặp FROM_TO và chứng minh chỉ gửi B.
- Nhập/nói vùng không tồn tại; quay lỗi và chứng minh không có goal mới.
- Trong một route, chứng minh nút lệnh mới bị khóa rồi bấm Hủy.
- Đặt vật cản simulation và quay Nav2 replanning/tránh vật cản.

## File bằng chứng cần bổ sung sau khi chạy thật

- ảnh Map Editor sau reload;
- ảnh GPU/model và transcript của ba câu;
- ảnh/terminal Nav2 cho từng route, cancel và invalid-region;
- ảnh RViz thể hiện vật cản/đường tái lập;
- liên kết video cuối cùng trong README hoặc release.

Đổi trạng thái trong `TEST_MATRIX.md` chỉ khi bằng chứng tương ứng đã tồn tại.
