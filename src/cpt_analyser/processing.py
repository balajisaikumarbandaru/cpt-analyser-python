"""Processing: spike filter, fs shift, depth correction, derived parameters,
Robertson (1990) soil behaviour type, layering and dissipation tests.

Every function mirrors the one of the same name in ``CPT_Analyser.html`` so the
two tools give the same numbers. All equations are listed in ``docs/EQUATIONS.md``.
"""
from __future__ import annotations

import math

from ._js import NAN, base_name, clamp, fin, jmax, jmin, ln, log10, pow_, sqrt
from .constants import PA
from .models import CPT, Dissipation
from .settings import Settings


def median(a) -> float:
    b = sorted(v for v in a if fin(v))
    if not b:
        return 0.0
    m = len(b) >> 1
    return b[m] if len(b) % 2 else (b[m - 1] + b[m]) / 2


def spike_filter(a, passes: int, k: float) -> list:
    """CPTask-style spike filter: a single-sample peak (local extreme that sticks out well
    beyond the local noise level) is replaced by the mean of its neighbours. Running it
    N times removes peaks up to ~N samples wide."""
    x = list(a)
    n = len(x)
    for _ in range(passes):
        dev = []
        for i in range(1, n - 1):
            r = abs(x[i] - (x[i - 1] + x[i + 1]) / 2)
            if fin(r):
                dev.append(r)
        noise = 1.4826 * median(dev)
        y = list(x)
        for i in range(1, n - 1):
            a0, a1, a2 = x[i - 1], x[i], x[i + 1]
            if not (fin(a0) and fin(a1) and fin(a2)):
                continue
            m = (a0 + a2) / 2
            thr = max(k * noise, 0.05 * abs(m), 1e-6)
            if (a1 > max(a0, a2) or a1 < min(a0, a2)) and abs(a1 - m) > thr:
                y[i] = m
        x = y
    return x


def interp(xs, ys, x) -> float:
    n = len(xs)
    if not n or x < xs[0] or x > xs[n - 1]:
        return NAN
    lo, hi = 0, n - 1
    while hi - lo > 1:
        m = (lo + hi) >> 1
        if xs[m] <= x:
            lo = m
        else:
            hi = m
    if xs[hi] == xs[lo]:
        return ys[lo]
    t = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])


def zone1990(Q, F, Ic) -> int:
    """Robertson (1990) zone 1–9 from Qt, Fr and Ic (0 = not classified)."""
    if not (Q > 0 and F > 0) or not fin(Ic):
        return 0
    if Q < 12 * math.exp(-1.4 * F):
        return 1
    if F > 1.5:
        x = F - 1
        den = 0.005 * x - 0.0003 * x * x - 0.002
        if den > 0 and Q > 1 / den:
            return 8 if F < 4.5 else 9
    if Ic > 3.6:
        return 2
    if Ic > 2.95:
        return 3
    if Ic > 2.6:
        return 4
    if Ic > 2.05:
        return 5
    if Ic > 1.31:
        return 6
    return 7


def settings_for(obj, settings: Settings | None) -> Settings:
    """Per-CPT settings win over the collection settings, which win over the defaults."""
    if getattr(obj, "settings", None) is not None:
        return obj.settings
    return settings if settings is not None else Settings()


def u_location(c: CPT, F: dict) -> str:
    r = c.raw
    if F["uLoc"] != "auto" and any(fin(v) for v in getattr(r, F["uLoc"], [])):
        return F["uLoc"]
    return next((k for k in ("u2", "u1", "u3") if any(fin(v) for v in getattr(r, k))), "u2")


def shift_on(c: CPT, F: dict) -> bool:
    m = F["shiftFs"]
    return m == "on" or (m == "auto" and c.source == "gme")


def process_cpt(c: CPT, settings: Settings | None = None) -> CPT:
    """Calculate all derived values into ``c.data`` and the soil layers into ``c.layers``."""
    S = settings_for(c, settings)
    F = S.factors
    h, r = c.header, c.raw
    n = len(r.L)
    passes = max(0, math.floor(float(F["filterPasses"] or 0) + 0.5))   # Math.round
    k = float(F["filterK"] or 4)
    L = r.L
    loc = u_location(c, F)
    qc = spike_filter(r.qc, passes, k)
    fs0 = spike_filter(r.fs, passes, k)
    u = spike_filter(getattr(r, loc), passes, k)
    dist = (h.sleeve if h.sleeve is not None else float(F["sleeveDefault"])) if shift_on(c, F) else 0
    fs = [interp(L, fs0, l + dist) for l in L] if dist else fs0
    if F["inclCorr"] and r.zc:
        z = [v if fin(v) else L[i] for i, v in enumerate(r.zc)]
    elif F["inclCorr"] and any(fin(v) for v in r.I):
        z = [NAN] * n
        z[0] = L[0]
        for i in range(1, n):
            a = r.I[i] if fin(r.I[i]) else 0
            z[i] = z[i - 1] + (L[i] - L[i - 1]) * math.cos(a * math.pi / 180)
    else:
        z = list(L)

    alpha = h.alpha if h.alpha is not None else float(F["alphaDefault"])
    gwl = h.gwl if h.gwl is not None else float(F["gwlDefault"])
    gw = float(F["gw"])
    g_dry, g_wet = float(F["gDry"]), float(F["gWet"])
    rob = F["gammaMethod"] == "rob"
    C0, C1, C2 = float(F["drC0"]), float(F["drC1"]), float(F["drC2"])
    icA, icB = float(F["icA"]), float(F["icB"])
    phiA, phiB = float(F["phiA"]), float(F["phiB"])
    nk_min, nk_max = float(F["nkMin"]), float(F["nkMax"])

    def A():
        return [NAN] * n

    d = {"z": z, "L": L, "qc": qc, "fs": fs, "u2": u, "u1": r.u1, "u3": r.u3, "I": r.I, "t": r.t, "uLoc": loc,
         "u0": A(), "qt": A(), "Rf": A(), "du": A(), "qe": A(), "uqc": A(), "gam": A(), "sv": A(), "svp": A(),
         "qn": A(), "Bq": A(), "Qt": A(), "Fr": A(), "Ic": A(), "zone": [0] * n, "Qtn": A(), "Icn": A(),
         "Dr": A(), "DrNC": A(), "DrOC": A(), "phi": A(), "Su": A(), "Su2": A(), "N60": A(), "v": A()}
    for key, vals in r.x.items():
        d[key] = vals
    for i in range(n):
        zi = z[i]
        u0 = gw * (zi - gwl) / 1000 if zi > gwl else 0.0                       # MPa
        qt = qc[i] + (1 - alpha) * u[i] if loc == "u2" and fin(u[i]) else qc[i]  # area correction needs u2
        Rf = fs[i] / qc[i] * 100 if qc[i] > 0 and fin(fs[i]) else NAN
        g = g_dry if zi <= gwl else g_wet
        if rob and Rf > 0 and qt > 0:
            g = clamp(gw * (0.27 * log10(Rf) + 0.36 * log10(qt * 1000 / PA) + 1.236), 12, 23)
        # total stress: integrate γ, splitting the first interval at the water table
        if i == 0:
            z0 = jmax(zi, 0)
            zw = jmin(z0, jmax(gwl, 0))
            sv = g_dry * zw + (g if rob else g_wet) * (z0 - zw)
            if z0 <= gwl:
                sv = (g if rob else g_dry) * z0
        else:
            sv = d["sv"][i - 1] + g * (zi - z[i - 1])
        svp = sv - u0 * 1000
        qn = qt - sv / 1000
        d["u0"][i], d["qt"][i], d["Rf"][i], d["gam"][i] = u0, qt, Rf, g
        d["sv"][i], d["svp"][i], d["qn"][i] = sv, svp, qn
        d["du"][i] = u[i] - u0
        d["qe"][i] = qc[i] - u[i]
        d["uqc"][i] = u[i] / qc[i] if qc[i] > 0 else NAN
        d["Bq"][i] = (u[i] - u0) / qn if qn > 0 else NAN
        Q = qn * 1000 / svp if svp > 0 and qn > 0 else NAN
        Fr = fs[i] / qn * 100 if qn > 0 and fs[i] > 0 else NAN
        Ic = sqrt((icA - log10(Q)) ** 2 + (log10(Fr) + icB) ** 2) if Q > 0 and Fr > 0 else NAN
        d["Qt"][i], d["Fr"][i], d["Ic"][i] = Q, Fr, Ic
        d["zone"][i] = zone1990(Q, Fr, Ic)
        if fin(Ic) and svp > 0:
            nn, Qtn, Icn = 1.0, Q, Ic
            for _ in range(30):
                Qtn = (qn * 1000 / PA) * pow_(PA / svp, nn)
                Icn = sqrt((3.47 - log10(Qtn)) ** 2 + (log10(Fr) + 1.22) ** 2) if Qtn > 0 else NAN
                n2 = jmin(1, 0.381 * Icn + 0.05 * svp / PA - 0.15)
                if not fin(n2) or abs(n2 - nn) < 1e-3:
                    nn = n2
                    break
                nn = n2
            d["Qtn"][i], d["Icn"][i] = Qtn, Icn
        sand = not F["soilLimit"] or (fin(Ic) and Ic < 2.6)
        clay = not F["soilLimit"] or (fin(Ic) and Ic >= 2.6)
        if sand and qc[i] > 0 and svp > 0:
            def drf(c0, c1, c2):
                return clamp(100 / c2 * ln(qc[i] * 1000 / (c0 * pow_(svp, c1))), 0, 100)
            d["Dr"][i] = drf(C0, C1, C2)
            d["DrNC"][i] = drf(157, 0.55, 2.41)
            d["DrOC"][i] = drf(181, 0.55, 2.61)
            d["phi"][i] = math.atan(phiA + phiB * ln(qc[i] * 1000 / svp)) * 180 / math.pi
        if clay and fin(qt):
            d["Su"][i] = (qt * 1000 - sv) / nk_min
            d["Su2"][i] = (qt * 1000 - sv) / nk_max
        if fin(Ic) and Ic < 4.6 and qc[i] > 0:
            d["N60"][i] = (qc[i] * 1000 / PA) / (8.5 * (1 - Ic / 4.6))
    if any(fin(v) for v in r.t):
        for i in range(n):
            a, b = max(0, i - 2), min(n - 1, i + 2)
            dt = r.t[b] - r.t[a]
            if dt > 0:
                d["v"][i] = (L[b] - L[a]) / dt * 100
    c.data = d
    c.layers = make_layers(c, S)
    return c


def make_layers(c: CPT, settings: Settings | None = None) -> list[dict]:
    """Soil layers from runs of equal SBT zone; layers thinner than ``minLayer`` are merged
    into the neighbour with the closer mean Ic."""
    S = settings_for(c, settings)
    F = S.factors
    d = c.data
    z, zone, Ic = d["z"], d["zone"], d["Ic"]
    n = len(z)
    tmin = float(F["minLayer"] or 0)
    if not n:
        return []
    runs: list[dict] = []
    for i in range(n):
        zn = zone[i]
        if runs and runs[-1]["zone"] == zn:
            runs[-1]["i1"] = i
        else:
            runs.append({"i0": i, "i1": i, "zone": zn})

    def top(r):
        return (z[r["i0"]] + z[r["i0"] - 1]) / 2 if r["i0"] > 0 else z[0]

    def bot(r):
        return (z[r["i1"]] + z[r["i1"] + 1]) / 2 if r["i1"] < n - 1 else z[n - 1]

    def avg(arr, r):
        vals = [arr[i] for i in range(r["i0"], r["i1"] + 1) if fin(arr[i])]
        return sum(vals) / len(vals) if vals else NAN

    def majority(r):
        tt = [0.0] * 10
        for i in range(r["i0"], r["i1"] + 1):
            tt[zone[i]] += z[i + 1] - z[i] if i < n - 1 else 0.01
        b = 0
        for zz in range(1, 10):
            if tt[zz] > tt[b] or (b == 0 and tt[zz] > 0 and tt[zz] >= tt[0] * 0.25):
                b = zz
        return b

    while len(runs) > 1:
        k, tk = -1, math.inf
        for i, r in enumerate(runs):
            th = bot(r) - top(r)
            if th < tmin and th < tk:
                tk, k = th, i
        if k < 0:
            break
        r = runs[k]
        ic = avg(Ic, r)
        p = runs[k - 1] if k > 0 else None
        q = runs[k + 1] if k + 1 < len(runs) else None
        if not p:
            into = k + 1
        elif not q:
            into = k - 1
        else:
            dp, dq = abs(avg(Ic, p) - ic), abs(avg(Ic, q) - ic)
            into = k - 1 if (dp if fin(dp) else 9) <= (dq if fin(dq) else 9) else k + 1
        tg = runs[into]
        tg["i0"], tg["i1"] = min(tg["i0"], r["i0"]), max(tg["i1"], r["i1"])
        runs.pop(k)
        tg["zone"] = majority(tg)
        for i in range(len(runs) - 1, 0, -1):
            if runs[i]["zone"] == runs[i - 1]["zone"]:
                runs[i - 1]["i1"] = runs[i]["i1"]
                runs.pop(i)

    out = []
    for r in runs:
        ic = avg(Ic, r)
        lim = F["soilLimit"]
        sand = not lim or ic < 2.6
        clay = not lim or ic >= 2.6
        out.append({"top": top(r), "bottom": bot(r), "zone": r["zone"], "qc": avg(d["qc"], r), "fs": avg(d["fs"], r),
                    "Rf": avg(d["Rf"], r), "Ic": ic,
                    "Dr": avg(d["Dr"], r) if sand else NAN, "phi": avg(d["phi"], r) if sand else NAN,
                    "Su": avg(d["Su"], r) if clay else NAN, "Su2": avg(d["Su2"], r) if clay else NAN,
                    "N60": avg(d["N60"], r)})
    return out


def find_parent(D: Dissipation, cpts):
    if not D.parent:
        return None
    b = base_name(D.parent).lower()
    return next((x for x in cpts if x.kind == "cpt" and base_name(x.file).lower() == b), None)


def process_diss(D: Dissipation, settings: Settings | None = None, cpts=()) -> Dissipation:
    """u0, ui, u50, t50, t<pct> and the coefficient of consolidation ch (Teh & Houlsby 1991)."""
    S = settings_for(D, settings)
    F = S.factors
    o, h = D.options, D.header
    parent = find_parent(D, cpts)
    gwl = h.gwl if h.gwl is not None else (parent.header.gwl if parent and parent.header.gwl is not None
                                           else float(F["gwlDefault"]))
    u0calc = max(0.0, float(F["gw"]) * (D.depth - gwl) / 1000) if fin(D.depth) else 0.0
    u0 = o["u0_own"] if fin(o.get("u0_own")) else u0calc
    # initial pore pressure: the early peak (standard and dilatory responses) or, when u rises towards u0, the first reading
    t_end = max(v for v in D.t if fin(v))
    imax = 0
    for i, v in enumerate(D.u):
        if fin(v) and D.t[i] <= 0.3 * t_end and (not fin(D.u[imax]) or v > D.u[imax]):
            imax = i
    i0 = imax
    if not (D.u[imax] > u0):
        i0 = next((i for i, v in enumerate(D.u) if fin(v)), -1)
        imax = i0
    ui = o["ui_own"] if fin(o.get("ui_own")) else (D.u[i0] if i0 >= 0 else NAN)

    def t_at(U):
        """First time after the start point where the degree of dissipation reaches U (0..1)."""
        target = ui - (ui - u0) * U
        for i in range(max(1, imax + 1), len(D.t)):
            a, b = D.u[i - 1], D.u[i]
            if fin(a) and fin(b) and ((ui >= u0 and b <= target <= a) or (ui < u0 and b >= target >= a)):
                return D.t[i] if a == b else D.t[i - 1] + (target - a) / (b - a) * (D.t[i] - D.t[i - 1])
        return NAN

    area = h.cone_area if h.cone_area is not None else 1000
    if area <= 50:
        area *= 100  # cm² written as mm² in some files
    r = math.sqrt(area * 1e-6 / math.pi)  # cone radius, m
    t50, tp = t_at(0.5), t_at(o["pct"] / 100)
    ch = o["T50"] * r * r * math.sqrt(o["Ir"]) / t50 if fin(t50) and t50 > 0 else NAN  # m²/s
    D.result = {"u0": u0, "u0calc": u0calc, "ui": ui, "imax": imax, "t50": t50, "tp": tp, "ch": ch, "r": r,
                "area": area, "u50": ui - (ui - u0) * 0.5}
    return D
