"""Soil behaviour type zones and the catalogue of plottable signals."""
from __future__ import annotations

PA = 100.0  # atmospheric pressure, kPa

# Robertson (1990) soil behaviour type zones: (name, short name, colour)
ZONES = [
    ("Not classified", "n/a", "#ffffff"),
    ("Sensitive, fine grained", "Sensitive", "#c94f3d"),
    ("Organic soils – peat", "Organic", "#7b4a2a"),
    ("Clays – silty clay to clay", "Clay", "#4f7cac"),
    ("Silt mixtures – clayey silt to silty clay", "Silt mix", "#5aa6a0"),
    ("Sand mixtures – silty sand to sandy silt", "Sand mix", "#9cc96b"),
    ("Sands – clean sand to silty sand", "Sand", "#efcc55"),
    ("Gravelly sand to dense sand", "Gravelly sand", "#e58e37"),
    ("Very stiff sand to clayey sand", "V. stiff sand", "#a3a3a3"),
    ("Very stiff, fine grained", "V. stiff fine", "#5e5e5e"),
]

# Ic boundaries of zones 2–7: (Ic from, Ic to, zone)
IC_BANDS = [(0, 1.31, 7), (1.31, 2.05, 6), (2.05, 2.6, 5), (2.6, 2.95, 4), (2.95, 3.6, 3), (3.6, 9, 2)]

GREY_ZONE = [255, 200, 40, 70, 110, 150, 230, 185, 130, 90]  # black-and-white plot fills


class Signal(dict):
    """name, sym, unit, col, def (min, max), log – same fields as ``SIG`` in the HTML."""

    def __getattr__(self, k):
        return self[k]


def _s(name, sym, unit, col, lo, hi, log=False):
    return Signal(name=name, sym=sym, unit=unit, col=col, default=(lo, hi), log=log)


# Keys are the same as the HTML version, so plot settings files work in both.
SIGNALS: dict[str, Signal] = {
    "qc": _s("Cone resistance", "qc", "MPa", "#1d4ed8", 0, 30),
    "fs": _s("Sleeve friction", "fs", "MPa", "#c0262d", 0, 0.3),
    "u2": _s("Pore pressure (selected filter, u0 dashed)", "u", "MPa", "#0f766e", -0.1, 1),
    "u1": _s("Pore pressure u1 (cone face)", "u1", "MPa", "#0d9488", -0.1, 1),
    "u3": _s("Pore pressure u3 (behind sleeve)", "u3", "MPa", "#115e59", -0.1, 1),
    "Rf": _s("Friction ratio", "Rf", "%", "#7c3aed", 0, 10),
    "I": _s("Inclination", "I", "°", "#6b7280", 0, 10),
    "v": _s("Penetration rate", "v", "cm/s", "#6b7280", 0, 4),
    "qt": _s("Corrected cone resistance", "qt", "MPa", "#1e3a8a", 0, 30),
    "qn": _s("Net cone resistance", "qn", "MPa", "#1e40af", 0, 30),
    "qe": _s("Effective cone resistance", "qe", "MPa", "#3b5bdb", 0, 30),
    "du": _s("Excess pore pressure", "Δu", "MPa", "#0e7490", -0.2, 1),
    "Bq": _s("Pore pressure ratio", "Bq", "-", "#0f766e", -0.2, 1),
    "uqc": _s("Pore pressure ratio u/qc", "u/qc", "-", "#0f766e", -0.2, 1),
    "Qt": _s("Normalised cone resistance", "Qt", "-", "#1d4ed8", 1, 1000, True),
    "Fr": _s("Normalised friction ratio", "Fr", "%", "#7c3aed", 0.1, 10, True),
    "Ic": _s("Soil behaviour type index (1990)", "Ic", "-", "#111827", 1, 4),
    "Icn": _s("SBT index Ic (2009, Qtn)", "Ic,n", "-", "#374151", 1, 4),
    "Qtn": _s("Normalised cone resistance (2009)", "Qtn", "-", "#1d4ed8", 1, 1000, True),
    "gam": _s("Unit weight", "γ", "kN/m³", "#6b7280", 12, 22),
    "sv": _s("Total vertical stress", "σv", "kPa", "#6b7280", 0, 400),
    "svp": _s("Effective vertical stress", "σ'v", "kPa", "#374151", 0, 300),
    "Dr": _s("Relative density (Baldi)", "Dr", "%", "#b45309", 0, 100),
    "DrNC": _s("Relative density, normally consolidated", "Dr NC", "%", "#b45309", 0, 100),
    "DrOC": _s("Relative density, over-consolidated", "Dr OC", "%", "#92400e", 0, 100),
    "phi": _s("Friction angle", "φ", "°", "#9a3412", 25, 50),
    "Su": _s("Undrained shear strength (Nk min / max)", "Su", "kPa", "#1f6f43", 0, 200),
    "N60": _s("Equivalent SPT N60", "N60", "-", "#6d28d9", 0, 60),
    "Qst": _s("Total friction (mechanical CPT)", "Qst", "kN", "#9f1239", 0, 50),
    "Qtot": _s("Total force (mechanical CPT)", "Qt", "kN", "#7f1d1d", 0, 100),
}

EXTRA_COLOURS = ["#7a5c2e", "#4d7c0f", "#a21caf", "#0369a1", "#b91c1c", "#57534e"]
