"""GEF reader: GEF-CPT-Report and GEF-DISS-Report files."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .._js import NAN, base_name, fin, js_number, js_str, num, opt_num
from ..constants import EXTRA_COLOURS, SIGNALS
from ..models import CPT, Dissipation, Header, RawData
from ..ticks import nice_step


@dataclass
class GefLayout:
    """What is needed to write the file back unchanged except for edited values."""
    header_lines: list
    tok: list
    data_lines: list
    row_idx: list
    map: dict
    scale: dict
    col_sep: str | None
    rec_sep: str | None
    voids: dict
    h0: Header


def gef_header(text: str):
    lines = re.split(r"\r?\n", text)
    H: dict[str, list[str]] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*#\s*([A-Za-z0-9_]+)\s*=\s*(.*)$", lines[i])
        if m:
            k = m.group(1).upper()
            H.setdefault(k, []).append(m.group(2).strip())
            if k == "EOH":
                i += 1
                break
        i += 1
    return H, lines, i


def parts(v: str) -> list[str]:
    return [s.strip() for s in v.split(",")]


def _first(H, k):
    return (H.get(k) or [""])[0]


def gef_common_header(H: dict, fname: str) -> Header:
    MT, MV = {}, {}
    for v in H.get("MEASUREMENTTEXT", []):
        p = parts(v)
        MT[js_number(p[0])] = ", ".join(p[1:-1]) if len(p) > 2 else (p[1] if len(p) > 1 else "")
    for v in H.get("MEASUREMENTVAR", []):
        p = parts(v)
        MV[js_number(p[0])] = num(p[1]) if len(p) > 1 else NAN
    h = Header()
    h.test_id = _first(H, "TESTID") or base_name(fname)
    h.job_no = _first(H, "PROJECTID").split(",")[0].strip()
    h.project = MT.get(2) or _first(H, "PROJECTNAME") or h.job_no
    h.client = MT.get(1) or ""
    h.location = MT.get(3) or ""
    h.cone_type = MT.get(4) or ""
    h.remarks = "; ".join(x for x in (MT.get(20), MT.get(21), MT.get(22), MT.get(23)) if x)
    if H.get("STARTDATE"):
        p = [js_number(x) for x in parts(H["STARTDATE"][0])]
        if len(p) >= 3:
            h.date = f"{js_str(p[0])}-{js_str(p[1]).rjust(2, '0')}-{js_str(p[2]).rjust(2, '0')}"
    if H.get("XYID"):
        p = parts(H["XYID"][0])
        h.x = opt_num(p[1] if len(p) > 1 else None)
        h.y = opt_num(p[2] if len(p) > 2 else None)
    if H.get("ZID"):
        p = parts(H["ZID"][0])
        h.gl = opt_num(p[1] if len(p) > 1 else None)
    if fin(MV.get(1)):
        h.cone_area = MV[1]
    if fin(MV.get(3)):
        h.alpha = MV[3]
    if fin(MV.get(4)):
        h.beta = MV[4]
    if fin(MV.get(5)):
        h.sleeve = MV[5] / 1000
    if fin(MV.get(13)):
        h.predrill = MV[13]
    if fin(MV.get(14)):
        h.gwl = abs(MV[14])   # CPTask writes the water level as negative metres below ground
    return h


def _columns(H):
    cols: list = []
    for v in H.get("COLUMNINFO", []):
        p = parts(v)
        ci = int(js_number(p[0])) - 1
        while len(cols) <= ci:
            cols.append(None)
        cols[ci] = {"unit": p[1] if len(p) > 1 else "", "name": p[2] if len(p) > 2 else "",
                    "q": js_number(p[3]) if len(p) > 3 else NAN}
    voids = {}
    for v in H.get("COLUMNVOID", []):
        p = parts(v)
        voids[int(js_number(p[0])) - 1] = js_number(p[1]) if len(p) > 1 else NAN
    return cols, voids


def parse_gef(text: str, fname: str = "file.gef"):
    """Parse GEF text. Returns a :class:`CPT` or, for dissipation reports, a :class:`Dissipation`."""
    H, lines, i0 = gef_header(text)
    if "EOH" not in H:
        raise ValueError("No #EOH= found – not a GEF file")
    rc = _first(H, "REPORTCODE").upper()
    report = (_first(H, "REPORTCODE") + " " + _first(H, "PROCEDURECODE")).upper()
    if "DISS" in rc or ("DISS" in report and "CPT-REPORT" not in rc):
        return parse_diss(H, lines, i0, fname)

    header_lines = lines[:i0]
    cols, voids = _columns(H)
    col_sep = H["COLUMNSEPARATOR"][0] if H.get("COLUMNSEPARATOR") else None
    rec_sep = H["RECORDSEPARATOR"][0] if H.get("RECORDSEPARATOR") else None
    tok, data_lines = [], []
    for raw_line in lines[i0:]:
        ln = raw_line.strip()
        if not ln:
            continue
        if rec_sep and ln.endswith(rec_sep):
            ln = ln[: -len(rec_sep)].strip()
        tt = [s.strip() for s in ln.split(col_sep)] if col_sep else re.split(r"\s+", ln)
        if len(tt) < 2:
            continue
        tok.append(tt)
        data_lines.append(raw_line)

    def val(row, ci):
        if ci is None or ci >= len(row):
            return NAN
        v = num(row[ci])
        if not fin(v):
            return NAN
        if voids.get(ci) is not None and abs(v - voids[ci]) < 1e-6:
            return NAN
        return v

    def by_q(q):
        return next((i for i, c in enumerate(cols) if c and c["q"] == q), -1)

    def by_name(pattern):
        rx = re.compile(pattern, re.I | re.ASCII)
        return next((i for i, c in enumerate(cols) if c and rx.search(c["name"])), -1)

    def pick(*c):
        return next((x for x in c if x >= 0), None)

    m = {
        "L": pick(by_q(1), by_name(r"length|depth"), 0),
        "qc": pick(by_q(2), by_name(r"^qc$|cone res")),
        "fs": pick(by_q(3), by_name(r"^fs$|sleeve|local fric")),
        "u1": pick(by_q(5), by_name(r"^u1$")), "u2": pick(by_q(6), by_name(r"^u2?$")), "u3": pick(by_q(7), by_name(r"^u3$")),
        "I": pick(by_q(8)), "Ix": pick(by_q(9)), "Iy": pick(by_q(10)),
        "zc": pick(by_q(11)), "t": pick(by_q(12)),
        "Qst": pick(by_name(r"total friction|^qst$")), "Qtot": pick(by_name(r"total force|^qt\b.*kn|^qtot")),
    }
    if m["Qtot"] is not None and cols[m["Qtot"]] and not re.search("kn", cols[m["Qtot"]]["unit"], re.I) \
            and not re.search("total force", cols[m["Qtot"]]["name"], re.I):
        m["Qtot"] = None
    scale = {k: 1e-3 if m[k] is not None and re.search("kpa", cols[m[k]]["unit"], re.I) else 1
             for k in ("qc", "fs", "u1", "u2", "u3")}
    # other measured columns become extra plottable signals
    used = {v for v in m.values() if v is not None}
    derived_q = {4, 13, 14, 15, 16, 17, 18, 19, 20}
    extras = []
    for ci, c in enumerate(cols):
        if c and ci not in used and c["q"] not in derived_q:
            key = "x_" + re.sub(r"\W+", "_", c["name"], flags=re.ASCII).lower()[:24]
            extras.append({"ci": ci, "key": key, "name": c["name"], "unit": c["unit"]})

    raw = RawData()
    raw.zc = []
    if m["Qst"] is not None:
        raw.x["Qst"] = []
    if m["Qtot"] is not None:
        raw.x["Qtot"] = []
    for e in extras:
        raw.x[e["key"]] = []
    row_idx = []
    for ri, row in enumerate(tok):
        L = val(row, m["L"])
        if not fin(L):
            continue
        row_idx.append(ri)
        raw.L.append(L)
        for k in ("qc", "fs", "u1", "u2", "u3"):
            getattr(raw, k).append(val(row, m[k]) * scale[k])
        I = val(row, m["I"])
        if not fin(I) and m["Ix"] is not None and m["Iy"] is not None:
            a, b = val(row, m["Ix"]) * math.pi / 180, val(row, m["Iy"]) * math.pi / 180
            I = _acos(math.cos(a) * math.cos(b)) * 180 / math.pi if fin(a) and fin(b) else NAN
        raw.I.append(I)
        raw.t.append(val(row, m["t"]))
        raw.zc.append(val(row, m["zc"]))
        if m["Qst"] is not None:
            raw.x["Qst"].append(val(row, m["Qst"]))
        if m["Qtot"] is not None:
            raw.x["Qtot"].append(val(row, m["Qtot"]))
        for e in extras:
            raw.x[e["key"]].append(val(row, e["ci"]))
    if not any(fin(v) for v in raw.zc):
        raw.zc = None
    for e in extras:
        m[e["key"]] = e["ci"]
        raw.x_meta[e["key"]] = extra_meta(e["name"], e["unit"], raw.x[e["key"]], len(raw.x_meta))
    h = gef_common_header(H, fname)
    layout = GefLayout(header_lines, tok, data_lines, row_idx, m, scale, col_sep, rec_sep, voids, h.copy())
    return CPT(fname, h, raw, "gef", gef=layout)


def extra_meta(name, unit, vals, n_before=0) -> dict:
    """Plot defaults for a column that is not one of the standard signals (``registerExtra``)."""
    f = [v for v in vals if fin(v)]
    lo, hi = (min(f), max(f)) if f else (0, 1)
    if hi <= lo:
        hi = lo + 1
    st = nice_step(hi - lo, 4)
    lo, hi = math.floor(lo / st) * st, math.ceil(hi / st) * st
    return {"name": name, "sym": name, "unit": unit, "col": EXTRA_COLOURS[n_before % len(EXTRA_COLOURS)],
            "default": (lo, hi), "log": False, "extra": True}


def _acos(x):
    return math.acos(x) if -1 <= x <= 1 else NAN


def parse_diss(H, lines, i, fname) -> Dissipation:
    """GEF-DISS-Report: pore pressure dissipation test."""
    cols, voids = _columns(H)

    def fi(test):
        return next((k for k, c in enumerate(cols) if c and test(c)), -1)

    ct = fi(lambda c: re.search("time", c["name"], re.I) or re.fullmatch(r"s(ec)?", c["unit"], re.I))
    cu = fi(lambda c: c["q"] in (5, 6, 7) or re.search(r"pore|^u", c["name"], re.I))
    cq = fi(lambda c: c["q"] == 2 or re.search(r"cone|^qc", c["name"], re.I))
    us = 1e-3 if cu >= 0 and re.search("kpa", cols[cu]["unit"], re.I) else 1
    T, U, Q = [], [], []
    for line in lines[i:]:
        tt = re.split(r"[\s;]+", re.sub(r"!$", "", line.strip()))
        if len(tt) < 2:
            continue

        def g(ci):
            if ci < 0 or ci >= len(tt):
                return NAN
            v = num(tt[ci])
            return v if fin(v) and not (voids.get(ci) is not None and abs(v - voids[ci]) < 1e-6) else NAN

        tv = g(ct)
        if not fin(tv):
            continue
        T.append(tv)
        U.append(g(cu) * us)
        Q.append(g(cq))
    if not T:
        raise ValueError("No dissipation data found")
    h = gef_common_header(H, fname)
    depth, parent = None, ""
    if H.get("PARENT"):
        p = parts(H["PARENT"][0])
        parent = p[0]
        depth = opt_num(p[1] if len(p) > 1 else None)
    uq = cols[cu]["q"] if cu >= 0 else 6
    loc = "u1" if uq == 5 else "u3" if uq == 7 else "u2"
    if depth is not None and "@" not in h.test_id:
        h.test_id = f"{base_name(parent or fname)} D{h.test_id} @{js_str(depth)} m"
    return Dissipation(fname, h, T, U, Q, depth=depth, parent=parent, loc=loc)


__all__ = ["parse_gef", "gef_header", "gef_common_header", "GefLayout", "SIGNALS"]
