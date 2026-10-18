"""The Python results must match the HTML tool's JavaScript engine.

``tests/expected/*.expected.json`` were produced by running CPT_Analyser.html's own
code on the demo files (``python tools/html_reference.py CPT_Analyser.html --update-fixtures``).
If you change a calculation on purpose, change it in both versions and regenerate them.
"""
import json
import math
from pathlib import Path

import pytest

import cpt_analyser as ca

FIX = Path(__file__).parent / "fixtures"
EXP = Path(__file__).parent / "expected"
HEADER_MAP = {"testId": "test_id", "project": "project", "jobNo": "job_no", "client": "client", "location": "location",
              "coneType": "cone_type", "date": "date", "remarks": "remarks", "x": "x", "y": "y", "gl": "gl", "gwl": "gwl",
              "predrill": "predrill", "alpha": "alpha", "beta": "beta", "sleeve": "sleeve", "coneArea": "cone_area"}


def same(a, b):
    if a is None or (isinstance(a, float) and not math.isfinite(a)):
        return b is None
    if isinstance(a, str) or isinstance(b, str) or b is None:
        return a == b
    return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)


def load_py(name):
    p = FIX / name
    if p.suffix.upper().startswith(".1"):
        hdr = p.with_suffix(".0" + p.suffix[2:])
        return ca.parse_gme(hdr.read_text(), p.read_text(), p.name).process()
    return ca.read(p)


CASES = sorted(p.name.replace(".expected.json", "") for p in EXP.glob("*.expected.json"))


@pytest.mark.parametrize("name", CASES)
def test_matches_html(name):
    js = json.loads((EXP / f"{name}.expected.json").read_text(encoding="utf-8"))
    obj = load_py(name)
    for jk, pk in HEADER_MAP.items():
        b = js["h"].get(jk)
        a = getattr(obj.header, pk)
        assert same(a, b if (b != "" or isinstance(a, str)) else None), f"header {jk}: {a!r} != {b!r}"
    if js["kind"] == "diss":
        for k in ("u0", "ui", "t50", "tp", "ch", "u50"):
            assert same(obj.result[k], js["res"][k]), k
        return
    for k, vals in js["d"].items():
        if k == "uLoc":
            assert obj.data[k] == vals
            continue
        py = obj.data[k]
        assert len(py) == len(vals), k
        bad = [i for i, (a, b) in enumerate(zip(py, vals)) if not same(a, b)]
        assert not bad, f"{k}: {len(bad)} rows differ, first at row {bad[0]}: {py[bad[0]]} vs {vals[bad[0]]}"
    assert len(obj.layers) == len(js["layers"])
    for a, b in zip(obj.layers, js["layers"]):
        for k in a:
            assert same(a[k], b.get(k)), k
    if js.get("gef"):
        out = "\r\n".join(ln for ln in ca.to_gef(obj).split("\r\n") if not ln.startswith("#COMMENT= Saved"))
        assert out == js["gef"]
