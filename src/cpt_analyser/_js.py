"""Small helpers that reproduce JavaScript number semantics.

The browser version of CPT Analyser is written in JavaScript. A few of its
behaviours (``parseFloat`` accepting a numeric prefix, ``Math.min`` returning
NaN when any argument is NaN, ``Number('')`` being 0 …) differ from Python.
Using these helpers keeps the Python results identical to the HTML tool.
"""
from __future__ import annotations

import math
import os
import re

NAN = float("nan")

_PREFIX = re.compile(r"\s*([+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?))")
_FULL = re.compile(r"[+-]?(?:Infinity|(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)")


def fin(v) -> bool:
    """True for a finite int/float (JS ``typeof v === 'number' && isFinite(v)``)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _to_float(s: str) -> float:
    if s.lstrip("+-") == "Infinity":
        return -math.inf if s.startswith("-") else math.inf
    return float(s)


def num(v) -> float:
    """Lenient number parser: ``parseFloat(String(v).replace(',', '.'))``, NaN unless finite."""
    if v is None or v == "":
        return NAN
    if isinstance(v, bool):
        return NAN
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else NAN
    m = _PREFIX.match(str(v).replace(",", ".", 1))
    if not m:
        return NAN
    x = _to_float(m.group(1))
    return x if math.isfinite(x) else NAN


def opt_num(v):
    """Like :func:`num` but returns ``None`` instead of NaN."""
    x = num(v)
    return x if math.isfinite(x) else None


def js_number(v) -> float:
    """Strict conversion like JS ``Number(v)`` / unary ``+v``: '' → 0, junk → NaN."""
    if v is None:
        return NAN
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = str(v).strip()
    if s == "":
        return 0.0
    if _FULL.fullmatch(s):
        return _to_float(s)
    if re.fullmatch(r"0[xX][0-9a-fA-F]+", s):
        return float(int(s, 16))
    return NAN


def js_str(x) -> str:
    """String form of a number the way JavaScript prints it (5.0 → '5')."""
    if isinstance(x, float):
        if math.isnan(x):
            return "NaN"
        if math.isinf(x):
            return "Infinity" if x > 0 else "-Infinity"
        if x.is_integer() and abs(x) < 1e21:
            return str(int(x))
        r = repr(x)
        if "e" in r:
            mant, exp = r.split("e")
            return f"{mant}e{'+' if not exp.startswith('-') else '-'}{int(exp.lstrip('+-'))}"
        return r
    return str(x)


def to_fixed(x: float, dp: int) -> str:
    """``Number.prototype.toFixed`` (NaN → 'NaN')."""
    if not math.isfinite(x):
        return js_str(float(x))
    return f"{x:.{dp}f}"


def to_precision(x: float, p: int) -> float:
    """``+v.toPrecision(p)`` – round to p significant digits."""
    if not math.isfinite(x) or x == 0:
        return x
    return float(f"{x:.{p - 1}e}")


def jmin(*a: float) -> float:
    if any(isinstance(v, float) and math.isnan(v) for v in a):
        return NAN
    return min(a)


def jmax(*a: float) -> float:
    if any(isinstance(v, float) and math.isnan(v) for v in a):
        return NAN
    return max(a)


def clamp(v: float, a: float, b: float) -> float:
    return jmin(b, jmax(a, v))


def log10(x: float) -> float:
    if math.isnan(x) or x < 0:
        return NAN
    if x == 0:
        return -math.inf
    return math.log10(x)


def ln(x: float) -> float:
    if math.isnan(x) or x < 0:
        return NAN
    if x == 0:
        return -math.inf
    return math.log(x)


def sqrt(x: float) -> float:
    return math.sqrt(x) if x >= 0 else NAN


def acos(x: float) -> float:
    return math.acos(x) if -1 <= x <= 1 else NAN


def pow_(a: float, b: float) -> float:
    try:
        r = a ** b
    except (OverflowError, ZeroDivisionError):
        return math.inf
    return NAN if isinstance(r, complex) else float(r)


def base_name(s) -> str:
    """File name without folder and extension (``baseName`` in the HTML)."""
    return re.sub(r"\.[^.]+$", "", re.sub(r"^.*[\\/]", "", str(s)))


def safe_name(s: str) -> str:
    """File-name-safe version of a test id (``safe`` in the HTML)."""
    return re.sub(r"[^\w.\- ]+", "_", str(s), flags=re.ASCII)


def path_name(p) -> str:
    return os.path.basename(str(p))
