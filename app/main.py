import datetime as dt
from pathlib import Path
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from . import store
from .search import build_keywords, location_terms, filter_listings, same_street, rank
from .sources import SOURCES, parse_manual_text
from .sources.htmlimport import parse_saved_html
from .stats import summarize
from .textnorm import AdminMap
from .export import to_xlsx

BASE = Path(__file__).resolve().parent
app = FastAPI(title="Khảo giá tài sản bảo đảm")
tpl = Jinja2Templates(directory=str(BASE / "templates"))
admin = AdminMap(BASE.parent / "data" / "admin_mapping.csv")
LAND = {"": "Tất cả", "ONT": "Đất ở nông thôn (ONT)", "ODT": "Đất ở đô thị (ODT)", "CLN": "Cây lâu năm (CLN)",
        "BHK": "Cây hàng năm (BHK/LUC)", "RSX": "Đất rừng sản xuất (RSX)", "NTS": "Nuôi trồng thuỷ sản", "NN": "Nông nghiệp khác"}

def fmt(v):
    return f"{v:,.0f}".replace(",", ".") if v else "-"
tpl.env.filters["vnd"] = fmt

def recent(items, months):
    """Bỏ tin đăng quá `months` tháng (0 = không giới hạn). Tin không rõ ngày đăng vẫn giữ."""
    if not months:
        return items
    cut = (dt.datetime.now() - dt.timedelta(days=30 * months)).isoformat(timespec="seconds")
    return [l for l in items if not l.posted_at or l.posted_at >= cut]

def evaluate(q: dict):
    groups = location_terms(admin, q["xa"], q["huyen"], q["tinh"])
    allr = store.load_all()
    rec = recent(allr, q["months"])
    loc = filter_listings(rec, groups, need=q["need"])
    items = filter_listings(rec, groups, need=q["need"], area=q["area"] or None, tol=q["tol"] / 100,
                            land_type=q["land_type"])
    q["funnel"] = [("Tổng số tin đã lưu trong máy", len(allr)), (f"Còn lại sau lọc thời gian ({q['months']} tháng)", len(rec)),
                   ("Còn lại sau lọc địa danh", len(loc)),
                   (f"Còn lại sau lọc diện tích (±{q['tol']:.0f}%) và loại đất", len(items))]
    items = rank(items, q["duong"], q["area"] or None)
    ss = [l for l in items if q["duong"] and same_street(l, q["duong"])]
    d = q["discount"] / 100
    if len(ss) >= 3:   # đủ tin cùng đường: ưu tiên làm cơ sở tính
        res, basis = summarize(ss, discount=d), "street"
    else:
        res, basis = summarize(items, discount=d), "area"
    return items, res, ss, basis

def qdict(xa, huyen, tinh, area, land_type, discount, need, duong="", months=0, tol=50):
    return dict(tol=tol, months=months, duong=duong.strip(), xa=xa.strip(), huyen=huyen.strip(), tinh=tinh.strip(), area=area or 0,
                land_type=land_type, discount=discount, need=need)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return tpl.TemplateResponse(request, "index.html", dict(land=LAND, q=None, items=None, res=None,
                                aliases=None, errors=[], ss=[], basis="", sources=list(SOURCES)))

@app.post("/search", response_class=HTMLResponse)
def search(request: Request, duong: str = Form(""), xa: str = Form(""), huyen: str = Form(""), tinh: str = Form("Gia Lai"),
           area: float = Form(0), land_type: str = Form(""), discount: float = Form(10),
           need: int = Form(1), live: str = Form(""),
           months: int = Form(12), maxn: int = Form(200), tol: float = Form(50)):
    q = qdict(xa, huyen, tinh, area, land_type, discount, need, duong, months, tol)
    q["maxn"] = maxn
    q["fetchlog"] = []
    errors = []
    if live:
        # từ khoá tìm: dùng cả tên cũ và mới của xã/huyện để không bỏ sót
        # Từ khoá ngắn (chỉ địa danh) cho kết quả rộng hơn từ khoá dài; lọc chính xác làm ở bước sau
        kws = set()
        for x in (xa, huyen):
            if x.strip():
                kws.add(x.strip())
        if duong.strip():
            kws.add(f"{duong.strip()} {xa.strip() or huyen.strip()}".strip())
        for a in admin.aliases(xa) | admin.aliases(huyen):
            kws.add(a)
        for name, src in SOURCES.items():
            if hasattr(src, "discover_regions"):
                # Lọc theo khu vực (đầy đủ hơn tìm theo từ khoá, vì nhiều tin không ghi địa danh trong tiêu đề)
                try:
                    regs = src.discover_regions([x for x in (xa, huyen, tinh) if x.strip()])
                    for code, rname in regs.items():
                        got = src.search_region(code, limit=maxn, max_age_days=30 * months or None)
                        store.save(got)
                        q["fetchlog"].append(f"{name} · toàn bộ đất khu vực '{rname}' (mã {code}): lấy về {len(got)} tin")
                    if not regs:
                        q["fetchlog"].append(f"{name}: không xác định được mã khu vực từ địa danh đã nhập")
                except Exception as e:
                    errors.append(f"Nguồn {name} (lọc khu vực): {e}")
            for kw in kws:
                try:
                    got = src.search(kw, limit=maxn, max_age_days=30 * months or None)
                    store.save(got)
                    q["fetchlog"].append(f"{name} · '{kw}': lấy về {len(got)} tin")
                except Exception as e:
                    errors.append(f"Nguồn {name} (từ khoá '{kw}'): {e}")
    items, res, ss, basis = evaluate(q)
    shown = [sorted(admin.aliases(x)) for x in (xa, huyen) if x.strip()]
    return tpl.TemplateResponse(request, "index.html", dict(land=LAND, q=q, items=items, res=res,
                                aliases=shown, errors=errors, ss=ss, basis=basis, sources=list(SOURCES)))

@app.post("/import-html", response_class=HTMLResponse)
async def import_html(request: Request, files: list[UploadFile] = File(...), only_land: str = Form("1")):
    report = []
    for f in files:
        raw = (await f.read()).decode("utf-8", errors="replace")
        kind, items = parse_saved_html(raw, only_land=bool(only_land))
        if not kind:
            report.append((f.filename, "Không nhận diện được (hỗ trợ: alonhadat, batdongsan, thuviennhadat, raobannhadat)", 0))
            continue
        store.save(items)
        report.append((f.filename, kind, len(items)))
    return tpl.TemplateResponse(request, "imported.html", dict(report=report))

@app.post("/paste", response_class=HTMLResponse)
def paste(request: Request, text: str = Form(...), url: str = Form(""), address: str = Form("")):
    l = parse_manual_text(text, url=url, address=address)
    store.save([l])
    return tpl.TemplateResponse(request, "pasted.html", dict(l=l))

@app.get("/export.xlsx")
def export(duong: str = "", xa: str = "", huyen: str = "", tinh: str = "Gia Lai", area: float = 0, land_type: str = "",
           discount: float = 10, need: int = 1, months: int = 12, tol: float = 50):
    q = qdict(xa, huyen, tinh, area, land_type, discount, need, duong, months, tol)
    items, res, ss, basis = evaluate(q)
    data = to_xlsx(q, items, res, ss)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=khao-gia.xlsx"})
