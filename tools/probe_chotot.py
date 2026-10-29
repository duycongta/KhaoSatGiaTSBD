"""Chạy:  python tools/probe_chotot.py
Thử vài cách gọi API Chợ Tốt và in ra kết quả, để chọn cách lấy được nhiều tin đất nhất.
Gửi toàn bộ phần in ra cho người phát triển."""
import requests, collections

API = "https://gateway.chotot.com/v1/public/ad-listing"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def call(label, **p):
    try:
        r = requests.get(API, params=p, headers=H, timeout=20)
        j = r.json()
    except Exception as e:
        print(f"\n[{label}] LỖI: {e}"); return
    ads = j.get("ads", [])
    cats = collections.Counter((a.get("category"), a.get("category_name")) for a in ads)
    print(f"\n[{label}] http={r.status_code} total={j.get('total')} trang_nay={len(ads)} keys={sorted(j.keys())[:8]}")
    print("  danh mục trong trang:", dict(cats))
    for a in ads[:3]:
        print("  -", a.get("subject"), "|", a.get("price_string"), "|", a.get("size"), "| region:", a.get("region_name"), "| area:", a.get("area_name"))

call("A cg=1040 q=Quy Nhơn", cg=1040, q="Quy Nhơn", limit=20, st="s")
call("B cg=1040 không q", cg=1040, limit=20, st="s")
call("C cg=1000 q=Quy Nhơn", cg=1000, q="Quy Nhơn", limit=20, st="s")
call("D cg=1000 q=đất Quy Nhơn", cg=1000, q="đất Quy Nhơn", limit=20, st="s")
call("E không cg q=đất Quy Nhơn", q="đất Quy Nhơn", limit=20)
call("F cg=1040 q=Quy Nhơn trang 2", cg=1040, q="Quy Nhơn", limit=20, st="s", o=20)
print("\nXong. Hãy copy toàn bộ phần trên gửi lại.")
