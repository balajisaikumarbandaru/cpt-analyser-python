"""Run the calculation engine of the HTML CPT Analyser (JavaScript) on a file and
print / return its results as JSON. Used to check that the Python port gives
the same numbers, and to (re)generate ``tests/expected/*.expected.json``.

Needs the V8 wrapper ``mini-racer`` (``pip install mini-racer``) and a copy of
``CPT_Analyser.html`` from https://github.com/balajisaikumarbandaru/cpt-analyser

    python tools/html_reference.py CPT_Analyser.html tests/fixtures/demo_cpt.gef
    python tools/html_reference.py CPT_Analyser.html demo.0EF demo.1EF          # GME pair
    python tools/html_reference.py CPT_Analyser.html --update-fixtures          # rewrite expected files
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent.parent / "tests"
FIXTURES, EXPECTED = TESTS / "fixtures", TESTS / "expected"

STUBS = """
var window = {}; var document = {querySelector(){return null}, createElement(){return {}}};
var localStorage = {getItem(){return null}, setItem(){}};
"""

RUN = """
function __run(kind, a, b, name, settingsJson){
  state.cpts = [];
  if (settingsJson){ applySettings(S, JSON.parse(settingsJson)); }
  let c;
  if (kind === 'gme') c = parseGME(a, b, name);
  else if (kind === 'csv') c = parseDelimited(a, name);
  else c = parseGEF(a, name);
  addCPT(c);
  if (c.kind === 'diss') return JSON.stringify({kind: 'diss', h: c.h, t: c.diss.t, u: c.diss.u, qc: c.diss.qc,
    depth: c.diss.depth, parent: c.diss.parent, loc: c.diss.loc, res: c.res});
  const d = {}; for (const k in c.d) d[k] = c.d[k];
  const gef = c.gef ? toGEF(c).split('\\r\\n').filter(l => !/^#COMMENT= Saved/.test(l)).join('\\r\\n') : null;
  return JSON.stringify({kind: 'cpt', h: c.h, d, layers: c.layers, source: c.source, gef});
}
"""


def engine_source(html_path) -> str:
    html = Path(html_path).read_text(encoding="utf-8")
    start = html.index("const PA = 100")
    end = html.index("Plotting (SVG")
    end = html.rindex("/*", 0, end)
    core = html[start:end]
    helpers = []
    for fn in ("niceStep", "fmt", "applySettings", "toGEF", "rawArr"):
        m = re.search(r"^(?:function " + fn + r"\(.*|const " + fn + r" = .*)$", html, re.M)
        if m and m.group(0) not in core:
            if fn == "toGEF":   # multi-line function: copy up to the closing brace at column 0
                s = m.start()
                helpers.append(html[s: html.index("\n}\n", s) + 3])
            else:
                helpers.append(m.group(0))
    return STUBS + core + "\n" + "\n".join(helpers) + RUN


class Reference:
    def __init__(self, html_path):
        from py_mini_racer import MiniRacer
        self.ctx = MiniRacer()
        self.ctx.eval(engine_source(html_path))

    def run(self, kind, a, b=None, name="file", settings=None) -> dict:
        return json.loads(self.ctx.call("__run", kind, a, b, name, json.dumps(settings) if settings else None))

    def run_file(self, path, data_path=None, settings=None) -> dict:
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        if data_path:
            return self.run("gme", text, Path(data_path).read_text(encoding="utf-8", errors="replace"), Path(data_path).name, settings)
        kind = "gef" if p.suffix.lower() == ".gef" or text.lstrip().upper().startswith("#GEFID") else "csv"
        return self.run(kind, text, None, p.name, settings)


def update_fixtures(html_path):
    ref = Reference(html_path)
    for p in sorted(FIXTURES.iterdir()):
        if p.suffix.lower() in (".gef", ".csv", ".txt"):
            out = ref.run_file(p)
        elif re.match(r"^\.1", p.suffix):
            out = ref.run_file(p.with_suffix(".0" + p.suffix[2:]), p)
        else:
            continue
        if out.get("source") != "gef":
            out.pop("gef", None)   # a fresh GEF carries today's date; only the lossless GEF rewrite is compared
        dest = EXPECTED / (p.name + ".expected.json")
        dest.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
        print(dest)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    if sys.argv[2] == "--update-fixtures":
        update_fixtures(sys.argv[1])
    else:
        r = Reference(sys.argv[1]).run_file(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print(json.dumps(r, ensure_ascii=False)[:2000])
