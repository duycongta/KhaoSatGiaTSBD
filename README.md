# Khảo giá tài sản bảo đảm (bản mẫu)

Công cụ HỖ TRỢ khảo giá từ tin rao bán; kết quả chỉ để tham khảo, không thay thế thẩm định giá.

## Chạy
    pip install -r requirements.txt
    uvicorn app.main:app --host 0.0.0.0 --port 8000
    pytest            # kiểm thử lõi (trích xuất, ánh xạ cũ-mới, thống kê)

## Dùng
- Nhập xã/huyện/tỉnh (tên cũ HOẶC mới đều được), diện tích, loại đất → "Khảo giá".
- Tích "Thu thập mới" để gọi nguồn trực tuyến (hiện có: Chợ Tốt/Nhà Tốt). Kết quả lưu SQLite (`data/khaogia.sqlite`).
- Tin Facebook/Zalo: dán nội dung vào ô cuối trang, app tự trích giá/diện tích/loại đất; kiểm tra lại số trước khi dùng.
- Xuất Excel có link nguồn, thời điểm thu thập, đánh dấu tin ngoại lai.

## Việc phải làm trước khi dùng thật
1. `data/admin_mapping.csv`: điền bảng ánh xạ tên đơn vị hành chính cũ→mới theo nghị quyết sáp nhập (file chỉ có dòng ví dụ).
2. `app/sources/chotot.py`: chưa kiểm chứng với API thật (môi trường dev bị chặn mạng). Chạy thử, chỉnh `CATEGORY_LAND`, tên trường nếu cần.
3. Thêm nguồn khác (alonhadat, batdongsan…): tạo lớp kế thừa `Source`; cần mẫu HTML thật và kiểm tra điều khoản sử dụng/pháp chế.
4. Chưa có: tra số tờ/số thửa, bán kính theo toạ độ, ảnh chụp trang làm chứng cứ, phân quyền/đăng nhập.
