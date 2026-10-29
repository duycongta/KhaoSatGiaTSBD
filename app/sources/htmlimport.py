"""Đọc trang kết quả tìm kiếm đã lưu từ trình duyệt (Ctrl+S, "Trang web, chỉ HTML").

Cách này không gửi yêu cầu tự động tới các trang web nên không vướng chặn bot; người dùng tự mở trang.
Hỗ trợ: alonhadat.com.vn, batdongsan.com.vn. Nhận diện nguồn theo cấu trúc HTML.
"""
import datetime as dt, re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from ..models import Listing
from ..parse import parse_price, parse_area, parse_frontage, guess_land_type
from ..textnorm import norm

NOT_LAND = re.compile(r"(^|-)(nha|can-ho|chung-cu|biet-thu|villa|shophouse|nha-rieng|van-phong|cho-thue)(-|$)")

def _txt(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""

def _num(s: str):
    """'87,5 m²' -> 87.5 ; '1.200' -> 1200"""
    m = re.search(r"\d[\d.,]*", s or "")
    if not m:
        return None
    t = m.group(0).rstrip(".,")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", t):
        return float(t.replace(".", ""))
    return float(t.replace(",", "."))

def _is_land(slug_or_url: str, title: str) -> bool:
    if re.search(r"\b\d+\s*(pn|phong ngu)\b", norm(title)):   # có số phòng ngủ -> căn hộ/nhà, dù đăng sai mục
        return False
    slug = slug_or_url.rsplit("/", 1)[-1] if slug_or_url else ""
    path = slug_or_url.split("//")[-1].split("/", 1)[-1] if slug_or_url else ""
    if re.search(r"(^|/|-)ban-dat(-|/|$)", path) or re.search(r"(^|-)(lo-dat|dat-nen|dat-tho-cu|dat-o|dat-vuon|dat-rung)(-|$)", slug):
        return True
    t = norm(title)
    return bool(re.search(r"\bdat\b", t)) and not re.search(r"\b(can ho|chung cu|biet thu|nha pho|nha cap|nha \d|nha mat)\b", t) \
        and not NOT_LAND.search(slug)

def detect(html: str) -> str:
    if 'class="property-item"' in html or "property-item" in html and "itemprop=\"datePosted\"" in html:
        return "alonhadat"
    if "js__card" in html and "re__card" in html:
        return "batdongsan"
    return ""

def parse_alonhadat(html: str, only_land=True) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    now = dt.datetime.now().isoformat(timespec="seconds")
    out = []
    for it in soup.select("article.property-item"):
        a = it.select_one("a.link[href]") or it.select_one("a[href]")
        if not a:
            continue
        url = a["href"]
        title = _txt(it.select_one(".property-title"))
        if only_land and not _is_land(url, title):
            continue
        price_el = it.select_one('[itemprop="price"]')
        price = float(price_el["content"]) if price_el is not None and price_el.get("content", "").replace(".", "").isdigit() else parse_price(_txt(price_el))
        area_el = it.select_one('[itemprop="floorSize"] [itemprop="value"]')
        area = _num(_txt(area_el)) if area_el else None
        new_addr = _txt(it.select_one("p.new-address"))
        old_addr = _txt(it.select_one("p.old-address")).replace("(cũ)", "").strip()
        brief = _txt(it.select_one(".brief")).replace("<< Xem chi tiết >>", "").strip()
        dp = it.select_one('[itemprop="datePosted"]')
        out.append(Listing(
            source="alonhadat", url=url, title=title,
            address=", ".join(x for x in (old_addr, new_addr) if x), description=brief,
            price_vnd=price, area_m2=area, frontage_m=parse_frontage(title + " " + brief),
            land_type=guess_land_type(title + " " + brief + " " + url.replace("-", " ")),
            posted_at=dp.get("datetime", "") if dp is not None else "", fetched_at=now,
            raw={"title": title, "price_text": _txt(price_el), "area_text": _txt(area_el), "old_address": old_addr, "new_address": new_addr}))
    return out

def _bds_posted(txt: str, today: dt.date) -> str:
    t = norm(txt)
    if "hom nay" in t:
        return today.isoformat()
    if "hom qua" in t:
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\s*(ngay|tuan|thang)", t)
    if m:
        n, u = int(m.group(1)), m.group(2)
        return (today - dt.timedelta(days=n * {"ngay": 1, "tuan": 7, "thang": 30}[u])).isoformat()
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", txt)
    return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""

def parse_batdongsan(html: str, base="https://batdongsan.com.vn", only_land=True) -> list[Listing]:
    soup = BeautifulSoup(html, "html.parser")
    now = dt.datetime.now(); today = now.date(); now_s = now.isoformat(timespec="seconds")
    out = []
    for c in soup.select("div.js__card"):
        a = c.select_one("a.js__product-link-for-product-id[href]") or c.select_one("a[href*='-pr']")
        if not a:
            continue
        url = urljoin(base, a["href"])
        title = _txt(c.select_one(".re__card-title")) or a.get("title", "")
        if only_land and not _is_land(url, title):
            continue
        price_txt = _txt(c.select_one(".re__card-config-price"))
        area_txt = _txt(c.select_one(".re__card-config-area"))
        price = parse_price(price_txt) if "thoa thuan" not in norm(price_txt) else None
        price = round(price) if price else None
        loc = _txt(c.select_one(".re__card-location"))
        desc = _txt(c.select_one(".re__card-description"))
        out.append(Listing(
            source="batdongsan", url=url, title=title, address=loc, description=desc,
            price_vnd=price, area_m2=_num(area_txt), frontage_m=parse_frontage(title + " " + desc),
            land_type=guess_land_type(title + " " + desc + " " + url.rsplit("/", 1)[-1].replace("-", " ")),
            posted_at=_bds_posted(_txt(c.select_one(".re__card-published-info-published-at")), today), fetched_at=now_s,
            raw={"title": title, "price_text": price_txt, "area_text": area_txt, "location": loc,
                 "price_per_m2_text": _txt(c.select_one(".re__card-config-price_per_m2"))}))
    return out

def parse_saved_html(html: str, only_land=True) -> tuple[str, list[Listing]]:
    kind = detect(html)
    if kind == "alonhadat":
        return kind, parse_alonhadat(html, only_land)
    if kind == "batdongsan":
        return kind, parse_batdongsan(html, only_land=only_land)
    return "", []
