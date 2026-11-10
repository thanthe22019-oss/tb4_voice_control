# Danh sách ảnh minh họa báo cáo Bài thực hành 7 (`images/`)

Thư mục này chứa ảnh xuất đã xác minh từ repository và vị trí lưu các ảnh chụp màn hình khi chạy nghiệm thu thực tế. Khi một file ảnh chưa tồn tại, macro `\reportfigure` trong `preamble.tex` sẽ tự động tạo khung giữ chỗ (placeholder) hợp lệ khi biên dịch LaTeX.

## 1. Ảnh đã có sẵn từ repository (Verified Artifact)

- `segmented_map.png`: Bản sao trực tiếp từ `artifacts/segmented_map.png` (kích thước `788 x 1101` px, xuất tự động bởi `ros2 run tb4_voice_control render_segmented_map config/regions.yaml artifacts/segmented_map.png`). Thể hiện 3 vùng ngữ nghĩa (`Khu vực A`, `Khu vực B`, `Khu vực C`) cùng nhãn tiếng Việt và mũi tên hướng đích (yaw) trên nền bản đồ `maps/map.pgm`.

## 2. Ảnh chụp màn hình đã bổ sung ngày 10/11/2026

Chín file PNG dưới đây đã được người thực hiện đưa vào thư mục `images/`. Chúng được kiểm tra trực quan trước khi chèn vào báo cáo. Tên file được giữ theo checklist ban đầu; phần mô tả dưới đây ghi đúng nội dung thực tế của từng ảnh và giới hạn bằng chứng:

1. `01_original_occupancy_map.png`
   - **Nội dung:** Map Editor mở bản đồ Occupancy Grid gốc trước khi có lớp phủ phân vùng.
2. `02_map_editor_ui.png`
   - **Nội dung:** Map Editor tải `config/regions.yaml` và hiển thị đủ ba vùng, goal và thanh tọa độ Pixel/ROS. Ảnh tĩnh không tự chứng minh toàn bộ chu trình lưu--đóng--mở lại nên tiêu chí đó vẫn cần xác nhận riêng.
3. `03_voice_control_ui.png`
   - **Nội dung:** Voice Control UI hiển thị model Gemini, ba vùng và các nút điều khiển trong lúc đang chờ localization/action server; không để lộ API key.
4. `04_voice_command_zone_a.png`
   - **Nội dung thực tế:** Lệnh `FROM_TO` từ Khu vực A đến Khu vực B đang chạy một chặng tới B. Do tên file được đặt trước khi rà soát, LaTeX sử dụng ảnh này cho minh chứng `FROM_TO`, không dùng làm bằng chứng đi đến A.
5. `05_voice_command_alias_lab.png`
   - **Nội dung:** Transcript “đi đến phòng thí nghiệm” được phân giải thành `GO_TO` Khu vực B và UI báo điều hướng thành công.
6. `06_invalid_region_handling.png`
   - **Nội dung:** UI hiển thị lỗi `[unknown_region]` cho “phòng họp”, liệt kê ba vùng hợp lệ và báo chưa gửi thêm goal.
7. `07_rviz_single_route.png`
   - **Nội dung thực tế:** Transcript “Di chuyển đến khu vực A”, intent `GO_TO`, hàng đợi một chặng và trạng thái robot đang di chuyển; LaTeX sử dụng ảnh này cho câu lệnh đi đến A.
8. `08_multi_leg_route_and_cancel.png`
   - **Nội dung:** UI hiển thị hàng đợi `Khu vực A → Khu vực B`, chặng `2/2` và trạng thái “Đã hủy lộ trình”. Cửa sổ quản lý file che một phần nền; nên chụp lại sạch hơn nếu dùng cho bản nộp cuối.
9. `09_obstacle_avoidance.png`
   - **Nội dung:** Gazebo có vật cản hình hộp trước robot; RViz2 hiển thị costmap và quỹ đạo trong lúc robot đang di chuyển. Ảnh tĩnh chưa chứng minh robot đã hoàn tất vòng tránh nên kết quả end-to-end vẫn để `\pending`.

Xem hướng dẫn chi tiết từng bước chụp tại `../HUONG_DAN_CHUP_ANH.md`.
