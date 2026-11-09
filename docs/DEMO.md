# Kịch bản demo Bài thực hành 7

Tài liệu này là checklist quay video, không thay thế bằng chứng runtime. Không
commit file ghi âm riêng tư hoặc video dung lượng lớn; đăng video bằng liên kết
ngoài repository khi hoàn tất.

## Chuẩn bị

1. Chạy `arecord -l`, kiểm tra Internet/quota và export Gemini API key giới hạn quyền trong shell; không lưu key trong evidence.
2. Tạo `.venv-speech` bằng `scripts/setup_speech_venv.sh`, source ROS/workspace, mở UI qua `scripts/run_voice_control.sh` và Nav2 đúng một lần.
3. Undock robot, đặt initial pose trong RViz, chờ AMCL/Nav2 active.
4. Mở `config/regions.yaml` bằng Map Editor, chỉ ra ba vùng và ba goal.
5. Nhận biết âm thanh micro được gửi tới Google; kiểm tra transcript thật trước khi quay.

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
- transcript và độ trễ yêu cầu Gemini của ba câu, không có key;
- ảnh/terminal Nav2 cho từng route, cancel và invalid-region;
- ảnh RViz thể hiện vật cản/đường tái lập;
- liên kết video cuối cùng trong README hoặc release.

Đổi trạng thái trong `TEST_MATRIX.md` chỉ khi bằng chứng tương ứng đã tồn tại.
