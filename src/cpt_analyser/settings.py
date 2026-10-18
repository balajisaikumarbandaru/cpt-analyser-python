"""Processing factors and plot settings.

The JSON layout is the same as the ``.cptset.json`` files written by the HTML
version (``{"factors": {...}, "plot": {...}, "scales": {...}}``), so a settings
file can be shared between both tools.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .constants import SIGNALS

DEFAULT_FACTORS = {
    # unit weights [kN/m³], water level [m BGL], cone factors
    "gw": 10.0, "gDry": 18, "gWet": 20, "gammaMethod": "const",      # 'const' or 'rob' (Robertson & Cabal 2010)
    "gwlDefault": 1.0, "alphaDefault": 0.8, "sleeveDefault": 0.08,   # used when the file header has none
    # relative density (Baldi) and friction angle
    "drMode": "NC", "drC0": 157, "drC1": 0.55, "drC2": 2.41, "phiA": 0.105, "phiB": 0.16,
    # undrained shear strength cone factors, Ic equation constants
    "nkMin": 12, "nkMax": 20, "icA": 3.47, "icB": 1.22,
    # processing
    "filterPasses": 1, "filterK": 4,      # spike filter
    "shiftFs": "auto",                    # 'auto' (raw GME only), 'on', 'off'
    "inclCorr": True,                     # depth correction for inclination
    "soilLimit": True,                    # Dr/phi only for Ic < 2.6, Su only for Ic >= 2.6
    "minLayer": 0.3,                      # minimum layer thickness [m]
    "uLoc": "auto",                       # 'auto', 'u1', 'u2', 'u3'
    "datum": "mSHD", "company": "",
}

DEFAULT_PLOT = {
    "standard": "intl",           # 'intl' or 'dutch'
    "size": "A4", "orient": "portrait",
    "zMin": None, "zMax": None, "zPage": None,   # depth range and depth per page [m]
    "tracks": [{"k": "qc", "page": 1, "w": 1}, {"k": "fs", "page": 1, "w": 1}, {"k": "u2", "page": 1, "w": 1},
               {"k": "Rf", "page": 1, "w": 1}, {"k": "Ic", "page": 1, "w": 1}],
    "dutch": {"l1": "qc", "l2": "fs", "r": "Rf"},
    "sbt": True, "grid": True, "color": True, "chartColour": "depth",   # chartColour: 'depth' or 'zone'
}


def default_scale(key: str, extra_meta: dict | None = None) -> dict:
    s = SIGNALS.get(key)
    if s is None and extra_meta and key in extra_meta:
        lo, hi = extra_meta[key]["default"]
        return {"min": lo, "max": hi, "log": False}
    if s is None:
        return {"min": 0, "max": 1, "log": False}
    return {"min": s.default[0], "max": s.default[1], "log": bool(s.log)}


class Settings:
    """Factors, plot layout and axis scales. Edit the dicts directly, e.g.
    ``s.factors["gwlDefault"] = 2.0`` or ``s.scales["qc"]["max"] = 40``."""

    def __init__(self, factors: dict | None = None, plot: dict | None = None, scales: dict | None = None):
        self.factors = {**copy.deepcopy(DEFAULT_FACTORS), **(factors or {})}
        if self.factors["shiftFs"] is True:
            self.factors["shiftFs"] = "auto"
        if self.factors["shiftFs"] is False:
            self.factors["shiftFs"] = "off"
        p = {**copy.deepcopy(DEFAULT_PLOT), **(plot or {})}
        p["dutch"] = {**DEFAULT_PLOT["dutch"], **((plot or {}).get("dutch") or {})}
        tracks = []
        for x in p.get("tracks") or []:
            if isinstance(x, str):
                tracks.append({"k": x, "page": 1, "w": 1})
            elif x.get("k"):
                tracks.append({"k": x["k"], "page": _int_or(x.get("page"), 1), "w": _num_or(x.get("w"), 1)})
        p["tracks"] = tracks
        self.plot = p
        self.scales = {k: dict(v) for k, v in (scales or {}).items()}
        for k in SIGNALS:
            self.scales.setdefault(k, default_scale(k))

    # -- scales -------------------------------------------------------------
    def scale(self, key: str, extra_meta: dict | None = None) -> dict:
        if key not in self.scales:
            self.scales[key] = default_scale(key, extra_meta)
        return self.scales[key]

    # -- io -----------------------------------------------------------------
    def to_dict(self) -> dict:
        return {"factors": copy.deepcopy(self.factors), "plot": copy.deepcopy(self.plot), "scales": copy.deepcopy(self.scales)}

    @classmethod
    def from_dict(cls, d: dict) -> Settings:
        if "factors" not in d:
            raise ValueError("not a settings file")
        return cls(d.get("factors"), d.get("plot"), d.get("scales"))

    @classmethod
    def load(cls, path) -> Settings:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    def copy(self) -> Settings:
        return Settings.from_dict(self.to_dict())

    def __repr__(self):
        changed = {k: v for k, v in self.factors.items() if DEFAULT_FACTORS.get(k) != v}
        return f"Settings(changed factors={changed})"


def _num_or(v, d):
    try:
        x = float(v)
        return x if x else d
    except (TypeError, ValueError):
        return d


def _int_or(v, d):
    x = _num_or(v, d)
    return int(x) if float(x).is_integer() else x
