"""Turn diplomacy/maps/svg/standard.svg into frontend/src/map/standard.json.

standard.svg has seven traps, every one of which fails silently. Each is handled
here and then asserted, so a bad build fails loudly instead of shipping a wrong map:

  1. MapLayer carries transform="translate(-195 -170)"; the supply-centre,
     unit and label anchors sit OUTSIDE that group. Unhandled, every province
     renders 195px right and 170px below its own units.
  2. The gaps between province polygons ARE the borders -- MapLayer opens with a
     solid black rect and the polygons sit on top with ~5px between them. The
     renderer must paint that backing; nothing here needs a stroke.
  3. Four shapes carry no province id (unplayable = Iceland/Ireland, plus
     unplayable_water, denmark_water, constantinople_water) and are interleaved
     among the sea polygons. Filtering by id drops them and leaves black holes.
  4. Five sea provinces use SVG ids the engine does not know: MID/MAO, GOL/LYO,
     TYN/TYS, NAT/NAO, NRG/NWG. Resolve through the engine's own alias table.
  5. Supply-centre markers are <use> elements in SupplyCenterLayer, not in
     PROVINCE_DATA, and x/y is the top-left of a 20x20 box, so add 10.
  6. Three label anchors (ROM, POR, SKA) parse to junk from legend text.
  7. Five sea labels are multi-word and miss a three-letter text scan.
"""
from __future__ import annotations
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))

import diplomacy

SVG = os.path.join(os.path.dirname(diplomacy.__file__), "maps", "svg", "standard.svg")
OUT = os.path.join(ROOT, "frontend", "src", "map", "standard.json")

NUM = re.compile(r"-?\d+\.?\d*")


def shift(path: str, dx: float, dy: float) -> str:
    """Bake a translate into absolute path data. standard.svg uses only M/C/z."""
    assert not set(re.findall(r"[A-Za-z]", path)) - set("MCz"), "unexpected path command"
    nums = [float(x) for x in NUM.findall(path)]
    assert len(nums) % 2 == 0, "odd coordinate count"
    pts = iter([(x + dx, y + dy) for x, y in zip(nums[0::2], nums[1::2])])
    state = {"i": 0, "cur": None}

    def rep(_m):
        if state["i"] % 2 == 0:
            state["cur"] = next(pts)
        v = state["cur"][state["i"] % 2]
        state["i"] += 1
        return f"{v:g}"

    return NUM.sub(rep, path)


def flatten(path: str) -> list[list[tuple[float, float]]]:
    """Turn M/C/z path data into polylines, one per subpath."""
    toks = re.findall(r"[MCz]|-?\d+\.?\d*", path)
    subs, cur, i = [], [], 0
    pt = (0.0, 0.0)
    while i < len(toks):
        t = toks[i]
        if t == "M":
            if cur:
                subs.append(cur)
            pt = (float(toks[i + 1]), float(toks[i + 2]))
            cur = [pt]
            i += 3
        elif t == "C":
            p1 = (float(toks[i + 1]), float(toks[i + 2]))
            p2 = (float(toks[i + 3]), float(toks[i + 4]))
            p3 = (float(toks[i + 5]), float(toks[i + 6]))
            for k in range(1, 9):
                u = k / 8.0
                m = 1 - u
                cur.append((
                    m*m*m*pt[0] + 3*m*m*u*p1[0] + 3*m*u*u*p2[0] + u*u*u*p3[0],
                    m*m*m*pt[1] + 3*m*m*u*p1[1] + 3*m*u*u*p2[1] + u*u*u*p3[1],
                ))
            pt = p3
            i += 7
        else:
            i += 1
    if cur:
        subs.append(cur)
    return [c for c in subs if len(c) > 2]


def _area(poly) -> float:
    a = 0.0
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return abs(a) / 2


def _inside(poly, x, y) -> bool:
    c = False
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i - 1) % len(poly)]
        if ((y0 > y) != (y1 > y)) and (x < (x1 - x0) * (y - y0) / ((y1 - y0) or 1e-9) + x0):
            c = not c
    return c


def _edge_dist(poly, x, y) -> float:
    best = 1e18
    for i in range(len(poly)):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % len(poly)]
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x0) * dx + (y - y0) * dy) / L2))
        ex, ey = x0 + t * dx, y0 + t * dy
        d = (x - ex) ** 2 + (y - ey) ** 2
        if d < best:
            best = d
    return best ** 0.5


def interior_point(path: str):
    """The point furthest from any edge -- a label sits here without bleeding out.
    Uses the largest subpath, so island provinces label their mainland."""
    subs = flatten(path)
    if not subs:
        return None, 0.0
    poly = max(subs, key=_area)
    xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    best, bd = None, -1.0
    for step, (ax0, ax1, ay0, ay1) in ((28, (x0, x1, y0, y1)),):
        nx = max(6, int((ax1 - ax0) / max((ax1 - ax0) / step, 1)))
        for i in range(step + 1):
            for j in range(step + 1):
                x = ax0 + (ax1 - ax0) * i / step
                y = ay0 + (ay1 - ay0) * j / step
                if not _inside(poly, x, y):
                    continue
                d = _edge_dist(poly, x, y)
                if d > bd:
                    bd, best = d, (x, y)
    if best is None:
        return None, 0.0
    # refine around the winner
    span = (x1 - x0) / 28
    cx, cy = best
    for i in range(-4, 5):
        for j in range(-4, 5):
            x, y = cx + span * i / 4, cy + span * j / 4
            if _inside(poly, x, y):
                d = _edge_dist(poly, x, y)
                if d > bd:
                    bd, best = d, (x, y)
    return [round(best[0], 1), round(best[1], 1)], round(bd, 1)


def bbox(path: str):
    n = [float(x) for x in NUM.findall(path)]
    return min(n[0::2]), min(n[1::2]), max(n[0::2]), max(n[1::2])


def main() -> int:
    svg = open(SVG).read()
    game = diplomacy.Game()
    dmap = game.map

    # ---- trap 1: the MapLayer transform -------------------------------------
    m = re.search(r'<g id="MapLayer"[^>]*transform="translate\(([-\d.]+)\s+([-\d.]+)\)"', svg)
    assert m, "MapLayer transform not found - the file changed, re-check every offset"
    DX, DY = float(m.group(1)), float(m.group(2))

    layer_src = svg[svg.index('<g id="MapLayer"'): svg.index('<g id="SupplyCenterLayer"')]

    # ---- trap 2: the black backing --------------------------------------------
    backing = re.search(r'<rect fill="(\w+)" height="(\d+)" width="(\d+)" x="(\d+)" y="(\d+)"/>', layer_src)
    assert backing, "MapLayer backing rect not found - borders come from it"
    view_w, view_h = int(backing.group(3)), int(backing.group(2))

    # ---- trap 4: engine names -------------------------------------------------
    def resolve(svg_id: str) -> str:
        name = svg_id.upper().replace("-", "/")
        base = name.split("/")[0]
        real = dmap.aliases.get(base, base)
        return real + ("/" + name.split("/")[1] if "/" in name else "")

    # ---- trap 3: every shape, in document order, id or not --------------------
    layer = []
    for sm in re.finditer(r"<(path|polygon)\s+([^>]*?)/>", layer_src):
        attrs = sm.group(2)
        cls_m = re.search(r'class="([^"]*)"', attrs)
        id_m = re.search(r'id="([^"]*)"', attrs)
        d_m = re.search(r'(?:d|points)="([^"]*)"', attrs)
        if not (cls_m and d_m):
            continue
        sid = id_m.group(1) if id_m else None
        prov = resolve(sid[1:]) if sid and re.fullmatch(r"_[a-z]{3}(-[a-z]{2})?", sid) else None
        layer.append({"p": prov, "c": cls_m.group(1), "d": shift(d_m.group(1), DX, DY)})

    # ---- anchors (already in the untransformed space) --------------------------
    pdata = re.search(r"<jdipNS:PROVINCE_DATA>(.*?)</jdipNS:PROVINCE_DATA>", svg, re.S).group(1)
    anchors: dict[str, dict] = {}
    for pm in re.finditer(r'<jdipNS:PROVINCE name="([^"]+)"(.*?)</jdipNS:PROVINCE>', pdata, re.S):
        name, body = resolve(pm.group(1)), pm.group(2)
        e = {}
        for tag, key in (("UNIT", "unit"), ("DISLODGED_UNIT", "dislodged")):
            am = re.search(r"<jdipNS:" + tag + r'\b[^>]*?x="([\d.-]+)"[^>]*?y="([\d.-]+)"', body)
            if am:
                e[key] = [round(float(am.group(1)), 1), round(float(am.group(2)), 1)]
        if e:
            anchors[name] = e

    # ---- trap 5: supply-centre markers -----------------------------------------
    sc_dot = {}
    for um in re.finditer(r'<use height="(\d+)" id="sc_([A-Z]{3})" width="\d+" x="([\d.]+)"[^>]*y="([\d.]+)"', svg):
        half = int(um.group(1)) / 2
        sc_dot[resolve(um.group(2))] = [round(float(um.group(3)) + half, 1),
                                        round(float(um.group(4)) + half, 1)]

    # ---- traps 6 + 7: labels ---------------------------------------------------
    labels = {}
    for tm in re.finditer(r'<text[^>]*?x="([\d.]+)"[^>]*?y="([\d.]+)"[^>]*?>([A-Za-z][A-Za-z ]{1,})</text>', svg):
        key = resolve(tm.group(3).strip().replace(" ", "")[:3])
        labels.setdefault(key, [round(float(tm.group(1)), 1), round(float(tm.group(2)), 1)])

    # ---- display names: the reference board labels provinces in full ----------
    # The original SVG only carries three-letter codes, but the engine's alias
    # table has the long forms. A few need hand-cleaning.
    import collections
    inv = collections.defaultdict(list)
    for alias, abbr in dmap.aliases.items():
        inv[abbr].append(alias)
    NICE = {
        "LYO": "Gulf of Lyon", "BOT": "Gulf of Bothnia", "MAO": "Mid-Atlantic Ocean",
        "NAO": "North Atlantic Ocean", "STP": "St Petersburg", "HEL": "Heligoland Bight",
        "ENG": "English Channel", "NTH": "North Sea", "NWG": "Norwegian Sea",
        "TYS": "Tyrrhenian Sea", "EAS": "Eastern Mediterranean", "WES": "Western Mediterranean",
        "GAL": "Galicia", "BUL": "Bulgaria", "SKA": "Skagerrak", "BAR": "Barents Sea",
        "BLA": "Black Sea", "AEG": "Aegean Sea", "ADR": "Adriatic Sea", "ION": "Ionian Sea",
        "BAL": "Baltic Sea", "IRI": "Irish Sea", "NAF": "North Africa", "SWI": "Switzerland",
    }
    def display(abbr: str) -> str:
        if abbr in NICE:
            return NICE[abbr]
        cands = [a for a in inv.get(abbr, []) if a.isalpha() or " " in a]
        if not cands:
            return abbr.title()
        best = max(cands, key=len).replace("\\", " ").replace("  ", " ").strip()
        return " ".join(w.capitalize() for w in best.split())

    home_of = {h: p for p, hs in dmap.homes.items() for h in hs}
    provinces = {}
    for e in layer:
        pid = e["p"]
        if pid is None or pid in provinces:
            continue
        base = pid.split("/")[0]
        a = anchors.get(pid, anchors.get(base, {}))
        x0, y0, x1, y1 = bbox(e["d"])
        # The SVG's own label anchors were placed for a different rendering and
        # several sit outside their province or right on a border. Compute the
        # point furthest from any edge instead, so a label always sits inside the
        # region it names. Keep the SVG anchor only as a sanity comparison.
        lb, clearance = interior_point(e["d"])
        svg_lb = labels.get(base)
        if lb is None:
            lb = svg_lb or ([a["unit"][0], a["unit"][1] + 34] if a.get("unit") else None)
            clearance = 0.0
        provinces[pid] = {
            "kind": {"nopower": "land", "water": "sea", "impassable": "shut"}[e["c"]],
            "locType": dmap.loc_type.get(pid) or dmap.loc_type.get(base),
            "sc": base in dmap.scs,
            "home": home_of.get(base),
            "unit": a.get("unit"),
            "dislodged": a.get("dislodged"),
            "scDot": sc_dot.get(base),
            "label": lb,
            "labelClearance": clearance,   # distance from the label to the nearest border
            "name": display(base),
            "box": [round(x1 - x0, 1), round(y1 - y0, 1)],
            "coasts": sorted(k.split("/")[1] for k in anchors if k.startswith(base + "/")),
        }

    # ---- pull labels apart ----------------------------------------------------
    # The interior point is the most central spot in a province, which is also
    # where its unit sits, and in a crowded corner like Britain two neighbouring
    # centres land within a label's width of each other. Relax the label positions
    # against each other and against the unit tokens, never leaving the province.
    LBL_W, LBL_H = 46.0, 26.0          # a three-letter code at size 25
    UNIT_W, UNIT_H = 34.0, 34.0
    polys = {}
    for e in layer:
        if e["p"] and e["p"] in provinces and provinces[e["p"]]["label"]:
            subs = flatten(e["d"])
            if subs:
                polys[e["p"]] = max(subs, key=_area)

    movable = [pid for pid in provinces if provinces[pid]["label"] and pid in polys]
    obstacles = [(v["unit"], UNIT_W, UNIT_H) for v in provinces.values() if v.get("unit")]

    def overlap(ax, ay, aw, ah, bx, by, bw, bh):
        ox = (aw + bw) / 2 - abs(ax - bx)
        oy = (ah + bh) / 2 - abs(ay - by)
        return (ox, oy) if ox > 0 and oy > 0 else None

    for _ in range(90):
        moved = False
        for i, pid in enumerate(movable):
            lx, ly = provinces[pid]["label"]
            dx = dy = 0.0
            for other in movable[i + 1:]:
                ox_, oy_ = provinces[other]["label"]
                ov = overlap(lx, ly, LBL_W, LBL_H, ox_, oy_, LBL_W, LBL_H)
                if ov:
                    push = (ov[1] * 0.5) if ov[1] < ov[0] else (ov[0] * 0.5)
                    if ov[1] < ov[0]:
                        dy += push if ly >= oy_ else -push
                    else:
                        dx += push if lx >= ox_ else -push
            for (ux, uy), uw, uh in obstacles:
                ov = overlap(lx, ly, LBL_W, LBL_H, ux, uy, uw, uh)
                if ov:
                    dy += (ov[1] * 0.6) if ly >= uy else -(ov[1] * 0.6)
            if dx or dy:
                nx, ny = lx + max(-6.0, min(6.0, dx)), ly + max(-6.0, min(6.0, dy))
                poly = polys[pid]
                if _inside(poly, nx, ny) and _edge_dist(poly, nx, ny) >= 5:
                    provinces[pid]["label"] = [round(nx, 1), round(ny, 1)]
                    provinces[pid]["labelClearance"] = round(_edge_dist(poly, nx, ny), 1)
                    moved = True
        if not moved:
            break

    # report what could not be separated
    clashes = 0
    for i, a in enumerate(movable):
        ax, ay = provinces[a]["label"]
        for b in movable[i + 1:]:
            bx, by = provinces[b]["label"]
            if overlap(ax, ay, LBL_W, LBL_H, bx, by, LBL_W, LBL_H):
                clashes += 1

    coast_anchors = {k: v for k, v in anchors.items() if "/" in k}

    # ---- assertions: fail loudly, never ship a wrong map -----------------------
    errs = []
    if len(provinces) != 76:
        errs.append(f"expected 76 provinces, got {len(provinces)}")
    if sum(1 for v in provinces.values() if v["sc"]) != 34:
        errs.append("expected 34 supply centres")
    decor = [e for e in layer if e["p"] is None]
    if len(decor) != 4:
        errs.append(f"expected 4 decorative shapes, got {len(decor)}")
    eng_locs = {l.upper().split("/")[0] for l in dmap.locs}
    unknown = {p.split("/")[0] for p in provinces} - eng_locs
    if unknown:
        errs.append(f"provinces the engine does not know: {sorted(unknown)}")
    for pid, v in provinces.items():
        if not v["unit"]:
            errs.append(f"{pid}: no unit anchor")
            continue
        shape = next(e["d"] for e in layer if e["p"] == pid)
        x0, y0, x1, y1 = bbox(shape)
        ux, uy = v["unit"]
        if not (x0 - 2 <= ux <= x1 + 2 and y0 - 2 <= uy <= y1 + 2):
            errs.append(f"{pid}: unit anchor {v['unit']} outside its own shape - transform wrong")
        if v["sc"] and not v["scDot"]:
            errs.append(f"{pid}: supply centre with no marker position")
        if not v["label"]:
            errs.append(f"{pid}: no label anchor")
        if not v["name"] or v["name"] == pid:
            errs.append(f"{pid}: no display name")
    if errs:
        print("BUILD FAILED:", file=sys.stderr)
        for e in errs[:20]:
            print("  -", e, file=sys.stderr)
        return 1

    # Frame from actual content: every label, unit anchor and centre marker, plus
    # the land and the seas that touch it, with a margin. Hand-tuning this cut off
    # Syria, the eastern Mediterranean and North Africa.
    pts = []
    for v in provinces.values():
        for k in ("unit", "scDot", "label"):
            if v.get(k):
                pts.append(v[k])
    for e in layer:
        if e["c"] in ("nopower", "impassable", "neutral"):
            bx0, by0, bx1, by1 = bbox(e["d"])
            pts += [[bx0, by0], [bx1, by1]]
    mx0 = min(p[0] for p in pts); mx1 = max(p[0] for p in pts)
    my0 = min(p[1] for p in pts); my1 = max(p[1] for p in pts)
    pad = 26
    fit = [round(mx0 - pad), round(my0 - pad),
           round(mx1 - mx0 + pad * 2), round(my1 - my0 + pad * 2)]

    out = {
        "viewBox": [0, 0, view_w, view_h],
        "viewBoxFit": fit,
        "backing": True,
        "provinces": provinces,
        "coastAnchors": coast_anchors,
        "layer": layer,
        "homes": {p: sorted(h) for p, h in dmap.homes.items()},
        "startUnits": {p: sorted(game.powers[p].units) for p in sorted(game.powers)},
        "startCenters": {p: sorted(game.powers[p].centers) for p in sorted(game.powers)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"ok: {len(provinces)} provinces, {sum(1 for v in provinces.values() if v['sc'])} centres, "
          f"{len(layer)} layer shapes ({len(decor)} decorative), {len(coast_anchors)} coast anchors")
    print(f"    transform translate({DX:g} {DY:g}) baked in; all anchor assertions passed")
    tight = [v for v in provinces.values() if v["labelClearance"] < 6]
    print(f"    labels: interior point, then relaxed apart -- {clashes} remaining overlap(s), "
          f"{len(tight)} under 6 units of border clearance; viewBoxFit {fit}")
    print(f"    -> {os.path.relpath(OUT, ROOT)} ({os.path.getsize(OUT)//1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
