from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from . import store
from .search import build_keywords, location_terms, filter_listings
from .sources import SOURCES, parse_manual_text
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

def evaluate(q: dict):
    groups = location_terms(admin, q["xa"], q["huyen"], q["tinh"])
    items = filter_listings(store.load_all(), groups, need=q["need"], area=q["area"] or None,
                            land_type=q["land_type"])
    items.sort(key=lambda l: l.price_per_m2 or 0)
    return items, summarize(items, discount=q["discount"] / 100)

def qdict(xa, huyen, tinh, area, land_type, discount, need):
    return dict(xa=xa.strip(), huyen=huyen.strip(), tinh=tinh.strip(), area=area or 0,
                land_type=land_type, discount=discount, need=need)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return tpl.TemplateResponse(request, "index.html", dict(land=LAND, q=None, items=None, res=None,
                                aliases=None, errors=[], sources=list(SOURCES)))

@app.post("/search", response_class=HTMLResponse)
def search(request: Request, xa: str = Form(""), huyen: str = Form(""), tinh: str = Form("Gia Lai"),
           area: float = Form(0), land_type: str = Form(""), discount: float = Form(10),
           need: int = Form(1), live: str = Form("")):
    q = qdict(xa, huyen, tinh, area, land_type, discount, need)
    errors = []
    if live:
        # từ khoá tìm: dùng cả tên cũ và mới của xã/huyện để không bỏ sót
        kws = {build_keywords(xa, huyen, tinh)}
        for a in admin.aliases(xa) | admin.aliases(huyen):
            kws.add(a)
        for name, src in SOURCES.items():
            for kw in kws:
                try:
                    store.save(src.search(kw, limit=40))
                except Exception as e:
                    errors.append(f"Nguồn {name} (từ khoá '{kw}'): {e}")
    items, res = evaluate(q)
    shown = [sorted(admin.aliases(x)) for x in (xa, huyen) if x.strip()]
    return tpl.TemplateResponse(request, "index.html", dict(land=LAND, q=q, items=items, res=res,
                                aliases=shown, errors=errors, sources=list(SOURCES)))

@app.post("/paste", response_class=HTMLResponse)
def paste(request: Request, text: str = Form(...), url: str = Form(""), address: str = Form("")):
    l = parse_manual_text(text, url=url, address=address)
    store.save([l])
    return tpl.TemplateResponse(request, "pasted.html", dict(l=l))

@app.get("/export.xlsx")
def export(xa: str = "", huyen: str = "", tinh: str = "Gia Lai", area: float = 0, land_type: str = "",
           discount: float = 10, need: int = 1):
    q = qdict(xa, huyen, tinh, area, land_type, discount, need)
    items, res = evaluate(q)
    data = to_xlsx(q, items, res)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=khao-gia.xlsx"})
