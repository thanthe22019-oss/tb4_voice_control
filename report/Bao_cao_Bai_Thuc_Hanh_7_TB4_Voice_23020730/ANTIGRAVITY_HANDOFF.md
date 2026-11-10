# ANTIGRAVITY HANDOFF — Báo cáo Bài thực hành 7 (`Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730`)

**Ngày thực hiện:** 2026-11-10 (Asia/Ho_Chi_Minh)

**Kế hoạch triển khai:** `docs/superpowers/plans/2026-11-10-antigravity-long-report.md`

**Đặc tả thiết kế ràng buộc:** `docs/superpowers/specs/2026-11-10-antigravity-long-report-design.md`

---

## 1. Danh sách các file đã tạo (`report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/`)

Chỉ thư mục báo cáo mới và task artifact của Antigravity được tạo/cập nhật; toàn bộ mã nguồn ứng dụng ROS/Python, cấu hình, bản đồ, bài kiểm thử, artifact hiện có và thư mục báo cáo mẫu cũ (`Bao_cao_TurtleBot4_SLAM_Nav2_23020730`) được giữ nguyên hoàn toàn ở chế độ chỉ đọc:

1. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/main.tex`
2. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/preamble.tex`
3. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/references.bib`
4. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/Logo_UET.png`
5. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/HUONG_DAN.md`
6. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/HUONG_DAN_CHUP_ANH.md`
7. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/ANTIGRAVITY_HANDOFF.md`
8. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/images/README.md`
9. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/images/segmented_map.png` (sao chép nguyên bản từ `artifacts/segmented_map.png`, kích thước `788 x 1101` px)
10. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/00-frontmatter.tex`
11. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/01-muc-tieu-kien-truc.tex`
12. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/02-phan-vung-map-editor.tex`
13. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/03-ban-do-ngu-nghia-toa-do.tex`
14. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/04-nhan-dang-giong-noi-gemini.tex`
15. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/05-phan-tich-lenh-dieu-huong-nav2.tex`
16. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/06-cai-dat-van-hanh-kiem-thu.tex`
17. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/07-ket-qua-kiem-thu-tu-dong.tex`
18. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/08-nghiem-thu-thuc-te-minh-chung.tex`
19. `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/content/09-ket-luan-tai-lieu-tham-khao.tex`

---

## 2. Kết quả kiểm tra, biên dịch và kiểm toán (Verification Results)

- **Kiểm tra trình biên dịch `pdflatex` và gói TeX Live:**
  - Thực thi `pdflatex -interaction=nonstopmode -halt-on-error main.tex`: máy trạm hiện tại trả về `pdflatex: command not found` (không có `pdflatex`, `xelatex`, `lualatex`, `latexmk` hay `tectonic` được cài đặt).
  - Kiểm tra `dpkg-query -W`: các gói `texlive-latex-base`, `texlive-latex-recommended`, `texlive-latex-extra`, `texlive-fonts-recommended`, `texlive-lang-other` và `texlive-pictures` đều ở trạng thái `not-installed`.
- **Đường dẫn PDF và số trang (PDF Path & Page Count):**
  - **PDF Path:** Chưa sinh file `main.pdf` tại chỗ do thiếu công cụ `pdflatex` và bộ gói `texlive-*` nêu trên (tuân thủ nghiêm ngặt yêu cầu Task 4: ghi nhận chính xác công cụ/gói còn thiếu thay vì tuyên bố đã biên dịch). Khi chạy `pdflatex` 2 lần trên máy có TeX Live hoặc trên Overleaf/Prism, file đích sẽ được tạo tại `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/main.pdf`.
  - **Page Count:** `N/A (toolchain pdflatex chưa được cài đặt trên máy hiện tại)`.
- **Kiểm tra cấu trúc tĩnh LaTeX (12/12 file `.tex`; không thay thế biên dịch):**
  - Toàn bộ lệnh `\input{...}` trong `main.tex` trỏ tới file tồn tại.
  - Kiểm tra tĩnh trước đó ghi nhận ngoặc nhọn `{...}` và môi trường `\begin{...}` / `\end{...}` cân bằng; kết quả này chỉ phản ánh các mẫu đã kiểm tra.
  - Rà soát ký tự đặc biệt (`_`, `%`, `&`, `]` trong tham số tùy chọn của `\reportfigure`) đã sửa các dấu `_` và `[]` được phát hiện tại `03-ban-do-ngu-nghia-toa-do.tex` và `08-nghiem-thu-thuc-te-minh-chung.tex`. Vòng rà soát cuối còn thay từ chứa ký tự Cyrillic bằng `lô-gic` và quét lại cây báo cáo. Những kiểm tra tĩnh này không xác nhận toàn bộ cú pháp, khả năng hiển thị phông chữ hay kết quả biên dịch; PDF vẫn chưa được biên dịch do thiếu công cụ TeX.
- **Kiểm tra `git diff --check` và trạng thái cây làm việc:**
  - `git diff --check`: **PASSED** (không có lỗi khoảng trắng hay xung đột).
  - `git status -sb`: chỉ có thư mục mới `?? report/`, không có bất kỳ file mã nguồn, cấu hình, bản đồ hay bài kiểm thử nào bị sửa đổi. Không thực hiện `git commit` hay `git push`.
- **Quét tiền tố khóa xác thực và thông tin nhạy cảm:**
  - Quét biểu thức chính quy cho các tiền tố `AIza...`, `ghp_...`, `github_pat_...`, `sk-...`, `ya29....` trên toàn bộ repository (loại trừ `.git`, `.venv-speech`, `build`, `install`, `log`): **0 matches**. Không có khóa API, file âm thanh `.wav` hay nội dung hội thoại riêng tư nào được đọc, sao chép hoặc đưa vào báo cáo.
- **Kiểm toán các tuyên bố chưa có bằng chứng thực tế:**
  - Không có bất kỳ kết quả điều hướng trực tiếp, chuỗi transcript tiếng Việt nhận dạng thực tế, độ trễ từng câu lệnh hay URL công khai giả định nào được viết như kết quả đã hoàn thành.
  - Phản hồi khoảng `3,2 giây` của `gemini-3.5-transcribe` được ghi nhận đúng bản chất là bằng chứng hợp đồng phản hồi (`audio_transcription` response-contract evidence), kèm khẳng định rõ chưa chứng minh độ chính xác nhận dạng tiếng Việt.

---

## 3. Các vị trí giữ chỗ còn lại (`\pending` và ảnh chụp màn hình)

### 3.1. Các vị trí văn bản `\pending` cần cập nhật sau khi chạy thực tế

1. `content/07-ket-qua-kiem-thu-tu-dong.tex` (mục `9.3`, dòng 58): trạng thái chờ nghiệm thu độ chính xác nhận dạng tiếng Việt và thời gian phản hồi thực tế với khóa API mới.
2. `content/08-nghiem-thu-thuc-te-minh-chung.tex` (mục `10.1`, dòng 18--40): 12 dòng trong bảng nghiệm thu thực tế (`MANUAL/HARDWARE PENDING`):
   - Kịch bản 1: Map Editor sửa/lưu/reload 3 vùng và xuất `segmented_map.png`;
   - Kịch bản 2: Lệnh giọng nói 1 “Đi đến khu vực A”;
   - Kịch bản 3: Lệnh giọng nói 2 (alias) “Đi đến phòng thí nghiệm”;
   - Kịch bản 4: Lệnh giọng nói 3 (`FROM_TO` ngoài `Khu vực A`) “Di chuyển từ khu vực A đến khu vực B” (2 chặng);
   - Kịch bản 5: Lệnh `FROM_TO` khi robot đang ở trong `Khu vực A` (rút gọn còn 1 chặng tới `Khu vực B`);
   - Kịch bản 6: Vùng không tồn tại (`unknown_region`) báo lỗi trên UI và không gửi goal;
   - Kịch bản 7: Khóa nhận lệnh mới khi đang di chuyển và hủy lộ trình (`Hủy lộ trình`);
   - Kịch bản 8: Nav2 tái lập đường đi và tránh vật cản trong mô phỏng;
   - Kịch bản 9: Độ chính xác nhận dạng Gemini API và độ trễ từng yêu cầu cho 3 câu lệnh;
   - Kịch bản 10: Thiết bị micro (`arecord -l`) và 3 lần thu âm push-to-talk;
   - Kịch bản 11: Liên kết GitHub repository công khai;
   - Kịch bản 12: Liên kết video demo công khai (Google Drive / YouTube).
3. `content/08-nghiem-thu-thuc-te-minh-chung.tex` (mục `10.3.1`, dòng 65 & mục `10.3.2`, dòng 70): nhận xét chi tiết kết quả nhận dạng tiếng Việt và kết quả điều hướng đơn chặng/đa chặng/hủy lệnh/tránh vật cản.
4. `content/08-nghiem-thu-thuc-te-minh-chung.tex` (mục `10.4`, dòng 78--79): placeholder chèn URL GitHub Public và URL Video Demo công khai.
5. `content/09-ket-luan-tai-lieu-tham-khao.tex` (mục `11.2`, dòng 18): đoạn xác nhận hoàn tất nghiệm thu vận hành thực tế.

### 3.2. Các file ảnh chụp màn hình cần bổ sung vào `images/`

*(Ảnh `images/segmented_map.png` đã có sẵn; 9 ảnh dưới đây hiện hiển thị dưới dạng khung giữ chỗ `\reportfigure` có ghi rõ tên file và bằng chứng cần chụp)*:

1. `images/01_original_occupancy_map.png`
2. `images/02_map_editor_ui.png`
3. `images/03_voice_control_ui.png`
4. `images/04_voice_command_zone_a.png`
5. `images/05_voice_command_alias_lab.png`
6. `images/06_invalid_region_handling.png`
7. `images/07_rviz_single_route.png`
8. `images/08_multi_leg_route_and_cancel.png`
9. `images/09_obstacle_avoidance.png`

---

## 4. Các bước hành động tiếp theo chính xác dành cho người dùng (Exact Next Actions)

1. **Thu hồi/xoay vòng các khóa API cũ** từng xuất hiện trong lịch sử chẩn đoán trước đây và tạo một khóa `GEMINI_API_KEY` mới có giới hạn quyền, chỉ `export` trong shell khi chạy demo.
2. **Thực hiện phiên chạy nghiệm thu thực tế và quay video / chụp 9 ảnh màn hình** theo đúng hướng dẫn từng bước trong `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/HUONG_DAN_CHUP_ANH.md` và `docs/DEMO.md`, lưu đủ 9 file `.png` vào `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730/images/`.
3. **Cập nhật các vị trí `\pending`** trong `content/07-ket-qua-kiem-thu-tu-dong.tex`, `content/08-nghiem-thu-thuc-te-minh-chung.tex` và `content/09-ket-luan-tai-lieu-tham-khao.tex` (kiểm tra bằng lệnh `grep -R -n -E 'pending|CHÈN URL' content/`), đồng thời điền URL GitHub Public và URL Video Demo đã bật quyền truy cập công khai.
4. **Biên dịch báo cáo sang PDF** bằng một trong hai cách:
   - Trên máy Ubuntu (sau khi cài đặt `sudo apt-get install -y texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended texlive-lang-other texlive-pictures`):
     ```bash
     cd report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730
     pdflatex -interaction=nonstopmode -halt-on-error main.tex
     pdflatex -interaction=nonstopmode -halt-on-error main.tex
     ```
   - Hoặc tải toàn bộ thư mục `report/Bao_cao_Bai_Thuc_Hanh_7_TB4_Voice_23020730` lên Overleaf / Prism và biên dịch `main.tex` với trình biên dịch **pdfLaTeX**.
