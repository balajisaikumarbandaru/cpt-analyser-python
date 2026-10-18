"""Browser front end for the Python CPT Analyser.

    pip install -e ".[app]"
    streamlit run app/streamlit_app.py
"""
from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import cpt_analyser as ca  # noqa: E402
from cpt_analyser.constants import SIGNALS, ZONES  # noqa: E402
from cpt_analyser.exports import file_stem  # noqa: E402

st.set_page_config(page_title="CPT Analyser", layout="wide")
st.title("CPT Analyser")

DEMO = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


@st.cache_data(show_spinner=False)
def _store(files: tuple[tuple[str, bytes], ...]) -> str:
    d = Path(tempfile.mkdtemp(prefix="cpt_"))
    for name, data in files:
        (d / Path(name).name).write_bytes(data)
    return str(d)


def png(fig, dpi=130) -> bytes:
    b = io.BytesIO()
    fig.savefig(b, format="png", dpi=dpi)
    return b.getvalue()


# ------------------------------------------------------------------ input
with st.sidebar:
    st.header("Files")
    up = st.file_uploader("GEF, GME (.0xx + .1xx), CSV, Excel, .cptset.json", accept_multiple_files=True)
    use_demo = st.checkbox("Use demo data", value=not up)
    folder = _store(tuple((f.name, f.getvalue()) for f in up)) if up else None

    st.header("Factors")
    s = ca.Settings()
    F, P = s.factors, s.plot
    F["gwlDefault"] = st.number_input("Default water level [m BGL] (if not in file)", value=float(F["gwlDefault"]), step=0.1)
    F["gammaMethod"] = st.selectbox("Unit weight", ["const", "rob"], format_func=lambda v: {"const": "constant above / below water",
                                                                                         "rob": "Robertson & Cabal 2010"}[v])
    c1, c2 = st.columns(2)
    F["gDry"] = c1.number_input("γ dry [kN/m³]", value=float(F["gDry"]))
    F["gWet"] = c2.number_input("γ wet [kN/m³]", value=float(F["gWet"]))
    F["alphaDefault"] = c1.number_input("Default α", value=float(F["alphaDefault"]), step=0.05)
    F["filterPasses"] = c2.number_input("Spike filter passes", value=int(F["filterPasses"]), min_value=0, max_value=10)
    F["nkMin"] = c1.number_input("Nk min", value=float(F["nkMin"]))
    F["nkMax"] = c2.number_input("Nk max", value=float(F["nkMax"]))
    F["minLayer"] = st.number_input("Minimum layer thickness [m]", value=float(F["minLayer"]), step=0.1)
    F["shiftFs"] = st.selectbox("fs shift", ["auto", "on", "off"], help="auto = raw GME data only")
    F["uLoc"] = st.selectbox("Pore pressure filter", ["auto", "u1", "u2", "u3"])
    F["inclCorr"] = st.checkbox("Depth correction for inclination", value=True)
    F["datum"] = st.text_input("Level datum", value=F["datum"])

    st.header("Plot")
    P["standard"] = st.radio("Standard", ["intl", "dutch"], horizontal=True, format_func=lambda v: {"intl": "International", "dutch": "Dutch"}[v])
    c1, c2 = st.columns(2)
    P["size"] = c1.selectbox("Paper", ["A4", "A3"])
    P["orient"] = c2.selectbox("Orientation", ["portrait", "landscape"])
    keys = list(SIGNALS)
    tracks = st.multiselect("Graphs (international)", keys, default=[t["k"] for t in P["tracks"]],
                            format_func=lambda k: f"{SIGNALS[k]['sym']} – {SIGNALS[k]['name']}")
    P["tracks"] = [{"k": k, "page": 1, "w": 1} for k in tracks]
    zp = st.number_input("Depth per page [m] (0 = all on one page)", value=0.0, step=5.0)
    P["zPage"] = zp or None
    P["color"] = not st.checkbox("Black and white", value=False)
    settings_file = st.file_uploader("…or load a settings file", type=["json"])
    if settings_file:
        s = ca.Settings.from_dict(json.loads(settings_file.getvalue()))

paths = [folder] if folder else ([DEMO] if use_demo else [])
if not paths:
    st.info("Upload files in the sidebar, or tick *Use demo data*.")
    st.stop()
col = ca.load(*paths, settings=s)
# raw-value edits survive Streamlit reruns
edits = st.session_state.setdefault("edits", {})
for c in col.cpts:
    for k, vals in edits.get(c.test_id, {}).items():
        c.raw.channel(k)[:] = vals
    if c.test_id in edits:
        c.process(col.settings)
for e in col.errors:
    st.warning(e)
if not col.all():
    st.stop()

names = [c.test_id for c in col.cpts] + [d.test_id for d in col.dissipations]
pick = st.selectbox("Sounding", names)
obj = col[pick]

if obj.kind == "diss":
    o = obj.options
    c1, c2, c3, c4 = st.columns(4)
    o["axis"] = c1.selectbox("Time axis", ["log", "sqrt", "linear"])
    o["Ir"] = c2.number_input("Rigidity index Ir", value=100.0)
    o["pct"] = c3.number_input("Second time line [%]", value=70, min_value=1, max_value=99)
    u0 = c4.number_input("Own u0 [kPa] (0 = calculated)", value=0.0)
    o["u0_own"] = u0 / 1000 if u0 else None
    obj.process(col.settings, col.cpts)
    st.image(png(ca.plot_dissipation(obj)))
    r = obj.result
    st.write({"u0 [kPa]": r["u0"] * 1000, "ui [kPa]": r["ui"] * 1000, "t50 [s]": r["t50"], f"t{o['pct']} [s]": r["tp"], "ch [m²/s]": r["ch"]})
    st.download_button("Excel", ca.to_excel(obj, settings=col.settings), file_stem(obj) + ".xlsx")
    st.stop()

tab_log, tab_chart, tab_layers, tab_data, tab_cmp, tab_exp = st.tabs(["Log", "SBT chart", "Layers", "Data", "Compare", "Export"])
with tab_log:
    pages = ca.plot_pages(obj, col.settings)
    page = st.number_input("Page", 1, len(pages), 1) - 1 if len(pages) > 1 else 0
    st.image(png(ca.plot_log(obj, page, col.settings, col.dissipations_for(obj)), 160))
    if obj.header.warning:
        st.warning(obj.header.warning)
with tab_chart:
    st.image(png(ca.plot_sbt_chart(obj, col.settings)))
with tab_layers:
    df = obj.layers_dataframe()
    if len(df):
        df["fs"] = df["fs"] * 1000
        df = df.rename(columns={"top": "Top [m]", "bottom": "Bottom [m]", "thickness": "Thickness [m]", "zone": "SBT", "description": "Description",
                                "qc": "qc [MPa]", "fs": "fs [kPa]", "Rf": "Rf [%]", "Dr": "Dr [%]", "phi": "φ [°]", "Su": "Su Nkmin [kPa]",
                                "Su2": "Su Nkmax [kPa]"})
    st.dataframe(df.round(3), width="stretch")
with tab_data:
    st.caption("Edit raw readings in the table; everything else is recalculated when you press Apply.")
    raw = pd.DataFrame({"L [m]": obj.raw.L, "qc [MPa]": obj.raw.qc, "fs [MPa]": obj.raw.fs, f"{obj.data['uLoc']} [MPa]": getattr(obj.raw, obj.data["uLoc"])})
    edited = st.data_editor(raw, width="stretch", height=300, disabled=["L [m]"])
    c1, c2 = st.columns([1, 4])
    if c1.button("Apply edits"):
        loc = obj.data["uLoc"]
        edits[obj.test_id] = {"qc": edited["qc [MPa]"].tolist(), "fs": edited["fs [MPa]"].tolist(), loc: edited[f"{loc} [MPa]"].tolist()}
        st.rerun()
    if c2.button("Undo all edits") and obj.test_id in edits:
        del edits[obj.test_id]
        st.rerun()
    if obj.edited():
        st.success(f"{len(obj.edited())} value(s) edited – they are kept in the GEF download.")
    st.dataframe(obj.to_dataframe(), width="stretch", height=400)
with tab_cmp:
    c1, c2 = st.columns(2)
    sig = c1.selectbox("Signal", ["qc", "fs", "u2", "Rf", "Ic", "qt", "Qtn", "N60", "Dr", "Su"])
    mode = c2.radio("Mode", ["tile", "overlay"], horizontal=True)
    sel = st.multiselect("CPTs", [c.test_id for c in col.cpts], default=[c.test_id for c in col.cpts[:8]])
    st.image(png(ca.plot_compare([col[x] for x in sel], sig, mode, col.settings)))
with tab_exp:
    stem = file_stem(obj)
    c1, c2, c3 = st.columns(3)
    c1.download_button("CSV (this CPT)", ca.to_csv(obj, col.settings), stem + ".csv")
    c1.download_button("Excel (this CPT)", ca.to_excel(obj, settings=col.settings), stem + ".xlsx")
    c1.download_button("GEF (this CPT)", ca.to_gef(obj, col.settings).encode(obj.encoding, errors="replace"),
                       stem + ("_edited" if obj.edited() else "") + ".gef")
    c2.download_button("Layers, all CPTs (CSV)", ca.layers_csv(col.cpts), "CPT_layers.csv")
    c2.download_button("All CPTs in one CSV", ca.csv_all(col.cpts, col.settings), "CPT_all.csv")
    if c3.button("Build PDF of all logs"):
        b = io.BytesIO()
        ca.save_log_pdf(col.cpts, b, col.settings, collection=col)
        c3.download_button("Download PDF", b.getvalue(), "CPT_logs.pdf")
    c3.download_button("Settings file", json.dumps(col.settings.to_dict(), indent=2), "settings.cptset.json")
    st.caption("Zones: " + ", ".join(f"{i} {z[1]}" for i, z in enumerate(ZONES) if i))
