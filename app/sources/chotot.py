"""Nguồn Chợ Tốt / Nhà Tốt qua API công khai dùng bởi chính website.

CHƯA KIỂM CHỨNG TRÊN DỮ LIỆU THẬT (môi trường phát triển bị chặn mạng).
Khi chạy lần đầu, kiểm tra và chỉnh các hằng số dưới đây nếu API trả lỗi/rỗng.
Lưu ý: tuân thủ điều khoản sử dụng của nguồn; hạn chế tần suất gọi.
"""
import datetime as dt, time
import requests
from .base import Source
from ..models import Listing
from ..parse import parse_frontage, guess_land_type

API = "https://gateway.chotot.com/v1/public/ad-listing"
CATEGORY_LAND = 1040      # TODO xác minh: danh mục "Đất" (mua bán). Nếu rỗng, thử 1000 rồi lọc.
HEADERS = {"User-Agent": "Mozilla/5.0 (khaogia-tham-dinh)", "Accept": "application/json"}

class Chotot(Source):
    name = "chotot"

    def search(self, keywords: str, limit: int = 50, max_age_days: int | None = None) -> list[Listing]:
        """Phân trang lùi dần theo thời gian (API trả tin mới nhất trước) cho tới khi đủ `limit`,
        hết tin, hoặc gặp tin cũ hơn `max_age_days`."""
        out, offset = [], 0
        cutoff = (dt.datetime.now() - dt.timedelta(days=max_age_days)).timestamp() * 1000 if max_age_days else None
        stop = False
        while len(out) < limit and not stop:
            params = {"cg": CATEGORY_LAND, "q": keywords, "limit": 20,
                      "o": offset, "st": "s"}   # st=s: tin bán
            r = requests.get(API, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            ads = r.json().get("ads", [])
            if not ads:
                break
            now = dt.datetime.now().isoformat(timespec="seconds")
            for a in ads:
                if cutoff and a.get("list_time") and a["list_time"] < cutoff:
                    stop = True
                    break
                addr = ", ".join(x for x in (a.get("street_name"), a.get("ward_name"),
                                             a.get("area_name"), a.get("region_name")) if x)
                body = a.get("body", "") or ""
                posted = ""
                if a.get("list_time"):
                    posted = dt.datetime.fromtimestamp(a["list_time"] / 1000).isoformat(timespec="seconds")
                out.append(Listing(
                    source=self.name,
                    url=f"https://www.nhatot.com/mua-ban-dat/{a.get('list_id')}.htm",
                    title=a.get("subject", ""), address=addr, description=body,
                    price_vnd=a.get("price"), area_m2=a.get("size") or a.get("land_area"),
                    frontage_m=parse_frontage(a.get("subject", "") + " " + body),
                    land_type=guess_land_type(a.get("subject", "") + " " + body),
                    posted_at=posted, fetched_at=now, raw=a))
            offset += len(ads)
            time.sleep(1.5)   # lịch sự với máy chủ nguồn
        return out
