"""Compare the Python results with the HTML tool's JavaScript engine, file by file.

    pip install mini-racer
    python tools/compare_with_html.py path/to/CPT_Analyser.html data/*.gef

Prints the largest difference per calculated value and a final PASS / FAIL line.
Run it after changing a calculation in either version to see that they still agree.
"""
from __future__ import annotations

import datetime as dt
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from html_reference import Reference  # noqa: E402

import cpt_analyser as ca  # noqa: E402
from cpt_analyser.readers.gme import is_gme  # noqa: E402

HEADER_MAP = {"testId": "test_id", "project": "project", "jobNo": "job_no", "client": "client", "location": "location",
              "coneType": "cone_type", "date": "date", "remarks": "remarks", "x": "x", "y": "y", "gl": "gl", "gwl": "gwl",
              "predrill": "predrill", "alpha": "alpha", "beta": "beta", "sleeve": "sleeve", "coneArea": "cone_area"}


def close(a, b, rtol=1e-9, atol=1e-9) -> bool:
    if a is None or (isinstance(a, float) and not math.isfinite(a)):
        return b is None or (isinstance(b, float) and not math.isfinite(b))
    if b is None or isinstance(b, str) or isinstance(a, str):
        return a == b
    return abs(a - b) <= atol + rtol * abs(b)


def diff_list(py, js):
    """(number of mismatching rows, largest absolute difference)."""
    bad, worst = 0, 0.0
    for a, b in zip(py, js):
        if not close(a, b):
            bad += 1
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and math.isfinite(a):
                worst = max(worst, abs(a - b))
    return bad + abs(len(py) - len(js)), worst


def same_text(py: str, js: str) -> bool:
    """Equal, except where the browser replaced a non-UTF-8 byte by U+FFFD (the Python version keeps it)."""
    return len(py) == len(js) and all(a == b or b == "\ufffd" for a, b in zip(py, js))


def compare(ref: Reference, path: Path, data_path: Path | None = None) -> list[str]:
    try:
        js = ref.run_file(path, data_path)
    except Exception as e:  # noqa: BLE001 – the HTML rejects the file: Python must reject it too
        try:
            ca.read(path)
        except Exception:  # noqa: BLE001
            return []
        return [f"HTML rejects the file ({str(e).splitlines()[0]}) but Python reads it"]
    obj = ca.parse_gme(path.read_text(errors="replace"), data_path.read_text(errors="replace"), data_path.name) if data_path \
        else ca.read(path)
    obj.process()
    problems = []
    for jk, pk in HEADER_MAP.items():
        a, b = getattr(obj.header, pk), js["h"].get(jk)
        if not close(a, b if b != "" or isinstance(a, str) else None):
            problems.append(f"header {jk}: py={a!r} js={b!r}")
    if js["kind"] == "diss":
        for k in ("u0", "ui", "t50", "tp", "ch", "u50"):
            if not close(obj.result[k], js["res"][k], 1e-9):
                problems.append(f"diss {k}: py={obj.result[k]} js={js['res'][k]}")
        return problems
    for k, vals in js["d"].items():
        if k == "uLoc":
            if obj.data[k] != vals:
                problems.append(f"uLoc py={obj.data[k]} js={vals}")
            continue
        bad, worst = diff_list(obj.data.get(k, []), vals)
        if bad:
            problems.append(f"{k}: {bad} rows differ (max |Δ| {worst:.3g})")
    if len(obj.layers) != len(js["layers"]):
        problems.append(f"layers: py {len(obj.layers)} js {len(js['layers'])}")
    else:
        for i, (a, b) in enumerate(zip(obj.layers, js["layers"])):
            for k in a:
                if not close(a[k], b.get(k)):
                    problems.append(f"layer {i} {k}: py={a[k]} js={b.get(k)}")
    if js.get("gef"):
        py_gef = "\r\n".join(ln for ln in ca.to_gef(obj, today=dt.date.today()).split("\r\n") if not ln.startswith("#COMMENT= Saved"))
        if not same_text(py_gef, js["gef"]):
            problems.append("GEF output differs")
    return problems


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    ref = Reference(argv[0])
    files = [Path(p) for p in argv[1:] if Path(p).is_file()]
    n_ok = n_bad = 0
    for p in files:
        if is_gme(p.name):
            if p.suffix[1] != "1":
                continue
            hp = p.with_suffix(".0" + p.suffix[2:])
            pr = compare(ref, hp, p)
        else:
            try:
                pr = compare(ref, p)
            except Exception as e:  # noqa: BLE001
                pr = [f"error: {e}"]
        if pr:
            n_bad += 1
            print(f"FAIL {p.name}")
            for x in pr[:12]:
                print("    " + x)
        else:
            n_ok += 1
    print(f"{'PASS' if not n_bad else 'FAIL'}: {n_ok} identical, {n_bad} with differences")
    return 1 if n_bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
