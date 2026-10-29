# Khảo giá tài sản bảo đảm (bản mẫu)

Công cụ HỖ TRỢ khảo giá từ tin rao bán; kết quả chỉ để tham khảo, không thay thế thẩm định giá.

## Chạy
    pip install -r requirements.txt
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    pytest            # kiểm thử lõi (trích xuất, ánh xạ cũ-mới, thống kê)

## Dùng
- Nhập xã/huyện/tỉnh (tên cũ HOẶC mới đều được), diện tích, loại đất → "Khảo giá".
- Tích "Thu thập mới" để app tự lấy tin từ: Chợ Tốt/Nhà Tốt (API), alonhadat, batdongsan, thuviennhadat, raobannhadat (mở trang kết quả theo tỉnh). Các trang web có thể chặn truy cập tự động: lỗi được ghi ở khung "phễu lọc". Nếu một nguồn bị chặn, bỏ tích nguồn đó và dùng các nguồn còn lại hoặc ô "Thêm tin thủ công". Kết quả lưu SQLite (`data/khaogia.sqlite`).
- Tin Facebook/Zalo: dán nội dung vào ô cuối trang, app tự trích giá/diện tích/loại đất; kiểm tra lại số trước khi dùng.
- Xuất Excel có link nguồn, thời điểm thu thập, đánh dấu tin ngoại lai.

## Việc phải làm trước khi dùng thật
1. `data/admin_mapping.csv`: điền bảng ánh xạ tên đơn vị hành chính cũ→mới theo nghị quyết sáp nhập (file chỉ có dòng ví dụ).
2. `app/sources/chotot.py`: chưa kiểm chứng với API thật (môi trường dev bị chặn mạng). Chạy thử, chỉnh `CATEGORY_LAND`, tên trường nếu cần.
3. Thêm nguồn khác (alonhadat, batdongsan…): tạo lớp kế thừa `Source`; cần mẫu HTML thật và kiểm tra điều khoản sử dụng/pháp chế.
4. Chưa có: tra số tờ/số thửa, bán kính theo toạ độ, ảnh chụp trang làm chứng cứ, phân quyền/đăng nhập.

## Nguồn "Tìm qua Google" (tuỳ chọn)
Gửi truy vấn như "bán đất đường X xã Y Gia Lai" tới Google Programmable Search (API chính thức), lấy tiêu đề + đoạn trích kèm link thật, trích giá/diện tích. Chỉ đọc đoạn trích, không mở trang đích.
1. Google Cloud Console → bật "Custom Search API" → tạo API key.
2. programmablesearchengine.google.com → tạo công cụ tìm kiếm, chọn "Search the entire web" → lấy mã Search engine ID (cx).
3. Đặt biến môi trường trước khi chạy app (Windows PowerShell):
```
$env:GOOGLE_API_KEY="..."; $env:GOOGLE_CSE_ID="..."
$env:ANTHROPIC_API_KEY="..."   # tuỳ chọn: AI đọc các đoạn trích mà regex không đọc được
python -m uvicorn app.main:app --port 8000
```
Miễn phí khoảng 100 truy vấn/ngày; mỗi lần khảo giá dùng ~9 lượt. Tin do AI trích ghi "google (AI)" trong cột Nguồn: phải mở link kiểm tra lại. Tin Facebook hầu như không có trong kết quả Google.
