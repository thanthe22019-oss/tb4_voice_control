# Danh sách ảnh minh họa báo cáo Bài thực hành 7 (`images/`)

Thư mục này chứa ảnh xuất đã xác minh từ repository và vị trí lưu các ảnh chụp màn hình khi chạy nghiệm thu thực tế. Khi một file ảnh chưa tồn tại, macro `\reportfigure` trong `preamble.tex` sẽ tự động tạo khung giữ chỗ (placeholder) hợp lệ khi biên dịch LaTeX.

## 1. Ảnh đã có sẵn từ repository (Verified Artifact)

- `segmented_map.png`: Bản sao trực tiếp từ `artifacts/segmented_map.png` (kích thước `788 x 1101` px, xuất tự động bởi `ros2 run tb4_voice_control render_segmented_map config/regions.yaml artifacts/segmented_map.png`). Thể hiện 3 vùng ngữ nghĩa (`Khu vực A`, `Khu vực B`, `Khu vực C`) cùng nhãn tiếng Việt và mũi tên hướng đích (yaw) trên nền bản đồ `maps/map.pgm`.

## 2. Ảnh cần chụp bổ sung khi chạy thực tế (`\pending`)

Lưu đúng tên file PNG dưới đây vào thư mục `images/` và biên dịch lại `main.tex`:

1. `01_original_occupancy_map.png`
   - **Bằng chứng cần chụp:** Bản đồ Occupancy Grid gốc (`maps/map.pgm` kèm thông số `maps/map.yaml`) hiển thị trong trình xem ảnh, RViz2 hoặc Map Editor trước khi bật lớp phủ phân vùng.
2. `02_map_editor_ui.png`
   - **Bằng chứng cần chụp:** Giao diện `map_editor` sau khi chỉnh sửa một đỉnh/goal, lưu, đóng và mở lại `config/regions.yaml`, hiển thị đủ 3 vùng (`Khu vực A`, `Khu vực B`, `Khu vực C`), bảng thuộc tính, thanh tọa độ Pixel/ROS và danh sách Validation không có lỗi.
3. `03_voice_control_ui.png`
   - **Bằng chứng cần chụp:** Giao diện `VoiceControlWindow` (`./scripts/run_voice_control.sh`) ở trạng thái sẵn sàng, hiển thị `Gemini API — gemini-3.5-transcribe`, danh sách khu vực hợp lệ (`Khu vực A, Khu vực B, Khu vực C`), nút `Giữ để nói`, `Hủy lộ trình` và ô nhập văn bản. Không để lộ `GEMINI_API_KEY`.
4. `04_voice_command_zone_a.png`
   - **Bằng chứng cần chụp:** Nhận dạng và thực thi câu lệnh giọng nói “Đi đến khu vực A”: hiển thị transcript trên UI, `Intent: GO_TO — đi đến Khu vực A`, tiến độ/kết quả điều hướng và vị trí robot tại `Khu vực A` trên RViz2/Gazebo.
5. `05_voice_command_alias_lab.png`
   - **Bằng chứng cần chụp:** Nhận dạng và thực thi câu lệnh giọng nói “Đi đến phòng thí nghiệm”: hiển thị transcript, alias `phòng thí nghiệm` được phân giải thành `Khu vực B` (`zone_b`), và robot dừng tại đích `Khu vực B` trên RViz2/Gazebo.
6. `06_invalid_region_handling.png`
   - **Bằng chứng cần chụp:** Xử lý câu lệnh có vùng không tồn tại (ví dụ “Đi đến khu vực Z”): hiển thị lỗi `[unknown_region]` kèm danh sách khu vực hợp lệ trên UI, trạng thái `Có lỗi — chưa gửi thêm goal`, và xác nhận không có goal `NavigateToPose` nào được gửi tới Nav2.
7. `07_rviz_single_route.png`
   - **Bằng chứng cần chụp:** RViz2 và Gazebo khi thực hiện lộ trình đơn chặng: thấy rõ bản đồ, đám mây hạt AMCL hội tụ, đường quy hoạch toàn cục (global path), local/global costmap và mô hình robot đang di chuyển.
8. `08_multi_leg_route_and_cancel.png`
   - **Bằng chứng cần chụp:** Thực thi lệnh đa chặng “Di chuyển từ khu vực A đến khu vực B” (`FROM_TO`): hiển thị hàng đợi `Khu vực A → Khu vực B` (khi xuất phát ngoài A) hoặc rút gọn 1 chặng (khi đang ở A), các nút gửi lệnh mới bị khóa khi đang chạy, và kết quả dừng lộ trình khi nhấn `Hủy lộ trình`.
9. `09_obstacle_avoidance.png`
   - **Bằng chứng cần chụp:** Cảnh Gazebo có vật cản đặt trên đường đi và RViz2 hiển thị local costmap cập nhật từ `/scan` cùng quỹ đạo Nav2 tái lập vòng qua vật cản an toàn.

Xem hướng dẫn chi tiết từng bước chụp tại `../HUONG_DAN_CHUP_ANH.md`.
