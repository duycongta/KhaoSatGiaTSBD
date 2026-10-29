"""Nguồn "Tìm qua Google": Google Programmable Search (API chính thức) -> lấy tiêu đề + đoạn trích có link thật
-> trích giá/diện tích bằng regex; tuỳ chọn dùng AI (Claude) cho các kết quả regex không đọc được.

Cấu hình bằng biến môi trường:
  GOOGLE_API_KEY, GOOGLE_CSE_ID     bắt buộc (tạo ở Google Cloud + programmablesearchengine.google.com,
                                    chọn "Search the entire web"). Miễn phí ~100 truy vấn/ngày.
  ANTHROPIC_API_KEY                 tuỳ chọn: bật trích xuất bằng AI. ANTHROPIC_MODEL mặc định claude-haiku-5-5.
Lưu ý: chỉ đọc tiêu đề/đoạn trích Google trả về, không mở trang đích. Kết quả AI được đánh dấu "(AI)" để kiểm tra lại.
"""
import datetime as dt, json, os, re, time
import requests
from .base import Source
from ..models import Listing
from ..parse import parse_price, parse_area, parse_frontage, guess_land_type
from ..textnorm import norm

CSE_API = "https://www.googleapis.com/customsearch/v1"
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
LAND_WORDS = {"ONT": "đất thổ cư", "ODT": "đất ở đô thị", "CLN": "đất vườn cây lâu năm", "BHK": "đất trồng cây hàng năm",
              "RSX": "đất rừng sản xuất", "NTS": "đất nuôi trồng thuỷ sản", "NN": "đất nông nghiệp"}

def build_queries(duong: str, xa: str, huyen: str, tinh: str, land_type: str = "") -> list[str]:
    where = " ".join(x.strip() for x in (duong, xa, huyen) if x.strip())
    what = LAND_WORDS.get(land_type, "đất")
    base = f"bán {what} {where} {tinh}".strip()
    return [base, f"{base} site:facebook.com", f"{base} giá m2 sổ đỏ"]

def _ai_extract(title: str, snippet: str) -> dict | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    prompt = ("Đọc tiêu đề và đoạn trích tin rao bán bất động sản. Chỉ trả về JSON một dòng với các khoá: "
              '{"is_for_sale": true|false, "price_vnd": số hoặc null, "area_m2": số hoặc null, "frontage_m": số hoặc null, '
              '"land_type": "ONT|ODT|CLN|BHK|RSX|NTS|NN hoặc rỗng"}. Chỉ lấy thông tin GHI RÕ trong văn bản; '
              "không suy đoán; thiếu thì để null. Giá đổi ra đồng (1 tỷ = 1000000000).\n\n"
              f"Tiêu đề: {title}\nĐoạn trích: {snippet}")
    r = requests.post(ANTHROPIC_API, timeout=40, headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                      "content-type": "application/json"},
                      json={"model": os.environ.get("ANTHROPIC_MODEL", "claude-haiku-5-5"), "max_tokens": 200,
                            "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    txt = r.json()["content"][0]["text"]
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0)) if m else None

def _verify_ai(d: dict, text: str) -> dict:
    """Chống AI bịa: diện tích phải có số xuất hiện trong văn bản; giá chỉ nhận khi văn bản có đơn vị tỷ/triệu."""
    out = {}
    t = norm(text, keep_num=True)
    a = d.get("area_m2")
    if isinstance(a, (int, float)) and a > 0 and re.search(rf"(?<!\d){int(a)}(?!\d)", t.replace(".", "").replace(",", " ")):
        out["area_m2"] = float(a)
    p = d.get("price_vnd")
    if isinstance(p, (int, float)) and p >= 1e6 and re.search(r"\b(ty|ti|trieu|tr)\b", t):
        out["price_vnd"] = float(p)
    f = d.get("frontage_m")
    if isinstance(f, (int, float)) and 0 < f < 100:
        out["frontage_m"] = float(f)
    out["land_type"] = d.get("land_type") or ""
    out["is_for_sale"] = d.get("is_for_sale", True) is not False
    return out

class GoogleSearch(Source):
    name = "google"
    keyword_search = False
    query_search = True

    def configured(self) -> bool:
        return bool(os.environ.get("GOOGLE_API_KEY") and os.environ.get("GOOGLE_CSE_ID"))

    def fetch_queries(self, queries: list[str], limit: int, log: list[str]) -> list[Listing]:
        if not self.configured():
            log.append("google: chưa cấu hình GOOGLE_API_KEY / GOOGLE_CSE_ID (xem README) — bỏ qua nguồn này")
            return []
        out, ai_used, calls = [], 0, 0
        now = dt.datetime.now().isoformat(timespec="seconds")
        for q in queries:
            got = 0
            for start in range(1, min(limit, 30) + 1, 10):   # API: tối đa 10 kết quả/lần, 100 kết quả/truy vấn
                try:
                    r = requests.get(CSE_API, params={"key": os.environ["GOOGLE_API_KEY"], "cx": os.environ["GOOGLE_CSE_ID"],
                                                      "q": q, "num": 10, "start": start, "hl": "vi", "lr": "lang_vi"}, timeout=25)
                    calls += 1
                    if r.status_code in (403, 429):
                        log.append(f"google: HTTP {r.status_code} — {r.json().get('error', {}).get('message', 'hết hạn mức hoặc khoá sai')}")
                        return out
                    r.raise_for_status()
                except Exception as e:
                    log.append(f"google · '{q}': lỗi {e}"); break
                items = r.json().get("items", [])
                for it in items:
                    title, snip, url = it.get("title", ""), (it.get("snippet", "") or "").replace("\n", " "), it.get("link", "")
                    text = f"{title}. {snip}"
                    nt = norm(text)
                    if re.search(r"\b(cho thue|can thue|tim thue)\b", nt) and not re.search(r"\b(ban)\b", nt):
                        continue
                    price, area, front = parse_price(text), parse_area(text), parse_frontage(text)
                    ltype, how = guess_land_type(text), "regex"
                    if (price is None or area is None) and os.environ.get("ANTHROPIC_API_KEY"):
                        try:
                            d = _ai_extract(title, snip)
                            ai_used += 1
                            if d:
                                v = _verify_ai(d, text)
                                if not v["is_for_sale"]:
                                    continue
                                price = price or v.get("price_vnd"); area = area or v.get("area_m2")
                                front = front or v.get("frontage_m"); ltype = ltype or v.get("land_type", "")
                                how = "ai" if (price or area) else "regex"
                        except Exception as e:
                            log.append(f"google: AI trích xuất lỗi: {e}")
                    if price is None:        # không có giá thì không dùng để khảo giá
                        continue
                    out.append(Listing(
                        source=f"google{' (AI)' if how == 'ai' else ''}", url=url, title=title, address="", description=snip,
                        price_vnd=price, area_m2=area, frontage_m=front, land_type=ltype, posted_at="", fetched_at=now,
                        raw={"query": q, "extract": how, "snippet": snip, "displayLink": it.get("displayLink", "")}))
                    got += 1
                if len(items) < 10:
                    break
                time.sleep(0.5)
            log.append(f"google · '{q}': {got} tin có giá")
        log.append(f"google: dùng {calls} lượt gọi API" + (f", {ai_used} lượt AI" if ai_used else ""))
        return out
