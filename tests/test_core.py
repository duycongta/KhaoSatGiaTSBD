from app.parse import parse_price, parse_area, parse_frontage, guess_land_type
from app.textnorm import AdminMap, core_name
from app.models import Listing
from app.search import filter_listings, location_terms
from app.stats import summarize
from pathlib import Path
import csv, tempfile

def test_price():
    assert parse_price("Bán đất giá 1,2 tỷ") == 1.2e9
    assert parse_price("giá 850 triệu") == 850e6
    assert parse_price("2 tỷ 500 triệu") == 2.5e9
    assert parse_price("không có giá") is None

def test_area_land():
    assert parse_area("DT 500m2 đất ở") == 500
    assert parse_area("rộng 1,5 ha") == 15000
    assert guess_land_type("đất vườn cây lâu năm") == "CLN"
    assert guess_land_type("đất rừng keo") == "RSX"
    assert parse_frontage("mặt tiền 5m") == 5

def mk(old_new):
    d = Path(tempfile.mkdtemp()) / "m.csv"
    d.write_text("ten_cu,ten_moi,ghi_chu\n" + old_new, encoding="utf-8"); return AdminMap(d)

def test_mapping_both_ways():
    a = mk("Phường Nhơn Bình,Quy Nhơn Nam,x\n# bỏ qua\n")
    assert "quy nhon nam" in a.aliases("Nhơn Bình")
    assert "nhon binh" in a.aliases("phường Quy Nhơn Nam")

def L(price, area, addr="Phường Nhơn Bình, Quy Nhơn", t="x"):
    return Listing("t", f"u{price}{area}", t, address=addr, price_vnd=price, area_m2=area)

def test_filter_matches_new_name_listing():
    a = mk("Phường Nhơn Bình,Quy Nhơn Nam,x\n")
    items = [L(1e9, 100, "Quy Nhơn Nam, Gia Lai"), L(1e9, 100, "Pleiku, Gia Lai", "b")]
    out = filter_listings(items, location_terms(a, "Nhơn Bình", "", ""), need=1)
    assert len(out) == 1

def test_stats_warning_and_outlier():
    few = summarize([L(1e9, 100), L(1.1e9, 100)])
    assert "CẢNH BÁO" in few.warning
    many = summarize([L(p * 1e8, 100, t=str(p)) for p in (10, 11, 12, 10, 11, 100)])
    assert len(many.outliers) == 1 and many.n_used == 5
    assert many.low < many.p25

def test_street_rank():
    from app.search import same_street, rank
    a = L(1e9, 100, "Đường Nguyễn Huệ, Quy Nhơn", "a"); b = L(1e9, 100, "Đường Lê Lợi, Quy Nhơn", "b")
    assert same_street(a, "Nguyễn Huệ") and same_street(a, "đường nguyễn huệ") and not same_street(b, "Nguyễn Huệ")
    assert rank([b, a], "Nguyễn Huệ", 100)[0] is a

ALO = """<article class="property-item"><a class="link vip" href="https://alonhadat.com.vn/chinh-chu-ban-dat-mat-bien-xa-nhon-ly-tp-quy-nhon-binh-dinh-18961528.html">
<h3 class="property-title">CHÍNH CHỦ BÁN ĐẤT MẶT BIỂN XÃ NHƠN LÝ</h3></a><time class="created-date" datetime="2026-10-29" itemprop="datePosted">Hôm nay</time>
<p class="brief">Mặt tiền 10m. Đất ở</p>
<span class="price"><span itemprop="price" content="30550000000">65 triệu /&nbsp;m²</span></span>
<span class="area" itemprop="floorSize"><span itemprop="value">470</span> <span itemprop="unitText">m²</span></span>
<p class="new-address"><span itemprop="streetAddress">Đường D1</span>, <span itemprop="addressLocality">Phường Quy Nhơn Đông</span>, <span itemprop="addressRegion">Gia Lai</span></p>
<p class="old-address"><span>Đường D1, Phường Quy Nhơn Đông, Thành phố Quy Nhơn, Bình Định</span> (cũ)</p></article>
<article class="property-item"><a class="link" href="https://alonhadat.com.vn/ban-nha-255-nguyen-hue-1.html"><h3 class="property-title">BÁN NHÀ 255 NGUYỄN HUỆ</h3></a></article>"""
BDS = """<div class="js__card js__card-full-web"><a class="js__product-link-for-product-id" href="https://batdongsan.com.vn/ban-dat-phuong-nhon-phu-1/ban-dat-87m-pr46481823">
<div class="re__card-title">BÁN ĐẤT KHU DÂN CƯ 87,5M²</div><span class="re__card-config-price">2,85 tỷ</span><span class="re__card-config-area">87,5 m²</span>
<div class="re__card-location">TP. Quy Nhơn (P. Quy Nhơn Bắc mới)</div><span class="re__card-published-info-published-at">Đăng hôm nay</span></a></div>
<div class="js__card"><a class="js__product-link-for-product-id" href="https://batdongsan.com.vn/ban-can-ho-chung-cu-x/ch-pr1"><div class="re__card-title">Căn hộ 2PN</div></a></div>"""

def test_import_alonhadat_bds():
    from app.sources.htmlimport import parse_saved_html
    k, items = parse_saved_html(ALO)
    assert k == "alonhadat" and len(items) == 2 and [x.kind for x in items] == ["dat", "nha"]
    l = items[0]
    assert l.price_vnd == 30550000000 and l.area_m2 == 470 and l.frontage_m == 10
    assert "Bình Định" in l.address and "Gia Lai" in l.address and l.posted_at == "2026-10-29"
    k, items = parse_saved_html(BDS)
    assert k == "batdongsan" and len(items) == 2 and items[1].kind == "can_ho"
    assert items[0].price_vnd == 2.85e9 and items[0].area_m2 == 87.5 and "Quy Nhơn Bắc" in items[0].address
    assert parse_saved_html("<html></html>")[0] == ""

TVN = """<a href="https://thuviennhadat.vn/ban-dat-phuong-quy-nhon-bac/ban-dat-90m-pst1.html" title="Bán đất 90m² mặt tiền 5m"><div class="KinhDoanhNhaDat-index-post-title"><h2>Bán đất</h2></div></a><div></div>"""
TVN = """<div class="w"><a href="https://thuviennhadat.vn/ban-dat-phuong-quy-nhon-bac/ban-dat-90m-pst1.html" title="Bán đất 90m² mặt tiền 5m"><div class="KinhDoanhNhaDat-index-post-title"><h2>Bán đất</h2></div>
<div class="KinhDoanhNhaDat-index-unit-container"><div class="highlight"> 2,1 tỷ </div><div class="highlight"> 90 m² </div></div>
<span class="KinhDoanhNhaDat-index-post-address"> Quy Nhơn, Bình Định </span></a><div class="KinhDoanhNhaDat-index-post-footer"><span class="post-date"> Đăng hôm nay </span></div></div>
<div class="w"><a href="https://thuviennhadat.vn/ban-can-ho-chung-cu-x/ch-pst2.html" title="Căn hộ"><div class="KinhDoanhNhaDat-index-post-title"><h2>Căn hộ</h2></div></a></div>"""
RBN = """<article class="listing-card " data-listing-id="1"><div class="listing-card__body"><h3 class="listing-card__title">
<a href="https://raobannhadat.vn/chi-tiet-tin/ban-dat-xa-nhon-binh-thanh-pho-quy-nhon-binh-dinh-co-so-do-2">Bán đất xã Nhơn Bình</a></h3>
<div class="listing-card__meta"><span class="price">750 triệu</span><span class="area">180 m²</span></div><p class="listing-card__addr"> Gia Lai </p>
<div class="listing-card__foot"><span class="time">2 tháng trước</span></div></div></article>
<article class="listing-card "><div class="listing-card__body"><h3 class="listing-card__title"><a href="https://raobannhadat.vn/chi-tiet-tin/q-terra-view-bien">Q'TERRA đất vàng</a></h3></div></article>"""

def test_import_thuvien_raoban():
    from app.sources.htmlimport import parse_saved_html
    k, items = parse_saved_html(TVN)
    assert k == "thuviennhadat" and len(items) == 2 and items[1].kind == "can_ho"
    assert items[0].price_vnd == 2.1e9 and items[0].area_m2 == 90 and "quy nhon bac" in items[0].address.lower().replace("ơ","o").replace("ắ","a")
    k, items = parse_saved_html(RBN)
    assert k == "raobannhadat" and len(items) == 2
    assert items[0].price_vnd == 750e6 and items[0].area_m2 == 180 and "nhon binh" in items[0].address and "chi tiet" not in items[0].address

def test_webscrape_pages_and_block(monkeypatch):
    import app.sources.webscrape as ws
    class R:
        def __init__(s, code, text): s.status_code, s.text = code, text
        def raise_for_status(s): pass
    calls = []
    def fake(url, headers=None, timeout=None):
        calls.append(url)
        if "trang-2" in url: return R(200, "<html></html>")       # hết tin -> dừng
        return R(200, ALO)
    monkeypatch.setattr(ws.requests, "get", fake); monkeypatch.setattr(ws.time, "sleep", lambda x: None)
    log = []
    got = ws.Alonhadat().fetch_area("Bình Định", 100, None, log)
    assert len(got) == 2 and calls[0].endswith("/can-ban-nha-dat/binh-dinh") and calls[1].endswith("/trang-2")
    monkeypatch.setattr(ws.requests, "get", lambda *a, **k: R(403, ""))
    log = []; assert ws.Alonhadat().fetch_area("Bình Định", 100, None, log) == [] and "chặn" in log[0]
    assert ws.slugs_for("Gia Lai") == ["gia-lai", "binh-dinh"]

def test_google_source(monkeypatch):
    import app.sources.googlesearch as g
    monkeypatch.setenv("GOOGLE_API_KEY", "k"); monkeypatch.setenv("GOOGLE_CSE_ID", "c"); monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    class R:
        status_code = 200
        def raise_for_status(s): pass
        def json(s): return {"items": [
            {"title": "Bán đất đường Bạch Đằng Quy Nhơn 100m2 giá 3,2 tỷ", "snippet": "Sổ hồng riêng", "link": "https://x/1"},
            {"title": "Cho thuê đất Bạch Đằng 5 triệu/tháng", "snippet": "", "link": "https://x/2"},
            {"title": "Tin tức thị trường đất Quy Nhơn", "snippet": "không có giá", "link": "https://x/3"}]}
    monkeypatch.setattr(g.requests, "get", lambda *a, **k: R()); monkeypatch.setattr(g.time, "sleep", lambda x: None)
    log = []
    got = g.GoogleSearch().fetch_queries(g.build_queries("Bạch Đằng", "Quy Nhơn", "", "Bình Định"), 10, log)
    assert [l.url for l in got][:1] == ["https://x/1"] and got[0].price_vnd == 3.2e9 and got[0].area_m2 == 100
    assert all(l.url != "https://x/2" and l.url != "https://x/3" for l in got)
    monkeypatch.delenv("GOOGLE_API_KEY"); log = []
    assert g.GoogleSearch().fetch_queries(["q"], 10, log) == [] and "chưa cấu hình" in log[0]

def test_ai_verification():
    from app.sources.googlesearch import _verify_ai
    v = _verify_ai({"price_vnd": 3.2e9, "area_m2": 999, "is_for_sale": True}, "Bán đất 100m2 giá 3,2 tỷ")
    assert v["price_vnd"] == 3.2e9 and "area_m2" not in v      # diện tích 999 không có trong văn bản -> bỏ


def test_kind_and_filter():
    from app.parse import guess_kind
    assert guess_kind("https://x/ban-dat-nen-du-an-abc/p-pr1", "") == "dat"
    assert guess_kind("https://x/ban-can-ho-chung-cu-q/ch-pr1", "") == "can_ho"
    assert guess_kind("https://x/ban-nha-rieng-duong-a/x-pr1", "") == "nha"
    assert guess_kind("", "Bán nhà 2 tầng hẻm Bạch Đằng") == "nha"
    a, b = L(1e9, 100, t="a"), L(3e9, 100, t="b"); a.kind, b.kind = "dat", "nha"
    out = filter_listings([a, b], [], kind="dat")
    assert out == [a]
