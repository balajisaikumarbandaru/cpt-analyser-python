"""Plots with matplotlib.

* :func:`plot_log` – the printable CPT log page (international or Dutch standard,
  multi-page, SBT column, title block). Drawn in millimetres on an A4/A3 page with
  the same layout as the HTML tool.
* :func:`plot_sbt_chart` – Robertson (1990) Qt–Fr chart.
* :func:`plot_dissipation` – dissipation test.
* :func:`plot_compare` – several CPTs side by side (tile) or in one graph (overlay).
* :func:`save_log_pdf` – all pages of one or more CPTs into a single PDF.
"""
from __future__ import annotations

import math

from matplotlib.figure import Figure
from matplotlib.patches import Polygon, Rectangle

from ._js import clamp, fin, log10
from .constants import GREY_ZONE, IC_BANDS, SIGNALS, ZONES
from .models import CPT, Dissipation
from .processing import settings_for, shift_on
from .settings import Settings
from .ticks import fmt, nice_step, tick_fmt, ticks

MM2PT = 72 / 25.4
FONT = ["Arial", "Helvetica", "DejaVu Sans"]
ANCHOR = {"start": "left", "middle": "center", "end": "right", None: "left"}
CMP_COLOURS = ["#1d4ed8", "#c0262d", "#0f766e", "#7c3aed", "#d97706", "#0369a1", "#be185d", "#4d7c0f", "#57534e", "#0891b2"]


def signal(c: CPT, k: str):
    """Plot metadata for a key (standard signal or extra file column), or None."""
    return SIGNALS.get(k) or c.raw.x_meta.get(k)


def page_dims(S: Settings):
    P = S.plot
    w, h = (297, 420) if P["size"] == "A3" else (210, 297)
    if P["orient"] == "landscape":
        w, h = h, w
    return w, h


def depth_range(c: CPT, S: Settings):
    P = S.plot
    z = [v for v in c.data["z"] if fin(v)]
    zmax = max(z) if z else 1
    z0 = P["zMin"] if fin(P["zMin"]) else 0
    z1 = P["zMax"] if fin(P["zMax"]) else max(1, math.ceil(zmax + 0.25))
    if z1 <= z0:
        z1 = z0 + 1
    return z0, z1


def plot_pages(c: CPT, settings: Settings | None = None) -> list[dict]:
    """Pages: each distinct track page number × each depth section ("depth per page")."""
    S = settings_for(c, settings)
    P = S.plot
    z0, z1 = depth_range(c, S)
    tp = [1] if P["standard"] == "dutch" else sorted({x["page"] for x in P["tracks"] if signal(c, x["k"])})
    if not tp:
        tp = [1]
    secs = []
    zp = float(P["zPage"] or 0) if fin(P.get("zPage")) else 0
    if zp > 0:
        a = z0
        while a < z1 - 1e-9:
            secs.append((a, min(z1, a + zp)))
            a += zp
    else:
        secs.append((z0, z1))
    return [{"tp": p, "za": s[0], "zb": s[1]} for s in secs for p in tp]


class _Page:
    """A figure whose data coordinates are millimetres from the top-left corner (like the SVG)."""

    def __init__(self, W, H):
        self.fig = Figure(figsize=(W / 25.4, H / 25.4))
        ax = self.fig.add_axes((0, 0, 1, 1))
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)
        ax.axis("off")
        ax.add_patch(Rectangle((0, 0), W, H, facecolor="#fff", edgecolor="none", zorder=-10))
        self.ax = ax

    def clip(self, x, y, w, h):
        r = Rectangle((x, y), w, h, transform=self.ax.transData, fill=False, visible=False)
        self.ax.add_patch(r)
        return r

    def text(self, x, y, s, fs=2.5, a=None, w=None, c="#111", rot=0):
        self.ax.text(x, y, s, fontsize=fs * MM2PT, ha=ANCHOR[a], va="baseline", color=c, family=FONT,
                     fontweight="bold" if w else "normal", rotation=-rot, rotation_mode="anchor", zorder=5)

    def line(self, x1, y1, x2, y2, col="#333", lw=0.2, dash=None, z=2):
        ln, = self.ax.plot([x1, x2], [y1, y2], color=col, lw=lw * MM2PT, solid_capstyle="butt", zorder=z)
        if dash:
            self._dash(ln, dash, lw)

    def rect(self, x, y, w, h, fill="none", stroke="none", lw=0.3, alpha=1.0, z=1):
        self.ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=stroke, lw=lw * MM2PT, alpha=alpha,
                                    zorder=z, joinstyle="miter"))

    def path(self, xs, ys, col, lw, dash=None, clip=None, z=3):
        ln, = self.ax.plot(xs, ys, color=col, lw=lw * MM2PT, solid_joinstyle="round", zorder=z)
        if dash:
            self._dash(ln, dash, lw)
        if clip is not None:
            ln.set_clip_path(clip)

    def poly(self, pts, fill, z=4):
        self.ax.add_patch(Polygon(pts, closed=True, facecolor=fill, edgecolor="none", zorder=z))

    @staticmethod
    def _dash(ln, dash, lw):
        # matplotlib scales dash patterns by the line width; give them in mm like the SVG
        ln.set_dashes([d * MM2PT / max(lw * MM2PT, 1e-6) for d in dash])


def _track_label(c, k, F):
    if k == "Su":
        return f"Su [kPa] Nk {_n(F['nkMin'])}/{_n(F['nkMax'])}"
    if k == "u2":
        return f"{c.data.get('uLoc') or 'u2'}, u0 [MPa]"
    s = signal(c, k)
    return f"{s['sym']} [{s['unit']}]"


def _n(v):
    from ._js import js_str
    return js_str(float(v))


def plot_log(c: CPT, page: int = 0, settings: Settings | None = None, dissipations=()) -> Figure:
    """One printable page of the CPT log. ``dissipations`` are marked on the pore-pressure graph."""
    S = settings_for(c, settings)
    P, F = S.plot, S.factors
    pages = plot_pages(c, S)
    pi = int(clamp(page, 0, len(pages) - 1))
    pg = pages[pi]
    W, H = page_dims(S)
    d, h, mono = c.data, c.header, not P["color"]
    tb = 27
    legend_h = 6 if P["sbt"] else 0
    has_gl = fin(h.gl)
    m = {"l": 17, "r": 17 if has_gl else 8, "t": 9, "b": 8}
    axis_h = 15
    y_top, y_bot = m["t"] + axis_h, H - m["b"] - tb - legend_h - 3
    x0, x1 = m["l"], W - m["r"]
    z0, z1 = pg["za"], pg["zb"]

    def Y(z):
        return y_top + (z - z0) / (z1 - z0) * (y_bot - y_top)

    zarr = d["z"]
    n = len(zarr)
    i0, i1 = 0, n - 1
    while i0 < n - 1 and zarr[i0 + 1] < z0:
        i0 += 1
    while i1 > 0 and zarr[i1 - 1] > z1:
        i1 -= 1
    pgf = _Page(W, H)
    T = pgf.text

    dz = nice_step(z1 - z0, (y_bot - y_top) / 12)
    dz_minor = dz / (5 if dz >= 1 else 2)
    grid = []
    if P["grid"]:
        z = math.ceil(z0 / dz_minor - 1e-9) * dz_minor
        while z <= z1 + 1e-9:
            grid.append((z, abs(z / dz - round(z / dz)) < 1e-6))
            z += dz_minor

    def h_grid(xa, xb):
        for z, major in grid:
            pgf.line(xa, Y(z), xb, Y(z), "#b9c1ca" if major else "#e6e9ed", 0.18 if major else 0.12, z=0.5)

    z = math.ceil(z0 / dz - 1e-9) * dz
    while z <= z1 + 1e-9:
        T(x0 - 1.5, Y(z) + 0.9, tick_fmt(round(z, 6)), a="end")
        if has_gl:
            T(x1 + 1.5, Y(z) + 0.9, f"{h.gl - z:.2f}")
        z += dz
    T(x0 - 11.5, (y_top + y_bot) / 2, "Depth [m BGL]", a="middle", rot=-90, fs=2.7)
    if has_gl:
        T(x1 + 13, (y_top + y_bot) / 2, f"Level [{F['datum']}]", a="middle", rot=90, fs=2.7)
    gwl = h.gwl if h.gwl is not None else float(F["gwlDefault"])
    if z0 <= gwl <= z1:
        yy = Y(gwl)
        pgf.poly([(x0 - 6.5, yy - 2.2), (x0 - 2.5, yy - 2.2), (x0 - 4.5, yy)], "#2b6cb0")
        pgf.line(x0 - 7, yy + 0.4, x0 - 2, yy + 0.4, "#2b6cb0", 0.25)
    strip_w = 9 if P["sbt"] else 0
    strip_gap = 2 if P["sbt"] else 0
    xP = x1 - strip_w - strip_gap

    def series(k):
        return d.get(k) or []

    def xy(vals, X):
        xs, ys = [], []
        for i in range(i0, i1 + 1):
            v = vals[i] if i < len(vals) else math.nan
            x = X(v) if fin(v) else math.nan
            xs.append(x if fin(x) else math.nan)
            ys.append(Y(zarr[i]) if fin(zarr[i]) else math.nan)
        return xs, ys

    if P["standard"] == "dutch":
        L1, L2, R = P["dutch"]["l1"], P["dutch"]["l2"], P["dutch"]["r"]
        clip = pgf.clip(x0, y_top, xP - x0, y_bot - y_top)
        h_grid(x0, xP)
        for j, k in enumerate([k for k in (L1, L2) if signal(c, k)]):
            s, col = S.scale(k, c.raw.x_meta), "#111" if mono else signal(c, k)["col"]
            X = (lambda s: lambda v: x0 + (v - s["min"]) / (s["max"] - s["min"]) * (xP - x0))(s)
            ty = y_top - 9.8 + j * 4.2
            T(x0 - 1.2, ty, f"{signal(c, k)['sym']} [{signal(c, k)['unit']}]", a="end", c=col, w=700, fs=2.1)
            tk = ticks(s["min"], s["max"])
            for ti, v in enumerate(tk):
                xx = X(v)
                if j == 0 and P["grid"]:
                    pgf.line(xx, y_top, xx, y_bot, "#d3d9e0", 0.15, z=0.5)
                T(xx, ty, tick_fmt(v), a="start" if ti == 0 else "end" if ti == len(tk) - 1 else "middle", c=col, fs=2.1)
            pgf.path(*xy(series(k), X), col, 0.32 if j == 0 else 0.26, clip=clip)
        if signal(c, R):
            s, col = S.scale(R, c.raw.x_meta), "#111" if mono else signal(c, R)["col"]
            xr0 = xP - 0.4 * (xP - x0)
            X = lambda v: xP - (v - s["min"]) / (s["max"] - s["min"]) * (xP - xr0)  # noqa: E731
            ty = y_top - 1.4
            T(xr0 - 2.5, ty, f"{signal(c, R)['sym']} [{signal(c, R)['unit']}] ←", a="end", c=col, w=700, fs=2.1)
            tk = ticks(s["min"], s["max"])
            for ti, v in enumerate(tk):
                T(X(v), ty, tick_fmt(v), a="end" if ti == 0 else "start" if ti == len(tk) - 1 else "middle", c=col, fs=2.1)
            pgf.path(*xy(series(R), X), col, 0.26, dash=(1, 0.6) if mono else None, clip=clip)
        pgf.rect(x0, y_top, xP - x0, y_bot - y_top, stroke="#333", lw=0.3, z=4)
    else:
        trs = [x for x in P["tracks"] if signal(c, x["k"]) and x["page"] == pg["tp"]]
        gap = 2.5
        wsum = sum(float(x.get("w") or 1) for x in trs) or 1
        avail = xP - x0 - gap * max(0, len(trs) - 1)
        xa = x0
        for tr in trs:
            k = tr["k"]
            tw = avail * float(tr.get("w") or 1) / wsum
            xb = xa + tw
            s, col = S.scale(k, c.raw.x_meta), "#111" if mono else signal(c, k)["col"]
            lg = bool(s.get("log")) and s["min"] > 0
            if lg:
                X = (lambda xa, tw, s: lambda v: xa + (log10(v) - log10(s["min"])) / (log10(s["max"]) - log10(s["min"])) * tw
                     if v > 0 else math.nan)(xa, tw, s)
            else:
                X = (lambda xa, tw, s: lambda v: xa + (v - s["min"]) / (s["max"] - s["min"]) * tw)(xa, tw, s)
            clip = pgf.clip(xa, y_top, tw, y_bot - y_top)
            if k in ("Ic", "Icn"):
                for lo, hi, zn in IC_BANDS:
                    a2 = clamp(X(max(lo, s["min"])), xa, xb)
                    b2 = clamp(X(min(hi, s["max"])), xa, xb)
                    if b2 > a2 and not mono:
                        pgf.rect(a2, y_top, b2 - a2, y_bot - y_top, fill=ZONES[zn][2], alpha=0.18, z=0.2)
            h_grid(xa, xb)
            T((xa + xb) / 2, y_top - 9.6, _track_label(c, k, F), a="middle", c=col, w=700, fs=2.1 if tw < 22 else 2.4)
            tk = ticks(s["min"], s["max"], lg)
            for ti, v in enumerate(tk):
                xx = X(v)
                if P["grid"]:
                    pgf.line(xx, y_top, xx, y_bot, "#d3d9e0", 0.15, z=0.5)
                if len(tk) <= 6 or ti % 2 == 0 or ti == len(tk) - 1:
                    T(xx, y_top - 1.6, tick_fmt(v), a="start" if ti == 0 else "end" if ti == len(tk) - 1 else "middle", fs=2.0)
            if k in ("u2", "Su"):
                pgf.line(xa, y_top - 5.6, xa + tw * 0.45, y_top - 5.6, col, 0.5)
                pgf.line(xa + tw * 0.55, y_top - 5.6, xb, y_top - 5.6, col, 0.4, dash=(1, 0.7))
            else:
                pgf.line(xa, y_top - 5.6, xb, y_top - 5.6, col, 0.5)
            if k == "u2":
                pgf.path(*xy(d["u0"], X), col, 0.25, dash=(1.2, 0.8), clip=clip)
            if k == "Su":
                pgf.path(*xy(d["Su2"], X), col, 0.25, dash=(1.2, 0.8), clip=clip)
            pgf.path(*xy(series(k), X), col, 0.3, clip=clip)
            if k == "u2":
                import re
                for ds in dissipations or ():
                    if fin(ds.depth) and z0 <= ds.depth <= z1:
                        yy = Y(ds.depth)
                        pgf.poly([(xb - 0.6, yy), (xb - 2.8, yy - 1.4), (xb - 2.8, yy + 1.4)], "#d97706")
                        mm = re.search(r" D(\S+) @", ds.test_id) or re.search(r"D(\S+)", ds.test_id)
                        T(xb - 3.4, yy + 0.8, "D" + (mm.group(1) if mm else ""), a="end", fs=1.9, c="#b45309")
            pgf.rect(xa, y_top, tw, y_bot - y_top, stroke="#333", lw=0.3, z=4)
            xa = xb + gap
        if not trs:
            T((x0 + xP) / 2, (y_top + y_bot) / 2, "No graphs on this page", a="middle", c="#888")
    if P["sbt"]:
        xs = x1 - strip_w
        T(xs + strip_w / 2, y_top - 9.6, "SBT", a="middle", w=700, fs=2.4)
        T(xs + strip_w / 2, y_top - 1.6, "1990", a="middle", fs=2.0)
        zone = d["zone"]
        st = i0
        for i in range(i0, i1 + 2):
            if i > i1 or zone[i] != zone[st]:
                zn = zone[st]
                za = clamp((zarr[st] + zarr[st - 1]) / 2 if st > 0 else zarr[st], z0, z1)
                zb = clamp((zarr[i - 1] + zarr[i]) / 2 if i - 1 < n - 1 else zarr[i - 1], z0, z1)
                if zn and zb > za:
                    pgf.rect(xs, Y(za), strip_w, Y(zb) - Y(za) + 0.05, fill=_zone_fill(zn, mono), z=1)
                st = i
        pgf.rect(xs, y_top, strip_w, y_bot - y_top, stroke="#333", lw=0.3, z=4)
        ly, lw = H - m["b"] - tb - legend_h + 1.5, (x1 - x0) / 9
        for zn in range(1, 10):
            lx = x0 + (zn - 1) * lw
            pgf.rect(lx, ly, 3, 3, fill=_zone_fill(zn, mono), stroke="#555", lw=0.1)
            T(lx + 4, ly + 2.4, f"{zn} {ZONES[zn][1]}", fs=2.0)
    # title block
    by, bx0, bx1 = H - m["b"] - tb, 8, W - 8
    cw, rh = (bx1 - bx0) / 4, tb / 3
    pgf.rect(bx0, by, bx1 - bx0, tb, stroke="#333", lw=0.35)
    for r in (1, 2):
        pgf.line(bx0, by + r * rh, bx1, by + r * rh, "#333", 0.2)
    for q in (1, 2, 3):
        pgf.line(bx0 + q * cw, by, bx0 + q * cw, by + tb, "#333", 0.2)
    zs = [v for v in zarr if fin(v)]
    z_end = max(zs) if zs else math.nan
    alpha = h.alpha if h.alpha is not None else float(F["alphaDefault"])
    corr = f"α={fmt(alpha, 2)}, {d.get('uLoc') or 'u2'}{', fs shift' if shift_on(c, F) else ''}" \
           f"{', incl.' if F['inclCorr'] else ''}, filter {_n(F['filterPasses'])}×"
    cells = [
        (F["company"] or "Cone penetration test", h.test_id),
        ("Project", h.project or h.job_no), ("Location", h.location), ("Date", h.date),
        ("Coordinates (E / N)", f"{fmt(h.x, 2)} / {fmt(h.y, 2)}" if fin(h.x) else "–"),
        ("Ground level", f"{fmt(h.gl, 3)} {F['datum']}" if fin(h.gl) else "–"),
        ("Water level", f"{fmt(gwl, 2)} m BGL{' (default)' if h.gwl is None else ''}"),
        ("Final depth", f"{fmt(z_end, 2)} m"),
        ("Cone", h.cone_type or "–"), ("Pre-drill", f"{fmt(h.predrill or 0, 2)} m"),
        ("Corrections", corr),
        ("Page", f"{pi + 1} / {len(pages)} · {'Dutch' if P['standard'] == 'dutch' else 'International'} · {P['size']} · z {fmt(z0, 1)}–{fmt(z1, 1)} m"),
    ]
    for k, (lab, val) in enumerate(cells):
        cx, cy = bx0 + (k % 4) * cw + 1.6, by + (k // 4) * rh
        if k == 0:
            T(cx, cy + 3.1, lab, fs=2.1, c="#555")
            T(cx, cy + 7.6, val, fs=3.6, w=700)
        else:
            T(cx, cy + 3.1, lab, fs=2.0, c="#555")
            T(cx, cy + 7.1, str(val if val not in (None, "") else "–")[:46], fs=2.6)
    return pgf.fig


def _zone_fill(zn, mono):
    if mono:
        g = GREY_ZONE[zn] / 255
        return (g, g, g)
    return ZONES[zn][2]


def plot_log_pages(c: CPT, settings: Settings | None = None, dissipations=()) -> list[Figure]:
    return [plot_log(c, i, settings, dissipations) for i in range(len(plot_pages(c, settings)))]


def save_log_pdf(cpts, path, settings: Settings | None = None, collection=None) -> None:
    """Every page of every CPT into one PDF (like *Print all*)."""
    from matplotlib.backends.backend_pdf import PdfPages
    if isinstance(cpts, CPT):
        cpts = [cpts]
    with PdfPages(path) as pdf:
        for c in cpts:
            diss = collection.dissipations_for(c) if collection is not None else ()
            for fig in plot_log_pages(c, settings, diss):
                pdf.savefig(fig)


# --------------------------------------------------------------------------- Robertson chart
def _depth_colour(t):
    t = clamp(t, 0, 1)
    a, b = (245, 158, 11), (37, 99, 235)
    return tuple((a[i] + (b[i] - a[i]) * t) / 255 for i in range(3))


def plot_sbt_chart(c: CPT, settings: Settings | None = None, ax=None):
    """Robertson (1990) normalised Qt–Fr chart with every sample, coloured by depth or zone."""
    S = settings_for(c, settings)
    fig = None
    if ax is None:
        fig = Figure(figsize=(6.2, 6))
        ax = fig.add_subplot(111)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.1, 10)
    ax.set_ylim(1, 1000)
    edge = dict(color="0.35", lw=1.2, alpha=0.8)
    for ic in (1.31, 2.05, 2.6, 2.95, 3.6):
        xs, ys = [], []
        for j in range(201):
            lf = -1 + j * 0.01
            dx = lf + 1.22
            if abs(dx) > ic:
                continue
            lq = 3.47 - math.sqrt(ic * ic - dx * dx)
            if 0 <= lq <= 3:
                xs.append(10 ** lf)
                ys.append(10 ** lq)
        ax.plot(xs, ys, **edge)
    f1 = [f for f in (0.1 * 1.03 ** j for j in range(200)) if f <= 10 and 12 * math.exp(-1.4 * f) >= 1]
    ax.plot(f1, [12 * math.exp(-1.4 * f) for f in f1], **edge)   # zone 1 boundary
    xs, ys = [], []
    f = 1.5
    while f <= 10:
        x = f - 1
        den = 0.005 * x - 0.0003 * x * x - 0.002
        if den > 0 and 1 / den <= 1000:
            xs.append(f)
            ys.append(1 / den)
        f *= 1.01
    ax.plot(xs, ys, **edge)
    x = 3.5
    ax.plot([4.5, 4.5], [1 / (0.005 * x - 0.0003 * x * x - 0.002), 1000], **edge)
    d = c.data
    z0, z1 = depth_range(c, S)
    px, py, pc = [], [], []
    for i in range(len(d["z"])):
        Q, Fr, z = d["Qt"][i], d["Fr"][i], d["z"][i]
        if not (Q > 0 and Fr > 0) or z < z0 or z > z1:
            continue
        px.append(clamp(Fr, 0.1, 10))
        py.append(clamp(Q, 1, 1000))
        pc.append(ZONES[d["zone"][i]][2] if S.plot["chartColour"] == "zone" else _depth_colour((z - z0) / (z1 - z0)))
    ax.scatter(px, py, s=10, c=pc, alpha=0.8, linewidths=0, zorder=3)
    for zn, Fv, Qv in [(1, 0.25, 2.6), (2, 6, 1.5), (3, 5, 4.5), (4, 2.6, 14), (5, 1.1, 40), (6, 0.45, 150), (7, 0.18, 600), (8, 2.6, 520), (9, 7, 280)]:
        ax.scatter([Fv], [Qv], s=240, c=[ZONES[zn][2]], edgecolors="white", linewidths=1.5, zorder=4)
        ax.text(Fv, Qv, str(zn), ha="center", va="center", fontweight="bold", color="white" if zn in (2, 9) else "#111", zorder=5)
    ax.set_xlabel("Normalised friction ratio Fr = fs / (qt − σv) × 100 [%]")
    ax.set_ylabel("Normalised cone resistance Qt = (qt − σv) / σ'v")
    ax.set_title(f"{c.test_id} – Robertson (1990)")
    ax.grid(True, which="both", alpha=0.15)
    return fig or ax.figure


# --------------------------------------------------------------------------- dissipation
def plot_dissipation(D: Dissipation, ax=None):
    """u against time (log, √t or linear per ``D.options['axis']``) with u0, ui, u50, t50 and t<pct>."""
    o, R = D.options, D.result
    fig = None
    if ax is None:
        fig = Figure(figsize=(9, 5.6))
        ax = fig.add_subplot(111)
    axis = o["axis"]
    t = list(D.t)
    if axis == "sqrt":
        tx = [math.sqrt(max(v, 0)) for v in t]
        ax.set_xlabel("√Time [√s]")
    else:
        tx = t
        ax.set_xlabel("Time [s]" + (" (log)" if axis == "log" else ""))
        if axis == "log":
            ax.set_xscale("log")
            tx = [v if v > 0 else math.nan for v in t]

    def X(v):
        return math.sqrt(max(v, 0)) if axis == "sqrt" else v

    ax.plot(tx, [v * 1000 for v in D.u], color="#0f766e", lw=2, label=D.loc)
    for val, col, lab in ((R["u0"], "#2b6cb0", "u0"), (R["ui"], "#64748b", "ui"), (R["u50"], "#d97706", "u50")):
        if fin(val):
            ax.axhline(val * 1000, color=col, ls="--", lw=1)
            ax.annotate(f"{lab} = {fmt(val * 1000, 1)} kPa", xy=(1, val * 1000), xycoords=("axes fraction", "data"),
                        xytext=(-4, 3), textcoords="offset points", ha="right", color=col, fontsize=9, zorder=6,
                        bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.8))
    for j, (tv, lab) in enumerate(((R["t50"], "t50"), (R["tp"], f"t{o['pct']}"))):
        if fin(tv) and tv > 0:
            ax.axvline(X(tv), color="#d97706", lw=1)
            ax.annotate(f"{lab} = {fmt(tv, 0)} s", xy=(X(tv), 0.06 + 0.07 * j), xycoords=("data", "axes fraction"),
                        xytext=(4, 0), textcoords="offset points", color="#d97706", fontsize=9, zorder=6,
                        bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.8))
    ax.set_ylabel(f"{D.loc} [kPa]", color="#0f766e")
    if o.get("show_qc") and any(fin(v) for v in D.qc):
        a2 = ax.twinx()
        a2.plot(tx, D.qc, color="#1d4ed8", lw=1.2, alpha=0.7)
        a2.set_ylabel("qc [MPa]", color="#1d4ed8")
        a2.set_ylim(bottom=0)
        ax.set_zorder(a2.get_zorder() + 1)   # u and its labels in front of the qc line
        ax.patch.set_visible(False)
    ch = R.get("ch")
    ax.set_title(f"{D.test_id}" + (f"   ch = {ch:.3g} m²/s" if fin(ch) else ""))
    ax.grid(True, which="both", alpha=0.15)
    return fig or ax.figure


# --------------------------------------------------------------------------- compare
def plot_compare(cpts, key: str = "qc", mode: str = "tile", settings: Settings | None = None):
    """Compare CPTs: ``mode='tile'`` (one graph per CPT with SBT strip) or ``'overlay'``."""
    S = settings or Settings()
    cpts = [c for c in cpts if c.kind == "cpt"]
    s = S.scale(key)
    lg = bool(s.get("log")) and s["min"] > 0
    zmax = max([1] + [max([v for v in c.data["z"] if fin(v)] or [0]) for c in cpts])
    z0 = S.plot["zMin"] if fin(S.plot["zMin"]) else 0
    z1 = S.plot["zMax"] if fin(S.plot["zMax"]) else math.ceil(zmax + 0.25)
    sig = SIGNALS.get(key) or {"sym": key, "unit": "", "col": "#1d4ed8"}
    label = f"{sig['sym']} [{sig['unit']}]"
    if mode == "tile":
        n = max(1, len(cpts))
        fig = Figure(figsize=(max(7, 1 + 1.6 * n), 7.6))
        gs = fig.add_gridspec(1, 2 * n, width_ratios=[5, 1] * n, wspace=0.08)
        for j, c in enumerate(cpts):
            ax = fig.add_subplot(gs[0, 2 * j])
            ax.plot(c.data.get(key, []), c.data["z"], color=sig["col"], lw=1.1)
            ax.set_xscale("log" if lg else "linear")
            ax.set_xlim(s["min"], s["max"])
            ax.set_ylim(z1, z0)
            ax.set_title(c.test_id, fontsize=10, fontweight="bold")
            ax.set_xlabel(label, color=sig["col"], fontsize=9)
            ax.xaxis.set_label_position("top")
            ax.xaxis.tick_top()
            ax.grid(True, alpha=0.15)
            if j:
                ax.tick_params(labelleft=False)
            else:
                ax.set_ylabel("Depth [m BGL]")
            sx = fig.add_subplot(gs[0, 2 * j + 1], sharey=ax)
            _zone_strip(sx, c)
            sx.set_ylim(z1, z0)
        return fig
    fig = Figure(figsize=(9, 7.6))
    ax = fig.add_subplot(111)
    for j, c in enumerate(cpts):
        ax.plot(c.data.get(key, []), c.data["z"], color=CMP_COLOURS[j % len(CMP_COLOURS)], lw=1.2, label=c.test_id)
    ax.set_xscale("log" if lg else "linear")
    ax.set_xlim(s["min"], s["max"])
    ax.set_ylim(z1, z0)
    ax.set_xlabel(label)
    ax.xaxis.set_label_position("top")
    ax.xaxis.tick_top()
    ax.set_ylabel("Depth [m BGL]")
    ax.grid(True, alpha=0.15)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=5, frameon=False)
    return fig


def _zone_strip(ax, c: CPT):
    d = c.data
    z, zone = d["z"], d["zone"]
    n = len(z)
    st = 0
    for i in range(n + 1):
        if i == n or zone[i] != zone[st]:
            zn = zone[st]
            za, zb = z[st], z[i] if i < n else z[n - 1]
            if zn and zb > za:
                ax.axhspan(za, zb, color=ZONES[zn][2], lw=0)
            st = i
    ax.set_xticks([])
    ax.tick_params(labelleft=False)
