"""Quick tour of the Python API. Run from the repository root:  python examples/quickstart.py"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import cpt_analyser as ca  # noqa: E402

out = Path("cpt_output")
out.mkdir(exist_ok=True)

# 1. open files and folders (GEF, GME pairs, CSV, Excel, .cptset.json settings)
col = ca.load("tests/fixtures")
print(col.cpts, col.dissipations, col.errors, sep="\n")

# 2. one sounding: header, calculated values, layers
cpt = col["DEMO-01"]
print(cpt.header.test_id, cpt.header.gwl, cpt.header.gl)
df = cpt.to_dataframe()                     # every raw and derived column
print(df[["Depth [m]", "qc [MPa]", "Ic [-]", "SBT [zone]"]].head())
print(cpt.layers_dataframe()[["top", "bottom", "zone", "description", "qc", "Dr", "Su"]])

# 3. change factors and recalculate everything
col.settings.factors.update(gwlDefault=2.0, gammaMethod="rob", minLayer=0.5)
col.process()

# 4. plots
ca.plot_log(cpt, 0, dissipations=col.dissipations_for(cpt)).savefig(out / "DEMO-01_log.png", dpi=200)
ca.plot_sbt_chart(cpt).savefig(out / "DEMO-01_SBT.png", dpi=150)
ca.plot_dissipation(col.dissipations[0]).savefig(out / "DEMO-01_D1.png", dpi=150)
ca.plot_compare(col.cpts, "qc", mode="tile").savefig(out / "compare_qc.png", dpi=150)
ca.save_log_pdf(col.cpts, out / "all_logs.pdf", collection=col)

# 5. data exports
(out / "DEMO-01.csv").write_text(ca.to_csv(cpt), encoding="utf-8")
ca.to_excel(cpt, out / "DEMO-01.xlsx")
(out / "layers.csv").write_text(ca.layers_csv(col.cpts), encoding="utf-8")

# 6. correct a reading and save the GEF – the original layout is kept, only that value changes
cpt.raw.qc[10] = 1.25
cpt.process(col.settings)
ca.save_gef(cpt, out / "DEMO-01_edited.gef")

# 7. save the settings for the HTML tool or the command line
col.settings.save(out / "site.cptset.json")
print("written to", out.resolve())
