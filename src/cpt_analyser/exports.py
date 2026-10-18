"""Data exports: CSV, layer summary, Excel and GEF (same layout as the HTML tool)."""
from __future__ import annotations

import datetime as _dt
import io
import re
import zipfile
from pathlib import Path

from ._js import fin, safe_name, to_precision
from .constants import SIGNALS, ZONES
from .models import CPT, Dissipation
from .processing import settings_for, shift_on
from .settings import Settings
from .ticks import fmt


def data_columns(c: CPT, settings: Settings | None = None):
    """(key, label, unit, decimals, is_raw) for every column of the data table."""
    F = settings_for(c, settings).factors
    loc = c.data.get("uLoc", "u2")
    cols = [("z", "Depth", "m", 2, False), ("L", "Length", "m", 2, False),
            ("qc", "qc raw", "MPa", 3, True), ("fs", "fs raw", "MPa", 4, True), (loc, f"{loc} raw", "MPa", 4, True),
            ("I", "I raw", "°", 2, True)]
    for k in c.raw.x:
        meta = SIGNALS.get(k) or c.raw.x_meta.get(k)
        cols.append((k, meta["sym"] if meta else k, meta["unit"] if meta else "", 3, True))
    cols += [("qc", "qc", "MPa", 3, False), ("fs", "fs shifted" if shift_on(c, F) else "fs", "MPa", 4, False),
             ("u2", loc, "MPa", 4, False), ("Rf", "Rf", "%", 2, False), ("qt", "qt", "MPa", 3, False),
             ("u0", "u0", "MPa", 4, False), ("du", "Δu", "MPa", 4, False), ("uqc", "u/qc", "-", 3, False),
             ("qe", "qe", "MPa", 3, False), ("gam", "γ", "kN/m³", 1, False), ("sv", "σv", "kPa", 1, False),
             ("svp", "σ'v", "kPa", 1, False), ("qn", "qn", "MPa", 3, False), ("Bq", "Bq", "-", 3, False),
             ("Qt", "Qt", "-", 1, False), ("Fr", "Fr", "%", 2, False), ("Ic", "Ic", "-", 2, False),
             ("zone", "SBT", "zone", 0, False), ("Icn", "Ic (2009)", "-", 2, False), ("Qtn", "Qtn", "-", 1, False),
             ("DrNC", "Dr NC", "%", 0, False), ("DrOC", "Dr OC", "%", 0, False), ("phi", "φ", "°", 1, False),
             ("Su", "Su Nkmin", "kPa", 0, False), ("Su2", "Su Nkmax", "kPa", 0, False), ("N60", "N60", "-", 0, False),
             ("v", "v", "cm/s", 2, False)]
    return cols


def _value(c: CPT, key, raw, i):
    arr = c.raw.channel(key) if raw else c.data.get(key, [])
    return arr[i] if i < len(arr) else None


# ---------------------------------------------------------------- CSV
def to_csv(c, settings: Settings | None = None, with_id: bool = False) -> str:
    if c.kind == "diss":
        lines = [("Test ID," if with_id else "") + f"Time [s],{c.loc} [MPa],qc [MPa]"]
        for tv, u, q in zip(c.t, c.u, c.qc):
            lines.append((f'"{c.test_id}",' if with_id else "") + ",".join(_jsnum(v) if fin(v) else "" for v in (tv, u, q)))
        return "\n".join(lines)
    cols = data_columns(c, settings)
    head = (["Test ID"] if with_id else []) + [f'"{label} [{unit}]"' for _k, label, unit, _dp, _r in cols]
    lines = [",".join(head)]
    for i in range(len(c.data["z"])):
        row = []
        for k, _l, _u, dp, raw in cols:
            v = _value(c, k, raw, i)
            row.append(str(v or "") if k == "zone" else f"{v:.{max(dp, 3)}f}" if fin(v) else "")
        lines.append(",".join(([f'"{c.test_id}"'] if with_id else []) + row))
    return "\n".join(lines)


def _jsnum(v):
    from ._js import js_str
    return js_str(float(v))


def csv_all(cpts, settings: Settings | None = None) -> str:
    """One CSV with a Test ID column for all CPTs."""
    parts = []
    for j, c in enumerate(x for x in cpts if x.kind == "cpt"):
        s = to_csv(c, settings, with_id=True)
        parts.append(s if j == 0 else "\n".join(s.split("\n")[1:]))
    return "\n".join(parts)


LAYER_HEAD = ["Top [m]", "Bottom [m]", "Thickness [m]", "SBT zone", "Description", "qc [MPa]", "fs [kPa]", "Rf [%]",
              "Ic", "Dr [%]", "phi [deg]", "Su Nkmax [kPa]", "Su Nkmin [kPa]", "N60"]


def layers_csv(cpts) -> str:
    lines = ["Test ID," + ",".join(LAYER_HEAD)]
    for c in cpts:
        for lay in getattr(c, "layers", []) or []:
            vals = [f'"{c.test_id}"', fmt(lay["top"], 2), fmt(lay["bottom"], 2), fmt(lay["bottom"] - lay["top"], 2),
                    str(lay["zone"]), f'"{ZONES[lay["zone"]][0]}"', fmt(lay["qc"], 3), fmt(lay["fs"] * 1000, 1),
                    fmt(lay["Rf"], 2), fmt(lay["Ic"], 2), fmt(lay["Dr"], 0), fmt(lay["phi"], 1), fmt(lay["Su2"], 0),
                    fmt(lay["Su"], 0), fmt(lay["N60"], 0)]
            lines.append(",".join("" if v == "–" else v for v in vals))
    return "\n".join(lines)


# ---------------------------------------------------------------- Excel
def excel_sheets(c, settings: Settings | None = None) -> list[tuple[str, list]]:
    S = settings_for(c, settings)
    F = S.factors
    h = c.header
    zs = [v for v in (c.data.get("z", []) if c.kind == "cpt" else []) if fin(v)]
    header = [["Client Name", h.project or h.client], ["Job Number", h.job_no], ["Sounding Number", h.test_id],
              ["Cone Number", h.cone_type], ["Location", h.location], ["Date", h.date],
              ["Water level", h.gwl if h.gwl is not None else float(F["gwlDefault"]), "mBGL", "(meter Below Ground Level)"],
              ["Ground level", h.gl, F["datum"]], ["Predrill", h.predrill or 0],
              ["Penetration Depth", max(zs) if zs else None, "mBGL"], ["Remarks", h.remarks],
              ["E Coordinate", h.x, "Easting (m)"], ["N Coordinate", h.y, "Northing (m)"],
              ["Alpha Factor", h.alpha if h.alpha is not None else float(F["alphaDefault"])],
              ["Beta Factor", h.beta if h.beta is not None else 1], ["Source file", c.file]]
    if c.kind == "diss":
        data = [["Time [s]", f"{c.loc} [MPa]", "qc [MPa]"]] + [[_cellv(a), _cellv(b), _cellv(q)] for a, b, q in zip(c.t, c.u, c.qc)]
        return [("Header", header), ("Data", data)]
    cols = data_columns(c, S)
    rows = [[f"{label} [{unit}]" for _k, label, unit, _dp, _r in cols]]
    for i in range(len(c.data["z"])):
        rows.append([to_precision(v, 8) if fin(v) else None for v in (_value(c, k, raw, i) for k, _l, _u, _d, raw in cols)])
    lay = [LAYER_HEAD]
    for L in c.layers:
        vals = [L["top"], L["bottom"], L["bottom"] - L["top"], L["zone"], ZONES[L["zone"]][0], L["qc"], L["fs"] * 1000,
                L["Rf"], L["Ic"], L["Dr"], L["phi"], L["Su2"], L["Su"], L["N60"]]
        lay.append([(to_precision(v, 6) if fin(v) else None) if isinstance(v, (int, float)) else v for v in vals])
    return [("Header", header), ("Data", rows), ("Layers", lay)]


def _cellv(v):
    return v if fin(v) else None


def to_excel(c, path=None, settings: Settings | None = None) -> bytes:
    """Write an .xlsx with Header, Data and Layers sheets. Returns the bytes (and writes ``path`` if given)."""
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in excel_sheets(c, settings):
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append([None if (isinstance(v, float) and not fin(v)) else v for v in r])
    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()
    if path:
        Path(path).write_bytes(data)
    return data


# ---------------------------------------------------------------- GEF
def _e4(v):
    """JS ``toExponential(4)`` (e.g. 1.2340e+1)."""
    m, e = f"{v:.4e}".split("e")
    return f"{m}e{'-' if e.startswith('-') else '+'}{int(e.lstrip('+-'))}"


def to_gef(c, settings: Settings | None = None, today: _dt.date | None = None) -> str:
    """GEF text. Files opened from GEF keep their exact layout; only edited values and
    changed header fields are rewritten. Other sources get a fresh GEF-CPT file."""
    today = today or _dt.date.today()
    ymd = f"{today.year}, {today.month}, {today.day}"
    h = c.header
    S = settings_for(c, settings)
    F = S.factors
    if isinstance(c, Dissipation):
        loc_q = 5 if c.loc == "u1" else 7 if c.loc == "u3" else 6
        out = ["#GEFID= 1, 1, 0", "#FILEOWNER= CPT Analyser", f"#FILEDATE= {ymd}", f"#PROJECTID= {h.job_no or '-'}",
               "#COLUMN= 3", "#COLUMNINFO= 1, s, Time, 21", f"#COLUMNINFO= 2, MPa, Pore pressure, {loc_q}",
               "#COLUMNINFO= 3, MPa, Cone resistance, 2", f"#LASTSCAN= {len(c.t)}",
               f"#PARENT= {c.parent or '-'}, {_jsnum(c.depth) if fin(c.depth) else 0}, m, penetration length, 1, # of test",
               "#REPORTCODE= GEF-DISS-Report, 1, 0, 0, -", f"#TESTID= {h.test_id}", "#EOH="]
        out += [" ".join(_e4(v) if fin(v) else "-9999" for v in row) for row in zip(c.t, c.u, c.qc)]
        return "\r\n".join(out) + "\r\n"

    edited = c.edited()
    if c.gef is not None:
        g = c.gef
        out = []
        h0 = g.h0
        fmap = {"testId": "test_id", "gl": "gl", "x": "x", "y": "y", "client": "client", "project": "project",
                "location": "location", "coneType": "cone_type", "alpha": "alpha", "beta": "beta",
                "predrill": "predrill", "gwl": "gwl"}

        def changed(*ks):
            return any(getattr(h, fmap[k]) != getattr(h0, fmap[k]) for k in ks)

        def rep(ln, key, fn):
            m = re.match(r"^\s*#" + key + r"\s*=\s*(.*)$", ln, re.I)
            return fn([s.strip() for s in m.group(1).split(",")]) if m else None

        def mtext(p):
            k = int(float(p[0])) if p[0].strip().lstrip("-").isdigit() else None
            f = {1: "client", 2: "project", 3: "location", 4: "coneType"}.get(k)
            return f"#MEASUREMENTTEXT= {k}, {getattr(h, fmap[f])}, {p[-1]}" if f and changed(f) else None

        def mvar(p):
            k = int(float(p[0])) if p[0].strip().lstrip("-").isdigit() else None
            f = {3: "alpha", 4: "beta", 13: "predrill", 14: "gwl"}.get(k)
            if not f or not changed(f) or not fin(getattr(h, fmap[f])):
                return None
            v = -h.gwl if f == "gwl" else getattr(h, fmap[f])
            return f"#MEASUREMENTVAR= {k}, {v:.6f}, {', '.join(p[2:])}"

        for ln in g.header_lines:
            r = None
            if re.match(r"^\s*#EOH", ln, re.I):
                out.append(f"#COMMENT= Saved with CPT Analyser {today.isoformat()}"
                           + (f", {len(edited)} value(s) edited" if edited else ""))
                out.append(ln)
                continue
            if changed("testId"):
                r = r or rep(ln, "TESTID", lambda p: f"#TESTID= {h.test_id}")
            if changed("gl"):
                r = r or rep(ln, "ZID", lambda p: f"#ZID= {p[0]}, {h.gl:.3f}" + (", " + ", ".join(p[2:]) if len(p) > 2 else "")
                             if fin(h.gl) else None)
            if changed("x", "y"):
                r = r or rep(ln, "XYID", lambda p: f"#XYID= {p[0]}, {h.x:.3f}, {h.y:.3f}" + (", " + ", ".join(p[3:]) if len(p) > 3 else "")
                             if fin(h.x) and fin(h.y) else None)
            r = r or rep(ln, "MEASUREMENTTEXT", mtext)
            r = r or rep(ln, "MEASUREMENTVAR", mvar)
            out.append(r if r is not None else ln)
        row_of = {ri: i for i, ri in enumerate(g.row_idx)}
        keys = [k for k, v in g.map.items() if v is not None and k in c.original]
        for ri, tt in enumerate(g.tok):
            i = row_of.get(ri)
            edits = [] if i is None else [k for k in keys if (k, i) in edited]
            if not edits:
                out.append(g.data_lines[ri])
                continue
            row = list(tt)
            for k in edits:
                v = c.raw.channel(k)[i]
                ci = g.map[k]
                while len(row) <= ci:
                    row.append("")
                row[ci] = f"{v / (g.scale.get(k) or 1):.4f}" if fin(v) else _jsnum(g.voids.get(ci, -9999))
            if g.col_sep:
                out.append(g.col_sep.join(row) + (g.rec_sep or ""))
                continue
            line = g.data_lines[ri]
            seg = re.findall(r"\s*\S+", line)
            out.append("".join(row[ci].rjust(len(s)) if ci < len(row) and row[ci] != tt[ci] else s
                               for ci, s in enumerate(seg)) + re.search(r"\s*$", line).group(0))
        return "\r\n".join(out) + "\r\n"

    # new / GME / CSV / Excel sources: write a fresh GEF-CPT file
    r = c.raw
    n = len(r.L)
    loc = c.data.get("uLoc", "u2")

    def V(v):
        return f"{v:.4f}" if fin(v) else "-9999.0000"

    cols = [("L", "m", "penetration length", 1), ("qc", "MPa", "qc", 2), ("fs", "MPa", "fs", 3)]
    if any(fin(v) for v in getattr(r, loc)) or c.source == "new":
        cols.append((loc, "MPa", loc, {"u1": 5, "u2": 6, "u3": 7}[loc]))
    if any(fin(v) for v in r.I):
        cols.append(("I", "degrees", "inclination", 8))
    if any(fin(v) for v in r.t):
        cols.append(("t", "s", "SampleTime", 12))
    if "Qst" in r.x:
        cols.append(("Qst", "kN", "total friction", 0))
    if "Qtot" in r.x:
        cols.append(("Qtot", "kN", "total force", 0))
    alpha = h.alpha if h.alpha is not None else float(F["alphaDefault"])
    sleeve = h.sleeve if h.sleeve is not None else float(F["sleeveDefault"])
    out = ["#GEFID= 1, 1, 0", "#FILEOWNER= CPT Analyser", f"#FILEDATE= {ymd}", f"#PROJECTID= {h.job_no or h.project or '-'}",
           f"#COLUMN= {len(cols)}"]
    out += [f"#COLUMNINFO= {i + 1}, {u}, {name}, {q or 99}" for i, (_k, u, name, q) in enumerate(cols)]
    out += [f"#COLUMNVOID= {i + 1}, -9999.000000" for i in range(len(cols))]
    out += [f"#LASTSCAN= {n}",
            f"#XYID= 0, {f'{h.x:.3f}' if fin(h.x) else '0'}, {f'{h.y:.3f}' if fin(h.y) else '0'}",
            f"#ZID= 0, {f'{h.gl:.3f}' if fin(h.gl) else '0'}",
            f"#MEASUREMENTTEXT= 1, {h.client or ''}, Client", f"#MEASUREMENTTEXT= 2, {h.project or ''}, Name of the project",
            f"#MEASUREMENTTEXT= 3, {h.location or ''}, Location", f"#MEASUREMENTTEXT= 4, {h.cone_type or ''}, Cone Type"]
    if h.remarks:
        out.append(f"#MEASUREMENTTEXT= 22, {h.remarks}, Remarks (1)")
    out += [f"#MEASUREMENTVAR= 3, {alpha:.6f}, -, Net surface area quotient of cone tip",
            f"#MEASUREMENTVAR= 5, {sleeve * 1000:.6f}, mm, Cone distance to centre of friction casing",
            f"#MEASUREMENTVAR= 13, {(h.predrill or 0):.6f}, m, Pre-excavated depth"]
    if h.gwl is not None:
        out.append(f"#MEASUREMENTVAR= 14, {-h.gwl:.6f}, m, WaterLevel")
    if h.date:
        out.append(f"#STARTDATE= {re.sub(r'-0?', ', ', h.date)}")
    out += [f"#COMMENT= {'Converted from GME raw data; fs not shifted' if c.source == 'gme' else 'Written by CPT Analyser'}",
            "#PROCEDURECODE= GEF-CPT-Report, 1, 1, 0, -", "#REPORTCODE= GEF-CPT-Report, 1, 1, 0, -",
            f"#TESTID= {h.test_id}", "#EOH="]
    for i in range(n):
        vals = [f"{r.L[i]:.2f}" if k == "L" else V(r.t[i] if k == "t" else r.channel(k)[i]) for k, *_ in cols]
        out.append(" ".join(s.rjust(10) for s in vals))
    return "\r\n".join(out) + "\r\n"


def save_gef(c, path, settings: Settings | None = None) -> Path:
    """Write :func:`to_gef` to ``path`` in the encoding of the source file."""
    path = Path(path)
    path.write_bytes(to_gef(c, settings).encode(getattr(c, "encoding", "utf-8"), errors="replace"))
    return path


# ---------------------------------------------------------------- zip helpers
def zip_bytes(files: dict[str, str | bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def file_stem(c) -> str:
    return safe_name(c.test_id)
