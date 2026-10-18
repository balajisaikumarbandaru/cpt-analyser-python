# Equations

Units: qc, fs, u, qt, qn in MPa; stresses in kPa; pa = 100 kPa. Function names refer to `src/cpt_analyser/processing.py`.

| Symbol | Unit | Parameter | Equation |
|---|---|---|---|
| qc, fs | MPa | cone resistance, sleeve friction | measured; fs shifted by the cone–sleeve distance for raw data (`shiftFs`) |
| u1, u2, u3 | MPa | pore pressure | measured; filter location from `uLoc` (auto: u2, else u1, else u3) |
| I | ° | inclination | measured resultant, or acos(cos Ix · cos Iy) |
| z | m | depth | corrected depth column if present, else zᵢ = zᵢ₋₁ + ΔL · cos I (`inclCorr`) |
| Rf | % | friction ratio | fs / qc × 100 |
| u0 | MPa | hydrostatic pore pressure | γw · (z − zw) / 1000 below the water level, else 0 |
| u/qc | – | pore pressure ratio | u / qc |
| qt | MPa | corrected cone resistance | qc + (1 − α) · u2 (only when the filter is u2) |
| Δu | MPa | excess pore pressure | u − u0 |
| qe | MPa | effective cone resistance | qc − u |
| γ | kN/m³ | unit weight | γdry above / γwet below the water level, or Robertson & Cabal (2010): γ/γw = 0.27 log Rf + 0.36 log(qt/pa) + 1.236, limited to 12–23 |
| σv | kPa | total vertical stress | Σ γ · Δz (first interval split at the water level) |
| σ′v | kPa | effective vertical stress | σv − u0 |
| qn | MPa | net cone resistance | qt − σv |
| Bq | – | pore pressure ratio | Δu / qn |
| Qt | – | normalised cone resistance | qn / σ′v |
| Fr | % | normalised friction ratio | fs / qn × 100 |
| Ic | – | SBT index | √[(a − log Qt)² + (log Fr + b)²], a = 3.47, b = 1.22 |
| SBT | zone | Robertson (1990) | zone 1: Qt < 12 e^(−1.4 Fr); zones 8/9: Fr > 1.5 and Qt > 1/(0.005(Fr−1) − 0.0003(Fr−1)² − 0.002), 8 if Fr < 4.5; zones 2–7 by Ic: > 3.6 → 2, > 2.95 → 3, > 2.6 → 4, > 2.05 → 5, > 1.31 → 6, else 7 (`zone1990`) |
| Qtn, Ic,n | – | Robertson (2009) | Qtn = (qn/pa)(pa/σ′v)ⁿ, n = 0.381 Ic,n + 0.05 σ′v/pa − 0.15 ≤ 1, iterated |
| Dr | % | relative density (Baldi et al. 1986) | 1/C2 · ln[qc / (C0 · σ′vᶜ¹)] (kPa), NC: 157, 0.55, 2.41; OC: 181, 0.55, 2.61; 0–100 % |
| φ′ | ° | friction angle | arctan[a + b · ln(qc / σ′v)], a = 0.105, b = 0.16 |
| Su | kPa | undrained shear strength | (qt − σv) / Nk, Nk = 12 … 20 |
| N60 | – | equivalent SPT (Jefferies & Davies) | (qc/pa) / [8.5 (1 − Ic/4.6)] |
| v | cm/s | penetration rate | ΔL / Δt over ±2 samples |
| ch | m²/s | coefficient of consolidation | T* · r² · √Ir / t50 (Teh & Houlsby 1991); T* = 0.245 (u2), 0.118 (u1) |
| GME | – | raw data conversion | qc = ch1·cal1/10, fs = ch2·cal2/10 (− qc/15 for subtraction cones), u = ch3·cal3/100, L = pre-drill + (index − first index) · 0.01 m |

## Spike filter (`spike_filter`)

Per pass: noise = 1.4826 · median |xᵢ − (xᵢ₋₁ + xᵢ₊₁)/2|. A sample that is a local maximum or minimum and differs from
the mean of its neighbours by more than max(k · noise, 5 % of that mean) is replaced by the mean. N passes remove peaks up
to about N samples wide.

## Layers (`make_layers`)

Consecutive samples with the same SBT zone form a layer (boundaries halfway between samples). While a layer is thinner
than `minLayer`, the thinnest is merged into the neighbour whose mean Ic is closest; the merged layer takes the zone that
covers most of its thickness. Layer values are the means of the samples.

## Dissipation (`process_diss`)

u0 from the test depth and the water level (test header, else parent CPT, else default). ui is the early peak within the
first 30 % of the test, or the first reading when u rises towards u0. t50 / t<sub>p</sub> is the first time after ui at
which u reaches ui − (ui − u0) · U, interpolated linearly.
