"""Command line: ``cpt-analyser info|export|settings``.

Examples::

    cpt-analyser info data/
    cpt-analyser export data/ -o out --pdf --png --csv --xlsx --layers
    cpt-analyser export CPT01.gef -o out --all --settings site.cptset.json
    cpt-analyser settings defaults.cptset.json      # write a settings file to edit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._js import fin
from .collection import load
from .constants import ZONES
from .exports import csv_all, file_stem, layers_csv, save_gef, to_csv, to_excel
from .settings import Settings


def _info(col) -> None:
    print(f"{'Test ID':28} {'Rows':>6} {'Depth [m]':>9} {'GWL':>6} {'Layers':>6}  Source / dominant soil")
    for c in col.cpts:
        z = [v for v in c.data["z"] if fin(v)]
        lay = c.layers
        dom = max(lay, key=lambda x: x["bottom"] - x["top"])["zone"] if lay else 0
        gwl = c.header.gwl
        print(f"{c.test_id[:28]:28} {len(z):6d} {max(z) if z else float('nan'):9.2f} "
              f"{'' if gwl is None else f'{gwl:.2f}':>6} {len(lay):6d}  {c.source} / {ZONES[dom][1]}"
              + (f"  ! {c.header.warning}" if c.header.warning else ""))
    for d in col.dissipations:
        r = d.result
        print(f"{d.test_id[:28]:28} {len(d.t):6d} {d.depth if d.depth is not None else float('nan'):9.2f} "
              f"{'':>6} {'':>6}  dissipation, t50 = {r['t50']:.0f} s, ch = {r['ch']:.3g} m²/s")
    for e in col.errors:
        print(f"  error: {e}", file=sys.stderr)


def _export(col, a) -> None:
    from .plotting import plot_dissipation, plot_log_pages, plot_sbt_chart, save_log_pdf
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    every = a.all
    written = []

    def w(name, data):
        p = out / name
        if isinstance(data, bytes):
            p.write_bytes(data)
        else:
            p.write_text(data, encoding="utf-8", newline="")
        written.append(p)

    for c in col.all():
        stem = file_stem(c)
        if a.csv or every:
            w(stem + ".csv", to_csv(c, col.settings))
        if a.xlsx or every:
            w(stem + ".xlsx", to_excel(c, settings=col.settings))
        if a.gef or every:
            written.append(save_gef(c, out / (stem + ("_edited" if c.kind == "cpt" and c.edited() else "") + ".gef"), col.settings))
        if c.kind == "diss":
            if a.png or a.pdf or every:
                fig = plot_dissipation(c)
                fig.savefig(out / f"{stem}.png", dpi=a.dpi)
                written.append(out / f"{stem}.png")
            continue
        if a.png or a.svg or every:
            pages = plot_log_pages(c, col.settings, col.dissipations_for(c))
            for i, fig in enumerate(pages):
                suffix = f"_p{i + 1}" if len(pages) > 1 else ""
                for ext in [e for e, on in (("png", a.png or every), ("svg", a.svg)) if on]:
                    fig.savefig(out / f"{stem}{suffix}.{ext}", dpi=a.dpi)
                    written.append(out / f"{stem}{suffix}.{ext}")
        if a.chart or every:
            plot_sbt_chart(c, col.settings).savefig(out / f"{stem}_SBT.png", dpi=a.dpi)
            written.append(out / f"{stem}_SBT.png")
    if (a.pdf or every) and col.cpts:
        save_log_pdf(col.cpts, out / "CPT_logs.pdf", col.settings, collection=col)
        written.append(out / "CPT_logs.pdf")
    if a.layers or every:
        w("CPT_layers.csv", layers_csv(col.cpts))
    if a.csv_all or every:
        w("CPT_all.csv", csv_all(col.cpts, col.settings))
    for p in written:
        print(p)
    for e in col.errors:
        print(f"error: {e}", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cpt-analyser", description="CPT viewer / interpreter (Python version of CPT Analyser)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("paths", nargs="+", help="GEF / GME / CSV / Excel / .cptset.json files or folders")
        p.add_argument("--settings", "-s", help="settings file (.cptset.json) for all CPTs")

    p = sub.add_parser("info", help="list the soundings with depth, water level and layers")
    common(p)
    p = sub.add_parser("export", help="write plots and data files")
    common(p)
    p.add_argument("-o", "--out", default="cpt_output", help="output folder (default: cpt_output)")
    for flag, hlp in (("pdf", "all log pages of all CPTs in one PDF"), ("png", "log pages as PNG"), ("svg", "log pages as SVG"),
                      ("chart", "Robertson chart PNG"), ("csv", "CSV per CPT"), ("csv-all", "one combined CSV"),
                      ("xlsx", "Excel per CPT"), ("gef", "GEF per CPT"), ("layers", "layer summary CSV"), ("all", "everything above except SVG")):
        p.add_argument("--" + flag, action="store_true", help=hlp)
    p.add_argument("--dpi", type=int, default=200)
    p = sub.add_parser("settings", help="write the default settings to a file you can edit")
    p.add_argument("file", nargs="?", default="defaults.cptset.json")

    a = ap.parse_args(argv)
    if a.cmd == "settings":
        Settings().save(a.file)
        print(a.file)
        return 0
    col = load(*a.paths, settings=a.settings)
    if a.cmd == "info":
        _info(col)
    else:
        if not any(getattr(a, k) for k in ("pdf", "png", "svg", "chart", "csv", "csv_all", "xlsx", "gef", "layers", "all")):
            a.pdf = a.layers = a.csv = True
        _export(col, a)
    return 1 if col.errors and not col.all() else 0


if __name__ == "__main__":
    raise SystemExit(main())
