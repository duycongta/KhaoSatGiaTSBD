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
