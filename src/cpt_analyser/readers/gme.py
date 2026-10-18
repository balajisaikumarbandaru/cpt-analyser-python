"""GME (Geomil raw format): header ``*.0xx`` + data ``*.1xx`` with calibration factors.

Conversion (verified against GEF files of the same tests):
qc = ch1·cal1/10, fs = ch2·cal2/10, u = ch3·cal3/100 MPa, L = pre-drill + (index − first index)·0.01 m.
"""
from __future__ import annotations

import math
import re

from .._js import NAN, base_name, js_number, num, opt_num
from ..models import CPT, Header, RawData

GME_RE = re.compile(r"\.[01][A-Za-z0-9]{0,3}$")
STD_EXT = re.compile(r"\.(gef|csv|txt|xlsx|xls|json)$", re.I)


def is_gme(name: str) -> bool:
    return bool(GME_RE.search(name)) and not STD_EXT.search(name)


def gme_pair_key(name: str):
    """('base|suffix', '0' or '1') – the .0xx header and .1xx data file share the key."""
    m = re.match(r"^(.*)\.([01])([A-Za-z0-9]*)$", name)
    return (m.group(1) + "|" + m.group(3), m.group(2)) if m else (None, None)


def parse_gme(header_text: str, data_text: str, name: str = "file.1") -> CPT:
    kv: dict[str, str] = {}
    for line in re.split(r"\r?\n", header_text):
        m = re.match(r"^\s*([^:]+?)\s*:(.*)$", line)
        if m and m.group(1).lower() not in kv:
            kv[m.group(1).lower()] = m.group(2).strip()
    cal = []
    for n in (1, 2, 3, 4):
        m = re.search(r"Cal Factor\.\s*" + str(n) + r"\s*:\s*([-\d.E+]+)", header_text, re.I)
        cal.append(num(m.group(1)) if m else NAN)
    if not math.isfinite(cal[0]):
        raise ValueError("GME header without calibration factors")
    n_ch = js_number(kv.get("nr channels") or 3)
    pre = num(kv.get("pre drill"))
    pre = pre if math.isfinite(pre) else 0.0
    rows = []
    for line in re.split(r"\r?\n", data_text):
        s = re.sub(r"^\||\|$", "", line.strip())
        if s:
            rows.append([js_number(x) for x in s.split("|")])
    if not rows:
        raise ValueError("GME data file is empty")
    raw = RawData()
    nf = len(rows[0])
    i0 = rows[0][nf - 4]
    # subtraction cone (type S): channel 2 carries tip + sleeve load; standard sleeve area = 15 × tip area
    subtraction = bool(re.match(r"s", kv.get("conetype") or "", re.I))
    for r in rows:
        if len(r) != nf or not all(math.isfinite(v) for v in r):
            continue
        raw.L.append(float(f"{pre + (r[nf - 4] - i0) * 0.01:.4f}"))
        qc = r[0] * cal[0] / 10
        raw.qc.append(qc)
        raw.fs.append(r[1] * cal[1] / 10 - (qc / 15 if subtraction else 0) if n_ch >= 2 else NAN)
        raw.u2.append(r[2] * cal[2] / 100 if n_ch >= 3 else NAN)
        raw.u1.append(NAN)
        raw.u3.append(NAN)
        raw.I.append(NAN)
        raw.t.append(r[nf - 2] + r[nf - 1] / 100)
    h = Header()
    h.project = kv.get("client name") or ""
    h.job_no = kv.get("job number") or ""
    h.cone_type = kv.get("conenumber") or ""
    h.location = kv.get("location") or ""
    h.test_id = kv.get("testnumber") or base_name(name)
    h.predrill = pre
    h.gl = opt_num(kv.get("ground level"))
    dm = re.search(r"(\d+)-(\d+)-(\d{4})", kv.get("date") or "")
    if dm:
        h.date = f"{dm.group(3)}-{dm.group(2).rjust(2, '0')}-{dm.group(1).rjust(2, '0')}"
    if subtraction:
        h.warning = "Subtraction cone (type S): fs conversion not verified"
    h.remarks = "Converted from GME raw data; inclination channels are not converted"
    return CPT(name, h, raw, "gme")
