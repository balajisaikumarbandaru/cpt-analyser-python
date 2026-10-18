"""CPT Analyser – cone penetration test reader and interpreter (Python version).

Quick start::

    import cpt_analyser as ca

    col = ca.load("data/")                 # GEF, GME, CSV, Excel, settings files or folders
    cpt = col[0]
    df = cpt.to_dataframe()                # raw + derived values
    layers = cpt.layers_dataframe()
    ca.plot_log(cpt).savefig("log.png", dpi=200)
    ca.save_log_pdf(col.cpts, "all.pdf", collection=col)

Change a factor and recalculate::

    col.settings.factors["gwlDefault"] = 2.0
    col.process()
"""
from .collection import Collection, load, read
from .constants import SIGNALS, ZONES
from .exports import csv_all, layers_csv, save_gef, to_csv, to_excel, to_gef
from .models import CPT, Dissipation, Header, RawData
from .plotting import plot_compare, plot_dissipation, plot_log, plot_log_pages, plot_pages, plot_sbt_chart, save_log_pdf
from .processing import make_layers, process_cpt, process_diss, spike_filter, zone1990
from .readers import parse_delimited, parse_gef, parse_gme, parse_xlsx
from .settings import Settings

__version__ = "0.1.0"

__all__ = [
    "Collection", "load", "read", "Settings", "CPT", "Dissipation", "Header", "RawData", "SIGNALS", "ZONES",
    "parse_gef", "parse_gme", "parse_delimited", "parse_xlsx",
    "process_cpt", "process_diss", "make_layers", "spike_filter", "zone1990",
    "plot_log", "plot_log_pages", "plot_pages", "plot_sbt_chart", "plot_dissipation", "plot_compare", "save_log_pdf",
    "to_csv", "csv_all", "layers_csv", "to_excel", "to_gef", "save_gef",
]
