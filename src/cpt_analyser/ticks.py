"""Axis ticks and number formatting shared by plots and exports."""
from __future__ import annotations

import math

from ._js import fin, js_str


def nice_step(rng: float, target: float) -> float:
    raw = rng / target if target else math.nan
    if not (raw > 0):
        return 1
    p = 10 ** math.floor(math.log10(raw))
    f = raw / p
    return (1 if f < 1.5 else 2 if f < 3 else 5 if f < 7 else 10) * p


def fmt(v, dp: int | None = None) -> str:
    """Number for display; '–' when missing. Default decimals depend on the magnitude."""
    if not fin(v):
        return "–"
    if dp is None:
        a = abs(v)
        dp = 0 if a >= 100 else 1 if a >= 10 else 2 if a >= 1 else 3
    return f"{v:.{dp}f}"


def tick_fmt(v: float) -> str:
    return js_str(float(f"{v:.6g}"))


def ticks(lo: float, hi: float, log: bool = False) -> list[float]:
    if log:
        out = []
        for e in range(math.floor(math.log10(lo)), math.ceil(math.log10(hi)) + 1):
            v = 10.0 ** e
            if lo * 0.999 <= v <= hi * 1.001:
                out.append(v)
        return out
    st = nice_step(hi - lo, 5)
    out = []
    v = math.ceil(lo / st - 1e-9) * st
    while v <= hi + st * 1e-6:
        out.append(round(v, 10))
        v += st
    return out
