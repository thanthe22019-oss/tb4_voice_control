# Hướng dẫn sử dụng và hoàn thiện gói báo cáo Bài thực hành 7 (`Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730`)

Thư mục này chứa mã nguồn LaTeX hoàn chỉnh cho báo cáo học thuật dài của **Bài thực hành 7** (MSSV: `23020730`), tuân thủ phong cách trình bày UET/TurtleBot 4 của các bài thực hành trước.

## 1. Cấu trúc thư mục báo cáo

- `main.tex`: File gốc điều phối toàn bộ báo cáo.
- `preamble.tex`: Khai báo các gói LaTeX, phông tiếng Việt T5, môi trường mã `svcode`, macro `\pending` và macro `\reportfigure`.
- `references.bib`: Bản xuất tài liệu tham khảo tùy chọn ở định dạng BibTeX, không được `main.tex` nạp và không cần chạy BibTeX. Danh sách đánh số trong `content/09-ket-luan-tai-lieu-tham-khao.tex` là danh mục chính thức xuất hiện trong PDF; cập nhật danh sách đó khi thay đổi tài liệu tham khảo.
- `Logo_UET.png`: Logo Trường Đại học Công nghệ — ĐHQGHN dùng cho trang bìa.
- `content/`:
  - `00-frontmatter.tex`: Trang bìa báo cáo.
  - `01-muc-tieu-kien-truc.tex`: Mục tiêu bài thực hành, kiến trúc tổng thể, cấu trúc repository, bảng mô-đun và giao diện ROS 2.
  - `02-phan-vung-map-editor.tex`: Cơ sở thiết kế phân vùng thủ công/bán tự động bằng đa giác và quy trình Map Editor UI.
  - `03-ban-do-ngu-nghia-toa-do.tex`: Thông số `maps/map.yaml` (`788 x 1101` px), công thức chuyển đổi tọa độ Pixel--ROS và bảng 3 vùng thực tế từ `config/regions.yaml` kèm ảnh `segmented_map.png`.
  - `04-nhan-dang-giong-noi-gemini.tex`: Lý do loại bỏ suy luận cục bộ NVIDIA/CUDA, kiến trúc Gemini-only (`gemini-3.5-transcribe`), thu âm push-to-talk mono 16 kHz WAV, bảo mật `GEMINI_API_KEY`, giải mã `audio_transcription.text` và bảng phân loại lỗi.
  - `05-phan-tich-lenh-dieu-huong-nav2.tex`: Ngữ pháp `GO_TO`/`FROM_TO`, chuẩn hóa tiếng Việt, khớp alias dài nhất, từ chối vùng không tồn tại, lập lộ trình đa chặng, khóa lệnh mới, hủy lộ trình và trạng thái `CLEANING` trên Nav2.
  - `06-cai-dat-van-hanh-kiem-thu.tex`: Quy trình cài đặt, biên dịch `colcon`, kiểm thử `pytest`/SDK, chạy Map Editor và khởi chạy mô phỏng/Nav2/Voice UI.
  - `07-ket-qua-kiem-thu-tu-dong.tex`: Kết quả kiểm thử tự động đã xác minh (`317 passed, 12 skipped, 2 warnings`, `11 passed` SDK acceptance, `329` colcon tests) và giải trình giới hạn của bằng chứng chẩn đoán 3,2 giây.
  - `08-nghiem-thu-thuc-te-minh-chung.tex`: Bảng nghiệm thu thực tế (`\pending`), 6 khung ảnh minh chứng runtime và liên kết bàn giao.
  - `09-ket-luan-tai-lieu-tham-khao.tex`: Kết luận, trạng thái nghiệm thu vận hành, hạn chế, hướng phát triển và tài liệu tham khảo.
- `images/`:
  - `segmented_map.png`: Ảnh phân vùng bản đồ đã xác minh từ `artifacts/segmented_map.png`.
  - `README.md`: Danh mục 1 ảnh đã có và 9 ảnh cần chụp bổ sung khi chạy thực tế.
- `HUONG_DAN_CHUP_ANH.md`: Hướng dẫn từng bước chạy hệ thống và chụp 9 ảnh màn hình bổ sung.
- `ANTIGRAVITY_HANDOFF.md`: Biên bản bàn giao kiểm toán tự động của Antigravity.

## 2. Cách biên dịch sang PDF

### Cách 1: Biên dịch trên Ubuntu 22.04 bằng `pdflatex`

Nếu máy chưa cài đặt TeX Live, cài đặt các gói cần thiết:

```bash
sudo apt-get update
sudo apt-get install -y \
  texlive-latex-base \
  texlive-latex-recommended \
  texlive-latex-extra \
  texlive-fonts-recommended \
  texlive-lang-other \
  texlive-pictures
```

Sau đó biên dịch 2 lần liên tiếp để cập nhật đầy đủ mục lục (`\tableofcontents`) và tham chiếu:

```bash
cd report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

### Cách 2: Biên dịch trên Overleaf hoặc Prism

1. Nén toàn bộ thư mục `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730` thành file `.zip` và tải lên Overleaf/Prism.
2. Chọn trình biên dịch **pdfLaTeX** và file gốc là `main.tex`.
3. Macro `\reportfigure` tạo khung giữ chỗ cho các ảnh runtime còn thiếu. Việc biên dịch thành công vẫn cần được xác minh trên máy có đầy đủ bộ công cụ và gói TeX.

## 3. Quy trình cập nhật trước khi nộp bài cuối cùng

1. Thực hiện phiên chạy thực tế theo `HUONG_DAN_CHUP_ANH.md` và lưu đủ 9 file ảnh PNG vào `images/`:
   - `01_original_occupancy_map.png`
   - `02_map_editor_ui.png`
   - `03_voice_control_ui.png`
   - `04_voice_command_zone_a.png`
   - `05_voice_command_alias_lab.png`
   - `06_invalid_region_handling.png`
   - `07_rviz_single_route.png`
   - `08_multi_leg_route_and_cancel.png`
   - `09_obstacle_avoidance.png`
2. Tìm toàn bộ vị trí đánh dấu `\pending` trong thư mục `content/`:

```bash
grep -R -n -E 'pending|CHÈN URL' content/
```

3. Thay thế các mục `\pending` trong `content/07-ket-qua-kiem-thu-tu-dong.tex`, `content/08-nghiem-thu-thuc-te-minh-chung.tex` và `content/09-ket-luan-tai-lieu-tham-khao.tex` bằng số liệu thực nghiệm thật (tên micro, transcript trả về của 3 câu lệnh, độ trễ từng lần gọi Gemini API, kết quả điều hướng đơn chặng/đa chặng/hủy lệnh/tránh vật cản, link GitHub Public và link video demo công khai).
4. **Quy tắc bảo mật bắt buộc:** Không bao giờ dán khóa `GEMINI_API_KEY`, nội dung file âm thanh riêng tư hoặc thông tin xác thực cá nhân vào báo cáo hay ảnh chụp màn hình.
5. Biên dịch lại `main.tex` 2 lần để xuất file `main.pdf` hoàn chỉnh.
