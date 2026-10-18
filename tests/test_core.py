import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pytest  # noqa: E402

import cpt_analyser as ca  # noqa: E402
from cpt_analyser._js import js_number, num  # noqa: E402
from cpt_analyser.cli import main  # noqa: E402

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def col():
    return ca.load(FIX)


def test_js_number_semantics():
    assert num("12,5") == 12.5
    assert num("3.2abc") == 3.2
    assert math.isnan(num("")) and math.isnan(num(None)) and math.isnan(num("abc"))
    assert js_number("") == 0 and math.isnan(js_number("1a"))


def test_spike_filter_removes_single_peak():
    a = [1.0 + 0.01 * ((i * 7) % 5) for i in range(60)]
    a[30] = 9.0
    out = ca.spike_filter(a, 1, 4)
    assert out[30] == pytest.approx((a[29] + a[31]) / 2)
    # the readings beside the spike must not be touched (they used to be judged against it)
    assert [i for i, (x, y) in enumerate(zip(a, out)) if x != y] == [30]


def test_spike_filter_passes_remove_wider_peaks():
    a = [1.0 + 0.01 * ((i * 7) % 5) for i in range(60)]
    a[30], a[31] = 9.0, 8.0
    assert ca.spike_filter(a, 1, 4)[31] == 8.0       # one pass only takes the top off a 2-sample peak
    assert max(ca.spike_filter(a, 2, 4)[30:32]) < 5
    out = ca.spike_filter(a, 5, 4)
    assert max(out[30:32]) < 1.5
    assert [i for i, (x, y) in enumerate(zip(a, out)) if x != y] == [30, 31]


def test_semicolon_csv_with_decimal_commas(tmp_path):
    src = FIX / "DEMO-03.csv"
    p = tmp_path / "DEMO-03.csv"
    p.write_text(src.read_text().replace(".", ","))   # 0,653;28,4;… – more commas than semicolons
    a, b = ca.read(src), ca.read(p)
    assert b.data["qc"][10] > 0
    assert a.data["qc"] == b.data["qc"] and a.data["fs"] == b.data["fs"] and a.data["u2"] == b.data["u2"]


def test_zone1990():
    assert ca.zone1990(math.nan, 1, 2) == 0
    assert ca.zone1990(200, 0.5, 1.2) == 7
    assert ca.zone1990(5, 3, 3.2) == 3


def test_load_folder(col):
    assert [c.test_id for c in col.cpts] == ["DEMO-01", "DEMO-02", "DEMO-03"]
    assert len(col.dissipations) == 1 and not col.errors
    d = col.dissipations[0]
    assert d.parent == "DEMO-01.gef" and d.depth == 5.0
    assert col.dissipations_for(col["DEMO-01"]) == [d]
    assert 100 < d.result["t50"] < 300


def test_header_and_extra_column(col):
    c = col["DEMO-01"]
    h = c.header
    assert (h.gwl, h.gl, h.alpha, h.sleeve) == (1.5, 4.25, 0.8, 0.08)
    assert h.date == "2026-01-15"
    assert "x_temperature" in c.raw.x and c.raw.x_meta["x_temperature"]["unit"] == "C"
    assert c.data["z"][-1] < c.data["L"][-1]  # inclination depth correction


def test_csv_units_kpa(col):
    c = col["DEMO-03"]
    assert c.raw.fs[0] < 0.5  # kPa columns were converted to MPa


def test_settings_change_and_roundtrip(tmp_path, col):
    c = col["DEMO-01"]
    before = c.data["svp"][-1]
    col.settings.factors["gWet"] = 18
    col.process()
    assert c.data["svp"][-1] < before
    p = tmp_path / "s.cptset.json"
    col.settings.save(p)
    assert ca.Settings.load(p).factors["gWet"] == 18


def test_per_cpt_settings_file(tmp_path):
    import shutil
    shutil.copy(FIX / "DEMO-01.gef", tmp_path)
    s = ca.Settings()
    s.factors["minLayer"] = 2.0
    s.save(tmp_path / "DEMO-01.cptset.json")
    c = ca.load(tmp_path)["DEMO-01"]
    assert c.settings is not None and c.settings.factors["minLayer"] == 2.0
    assert all(L["bottom"] - L["top"] >= 2.0 - 1e-9 for L in c.layers[:-1])


def test_gef_lossless_and_edit(col):
    c = col["DEMO-01"]
    orig = (FIX / "DEMO-01.gef").read_bytes().decode().split("\r\n")
    out = ca.to_gef(c).split("\r\n")
    assert [ln for ln in out if not ln.startswith("#COMMENT= Saved")] == orig
    c.raw.qc[10] = 1.2345
    c.header.gwl = 2.0
    out = ca.to_gef(c).split("\r\n")
    assert "#MEASUREMENTVAR= 14, -2.000000, m, WaterLevel" in out
    assert any("1 value(s) edited" in ln for ln in out)
    eoh = out.index("#EOH=")
    changed = [i for i, (a, b) in enumerate(zip(out[eoh + 1:], orig[orig.index("#EOH=") + 1:])) if a != b]
    assert changed == [10] and "1.2345" in out[eoh + 1 + 10]
    again = ca.parse_gef(ca.to_gef(c), "x.gef")
    assert again.raw.qc[10] == pytest.approx(1.2345) and again.header.gwl == 2.0


def test_fresh_gef_from_gme_reads_back(col):
    c = col["DEMO-02"]
    g = ca.parse_gef(ca.to_gef(c), "DEMO-02.gef").process()
    assert len(g.raw.L) == len(c.raw.L)
    assert g.raw.qc[100] == pytest.approx(c.raw.qc[100], abs=1e-4)


def test_excel_roundtrip(tmp_path, col):
    c = col["DEMO-01"]
    p = tmp_path / "x.xlsx"
    ca.to_excel(c, p)
    back = ca.parse_xlsx(p, "x.xlsx").process()
    assert back.header.test_id == "DEMO-01" and back.header.gwl == 1.5
    assert back.raw.qc[5] == pytest.approx(c.raw.qc[5], rel=1e-6)


def test_csv_exports(col):
    s = ca.to_csv(col["DEMO-01"])
    assert s.splitlines()[0].startswith('"Depth [m]","Length [m]"')
    assert len(s.splitlines()) == len(col["DEMO-01"].raw.L) + 1
    lay = ca.layers_csv(col.cpts).splitlines()
    assert lay[0].startswith("Test ID,Top [m]") and len(lay) > 3
    assert ca.csv_all(col.cpts).count("\n") == sum(len(c.raw.L) for c in col.cpts)


def test_dataframe(col):
    df = col["DEMO-01"].to_dataframe()
    assert "Ic [-]" in df.columns and len(df) == len(col["DEMO-01"].raw.L)


@pytest.mark.parametrize("standard", ["intl", "dutch"])
def test_plots(col, standard):
    c = col["DEMO-01"]
    s = col.settings.copy()
    s.plot["standard"] = standard
    s.plot["zPage"] = 8
    s.plot["tracks"].append({"k": "Qtn", "page": 2, "w": 1})
    pages = ca.plot_pages(c, s)
    assert len(pages) == (2 if standard == "dutch" else 4)
    for i in range(len(pages)):
        ca.plot_log(c, i, s, col.dissipations_for(c))
    ca.plot_sbt_chart(c)
    ca.plot_dissipation(col.dissipations[0])
    ca.plot_compare(col.cpts, "qc", "tile")
    ca.plot_compare(col.cpts, "Ic", "overlay")


def test_cli(tmp_path):
    assert main(["export", str(FIX), "-o", str(tmp_path), "--all"]) == 0
    names = {p.name for p in tmp_path.iterdir()}
    assert {"CPT_logs.pdf", "CPT_layers.csv", "CPT_all.csv", "DEMO-01.xlsx", "DEMO-01.gef", "DEMO-01.png", "DEMO-01_SBT.png"} <= names


def test_latin1_gef_written_back_unchanged(tmp_path):
    raw = (FIX / "DEMO-01.gef").read_bytes().replace(b"mm2, Nom.", "mm², Nom.".encode("latin-1"))
    (tmp_path / "L1.gef").write_bytes(raw)
    c = ca.read(tmp_path / "L1.gef")
    assert c.encoding == "latin-1"
    out = ca.save_gef(c, tmp_path / "out.gef").read_bytes().split(b"\r\n")
    assert [ln for ln in out if not ln.startswith(b"#COMMENT= Saved")] == raw.split(b"\r\n")
