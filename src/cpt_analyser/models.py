"""Data containers: header, raw readings, CPT and dissipation test."""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from typing import Any

from .settings import Settings


@dataclass
class Header:
    test_id: str = ""
    project: str = ""
    job_no: str = ""
    client: str = ""
    location: str = ""
    cone_type: str = ""
    date: str = ""          # YYYY-MM-DD
    remarks: str = ""
    x: float | None = None  # easting
    y: float | None = None  # northing
    gl: float | None = None  # ground level [datum]
    gwl: float | None = None  # water level [m below ground level]
    predrill: float = 0.0
    alpha: float | None = None  # net area ratio
    beta: float | None = None
    sleeve: float | None = None  # cone tip to sleeve centre [m]
    cone_area: float | None = None  # [mm²]
    warning: str = ""

    def copy(self) -> Header:
        return copy.copy(self)


RAW_KEYS = ("qc", "fs", "u1", "u2", "u3", "I")


@dataclass
class RawData:
    """Measured readings, one list per channel. Units: m, MPa, degrees, s."""
    L: list = field(default_factory=list)    # penetration length
    qc: list = field(default_factory=list)
    fs: list = field(default_factory=list)
    u1: list = field(default_factory=list)
    u2: list = field(default_factory=list)
    u3: list = field(default_factory=list)
    I: list = field(default_factory=list)    # resultant inclination
    t: list = field(default_factory=list)    # time
    zc: list | None = None                   # corrected depth from the file, if any
    x: dict = field(default_factory=dict)    # other columns: Qst, Qtot, x_<name> …
    x_meta: dict = field(default_factory=dict)  # name / unit / default scale of the x_ columns

    def channel(self, k: str) -> list:
        return getattr(self, k) if k in RAW_KEYS or k in ("L", "t") else self.x[k]

    def edit_keys(self) -> list[str]:
        return list(RAW_KEYS) + list(self.x)


@dataclass
class CPT:
    file: str
    header: Header
    raw: RawData
    source: str = "gef"            # gef, gme, csv, xlsx, new
    settings: Settings | None = None   # per-CPT settings; None = use the collection / default settings
    gef: Any = None                 # original GEF layout, for lossless saving
    kind: str = "cpt"
    data: dict = field(default_factory=dict)    # calculated values (see processing.process_cpt)
    layers: list = field(default_factory=list)
    original: dict = field(default_factory=dict)  # copy of the raw channels as opened
    encoding: str = "utf-8"         # text encoding of the source file (GEF files are written back with it)

    def __post_init__(self):
        if not self.original:
            self.original = {k: list(self.raw.channel(k)) for k in self.raw.edit_keys()}
        L = self.raw.L
        if any(L[i] < L[i - 1] for i in range(1, len(L))):
            self.header.warning = "Penetration length is not monotonic"

    @property
    def test_id(self) -> str:
        return self.header.test_id

    def edited(self) -> set[tuple[str, int]]:
        """(channel, row) pairs whose raw value differs from the file as opened."""
        out = set()
        for k, orig in self.original.items():
            cur = self.raw.channel(k)
            for i, (a, b) in enumerate(zip(orig, cur)):
                if not (a == b or (_nan(a) and _nan(b))):
                    out.add((k, i))
        return out

    def reset_edits(self):
        for k, orig in self.original.items():
            self.raw.channel(k)[:] = orig

    def process(self, settings: Settings | None = None):
        from .processing import process_cpt
        process_cpt(self, settings)
        return self

    def to_dataframe(self):
        """All raw and calculated values as a pandas DataFrame (one row per reading)."""
        import pandas as pd

        from .exports import data_columns
        cols = {}
        for key, label, unit, _dp, raw in data_columns(self):
            vals = self.raw.channel(key) if raw else self.data.get(key, [])
            cols[f"{label} [{unit}]"] = list(vals)
        return pd.DataFrame(cols)

    def layers_dataframe(self):
        import pandas as pd

        from .constants import ZONES
        return pd.DataFrame([{**lay, "thickness": lay["bottom"] - lay["top"], "description": ZONES[lay["zone"]][0]}
                             for lay in self.layers])

    def __repr__(self):
        z = [v for v in self.data.get("z", []) if math.isfinite(v)]
        return f"CPT({self.test_id!r}, {len(self.raw.L)} rows, {max(z) if z else float('nan'):.2f} m, source={self.source})"


@dataclass
class Dissipation:
    file: str
    header: Header
    t: list
    u: list
    qc: list
    depth: float | None = None
    parent: str = ""
    loc: str = "u2"
    settings: Settings | None = None
    kind: str = "diss"
    encoding: str = "utf-8"
    # u0_own / ui_own override the calculated values; T50 time factor; pct = second time line (t70 …)
    options: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)

    def __post_init__(self):
        o = {"u0_own": None, "ui_own": None, "Ir": 100, "T50": 0.118 if self.loc == "u1" else 0.245,
             "pct": 70, "axis": "log", "show_qc": True}
        o.update(self.options)
        self.options = o

    @property
    def test_id(self) -> str:
        return self.header.test_id

    def process(self, settings: Settings | None = None, cpts=()):
        from .processing import process_diss
        process_diss(self, settings, cpts)
        return self

    def __repr__(self):
        r = self.result
        return f"Dissipation({self.test_id!r}, depth={self.depth}, t50={r.get('t50')}, ch={r.get('ch')})"


def _nan(v) -> bool:
    return isinstance(v, float) and math.isnan(v)
