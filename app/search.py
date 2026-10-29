from .models import Listing
from .textnorm import AdminMap, norm, contains_phrase

def location_terms(admin: AdminMap, xa: str, huyen: str, tinh: str):
    return [admin.aliases(x) for x in (xa, huyen, tinh) if x.strip()]

def build_keywords(xa: str, huyen: str, tinh: str) -> str:
    return " ".join(x for x in (xa, huyen, tinh) if x.strip())

def matches_location(l: Listing, groups: list[set[str]], need: int) -> bool:
    """Tin phải khớp ít nhất `need` cấp (xã/huyện/tỉnh), mỗi cấp khớp bất kỳ tên cũ hoặc mới."""
    hay = norm(l.address + " " + l.title + " " + l.description)
    hits = sum(any(contains_phrase(hay, a) for a in g) for g in groups)
    return hits >= min(need, len(groups))

def filter_listings(items, groups, need=1, area=None, tol=0.5, land_type="", frontage_min=None):
    out = []
    for l in items:
        if groups and not matches_location(l, groups, need):
            continue
        if area and l.area_m2 and not (area * (1 - tol) <= l.area_m2 <= area * (1 + tol)):
            continue
        if land_type and l.land_type and l.land_type != land_type:
            continue
        out.append(l)
    # bỏ trùng: cùng giá + diện tích + (url hoặc tiêu đề)
    seen, uniq = set(), []
    for l in out:
        key = (l.price_vnd, l.area_m2, norm(l.title)[:40])
        if key in seen or (l.url and ("u", l.url) in seen):
            continue
        seen.add(key); seen.add(("u", l.url)); uniq.append(l)
    return uniq
