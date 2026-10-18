"""Write synthetic demo files (no real site data) to tests/fixtures/ or a folder you name.

    python tools/make_demo_data.py            # → tests/fixtures
    python tools/make_demo_data.py demo_data  # → demo_data/

Files: DEMO-01.gef (CPTu with inclination, spikes and an extra temperature column),
DEMO-01_D1.gef (dissipation test at 5 m), DEMO-02.0EF / DEMO-02.1EF (GME raw pair),
DEMO-03.csv (semicolon CSV with kPa units).
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

# (top, bottom, qc MPa, Rf %, excess pore pressure factor)
PROFILE = [(0.0, 1.6, 6.0, 0.8, 0.0), (1.6, 5.8, 0.6, 4.5, 0.55), (5.8, 7.6, 2.5, 2.4, 0.15),
           (7.6, 12.8, 14.0, 0.6, 0.0), (12.8, 15.2, 26.0, 0.5, -0.02)]


def profile(L, rnd):
    for top, bot, qc, rf, b in PROFILE:
        if top <= L < bot or L >= PROFILE[-1][1]:
            break
    trend = 1 + 0.04 * (L - top)
    qcv = max(0.05, qc * trend * (1 + rnd.gauss(0, 0.06)))
    fs = qcv * rf / 100 * (1 + rnd.gauss(0, 0.05))
    u0 = max(0.0, 10 * (L - 1.5) / 1000)
    u2 = u0 + b * qcv + rnd.gauss(0, 0.004)
    return qcv, fs, u2


def demo_cpt(path: Path, rnd):
    rows = []
    L, t = 0.0, 0.0
    ix = iy = 0.0
    while L <= 15.0 + 1e-9:
        qc, fs, u2 = profile(L, rnd)
        if abs(L - 4.20) < 1e-6:
            qc *= 4.0           # single-sample spike for the filter
        if abs(L - 9.50) < 1e-6:
            fs *= 3.0
        ix = min(6, ix + abs(rnd.gauss(0, 0.03)))
        iy += rnd.gauss(0, 0.02)
        res = math.degrees(math.acos(math.cos(math.radians(ix)) * math.cos(math.radians(iy))))
        temp = 24 + 0.15 * L + rnd.gauss(0, 0.05)
        rows.append((L, qc, fs, u2, ix, iy, t, res, temp))
        L = round(L + 0.02, 4)
        t += 1.0 + rnd.gauss(0, 0.05)
    head = [
        "#GEFID= 1, 1, 0", "#FILEOWNER= Synthetic demo", "#FILEDATE= 2026, 1, 15", "#PROJECTID= DEMO 001",
        "#COLUMN= 9",
        "#COLUMNINFO= 1, m, penetration length, 1", "#COLUMNINFO= 2, MPa, qc, 2", "#COLUMNINFO= 3, MPa, fs, 3",
        "#COLUMNINFO= 4, MPa, u2, 6", "#COLUMNINFO= 5, degrees, i_x, 9", "#COLUMNINFO= 6, degrees, i_y, 10",
        "#COLUMNINFO= 7, Sec, SampleTime, 12", "#COLUMNINFO= 8, degrees, i_res, 8", "#COLUMNINFO= 9, C, Temperature, 99",
        *[f"#COLUMNVOID= {i}, -9999.000000" for i in range(1, 10)],
        f"#LASTSCAN= {len(rows)}", "#XYID= 0, 12345.678, 23456.789, 0.00, 0.000", "#ZID= 0, 4.250, 0.000",
        "#MEASUREMENTTEXT= 1, Demo Client, Client", "#MEASUREMENTTEXT= 2, Demo reclamation, Name of the project",
        "#MEASUREMENTTEXT= 3, Test site, Location", "#MEASUREMENTTEXT= 4, DEMO10CFIIP, Cone Type",
        "#MEASUREMENTTEXT= 21, Synthetic data for tests, Remarks",
        "#MEASUREMENTVAR= 1, 1000.000000, mm2, Nom. surface area of cone tip",
        "#MEASUREMENTVAR= 3, 0.800000, -, Net surface area quotient of cone tip",
        "#MEASUREMENTVAR= 4, 1.000000, -, Net surface area quotient of friction casing",
        "#MEASUREMENTVAR= 5, 80.000000, mm, Cone distance to centre of friction casing",
        "#MEASUREMENTVAR= 13, 0.000000, m, Pre-excavated depth",
        "#MEASUREMENTVAR= 14, -1.500000, m, WaterLevel",
        "#STARTDATE= 2026, 1, 15", "#REPORTCODE= GEF-CPT-Report, 1, 1, 0, -", "#TESTID= DEMO-01", "#EOH=",
    ]
    body = [" ".join(f"{v:10.4f}" for v in r) for r in rows]
    path.write_text("\r\n".join(head + body) + "\r\n", encoding="utf-8")


def demo_diss(path: Path, rnd):
    u0, ui = 0.035, 0.42
    rows = []
    t = 0.0
    while t <= 1800:
        u = u0 + (ui - u0) * math.exp(-t / 260) + rnd.gauss(0, 0.002)
        if t < 3:
            u = ui * (0.9 + 0.03 * t)
        rows.append((t, u, 0.55 + rnd.gauss(0, 0.01)))
        t += 1 if t < 60 else 5 if t < 300 else 20
    head = ["#GEFID= 1, 1, 0", "#FILEOWNER= Synthetic demo", "#PROJECTID= DEMO 001", "#COLUMN= 3",
            "#COLUMNINFO= 1, s, Time, 21", "#COLUMNINFO= 2, MPa, Pore pressure, 6", "#COLUMNINFO= 3, MPa, Cone resistance, 2",
            "#COLUMNVOID= 1, -9999.000000", "#COLUMNVOID= 2, -9999.000000", "#COLUMNVOID= 3, -9999.000000",
            f"#LASTSCAN= {len(rows)}", "#PARENT= DEMO-01.gef, 5.00, m, penetration length, 1, # of test",
            "#MEASUREMENTVAR= 1, 1000.000000, mm2, Nom. surface area of cone tip",
            "#REPORTCODE= GEF-DISS-Report, 1, 0, 0, -", "#TESTID= 1", "#EOH="]
    body = [f"{a:.1f} {b:.5f} {c:.4f}" for a, b, c in rows]
    path.write_text("\r\n".join(head + body) + "\r\n", encoding="utf-8")


def demo_gme(header: Path, data: Path, rnd):
    cal = (0.25, 0.04, 0.5)
    header.write_text("\r\n".join([
        "Client name : Demo reclamation", "Job number : DEMO 001", "Testnumber : DEMO-02", "Location : Test site",
        "Date : 15-1-2026", "Conenumber : DEMO10CFP", "Conetype : C", "Nr channels : 3", "Pre drill : 0.50",
        "Ground level : 4.10", f"Cal Factor. 1 : {cal[0]}", f"Cal Factor. 2 : {cal[1]}", f"Cal Factor. 3 : {cal[2]}",
        "Cal Factor. 4 : 1.0"]) + "\r\n", encoding="utf-8")
    lines = []
    idx, s, cs = 1, 0, 0
    while True:
        L = 0.5 + (idx - 1) * 0.01
        if L > 12.0:
            break
        qc, fs, u2 = profile(L, rnd)
        ch = (round(qc * 10 / cal[0]), round(fs * 10 / cal[1]), round(u2 * 100 / cal[2]))
        lines.append(f"|{ch[0]}|{ch[1]}|{ch[2]}|{idx}|{idx}|{s}|{cs}|")
        idx += 1
        cs += 50
        if cs >= 100:
            s, cs = s + 1, cs - 100
    data.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")


def demo_csv(path: Path, rnd):
    lines = ["Depth [m];qc [MPa];fs [kPa];u2 [kPa];Inclination [deg]"]
    L = 0.0
    while L <= 10.0 + 1e-9:
        qc, fs, u2 = profile(L + 3, rnd)
        lines.append(f"{L:.2f};{qc:.3f};{fs * 1000:.1f};{u2 * 1000:.1f};{0.5 + L * 0.05:.2f}")
        L = round(L + 0.05, 4)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    rnd = random.Random(42)
    demo_cpt(out / "DEMO-01.gef", rnd)
    demo_diss(out / "DEMO-01_D1.gef", rnd)
    demo_gme(out / "DEMO-02.0EF", out / "DEMO-02.1EF", rnd)
    demo_csv(out / "DEMO-03.csv", rnd)
    for p in sorted(out.iterdir()):
        print(p)


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "tests" / "fixtures")
