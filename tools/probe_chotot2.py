"""Chạy:  python tools/probe_chotot2.py   rồi gửi toàn bộ phần in ra.
Tự tìm mã khu vực của Chợ Tốt từ tin Quy Nhơn, rồi thử lọc đất theo khu vực (không dùng từ khoá)."""
import requests

API = "https://gateway.chotot.com/v1/public/ad-listing"
H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

def get(**p):
    r = requests.get(API, params=p, headers=H, timeout=20)
    return r.status_code, r.json()

st, j = get(cg=1040, q="Quy Nhơn", limit=20, st="s")
ads = j.get("ads", [])
print("Số tin mẫu:", len(ads))
ad = next((a for a in ads if "Qui Nh" in (a.get("area_name") or "")), ads[0])
print("\nCác trường liên quan khu vực trong 1 tin mẫu:")
for k, v in ad.items():
    if any(s in k.lower() for s in ("region", "area", "ward", "street", "address", "geo", "lat", "long")):
        print(f"  {k} = {v}")

cands = {}
for k in ("region_v2", "region", "area_v2", "area", "ward", "ward_v2"):
    if k in ad:
        cands[k] = ad[k]
print("\nTrường có thể dùng để lọc:", cands)

def show(label, **p):
    try:
        st, j = get(cg=1040, limit=20, st="s", **p)
    except Exception as e:
        print(f"[{label}] LỖI {e}"); return
    a = j.get("ads", [])
    regs = sorted({(x.get("region_name"), x.get("area_name")) for x in a})
    print(f"[{label}] http={st} total={j.get('total')} trang_nay={len(a)} khu vực: {regs[:4]}")

print()
if "region_v2" in cands:
    show("lọc tỉnh region_v2", region_v2=cands["region_v2"])
if "region" in cands:
    show("lọc tỉnh region", region=cands["region"])
if "region_v2" in cands and "area_v2" in cands:
    show("lọc tỉnh+huyện (v2)", region_v2=cands["region_v2"], area_v2=cands["area_v2"])
if "region" in cands and "area" in cands:
    show("lọc tỉnh+huyện (cũ)", region=cands["region"], area=cands["area"])
if "region_v2" in cands and "area_v2" in cands and "ward" in ad:
    show("lọc tỉnh+huyện+phường", region_v2=cands["region_v2"], area_v2=cands["area_v2"], ward=ad["ward"])
print("\nXong. Hãy copy toàn bộ phần trên gửi lại.")
