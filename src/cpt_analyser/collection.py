"""Open many files at once – CPTs, dissipation tests and settings files."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ._js import base_name
from .models import CPT, Dissipation
from .processing import process_cpt, process_diss
from .readers.gef import parse_gef
from .readers.gme import gme_pair_key, is_gme, parse_gme
from .readers.tabular import parse_delimited, parse_xlsx
from .settings import Settings

SUPPORTED = re.compile(r"\.(gef|csv|txt|xlsx|xls|json)$", re.I)


def is_supported(name: str) -> bool:
    return bool(SUPPORTED.search(name)) or is_gme(name)


def read_text(p: Path) -> tuple[str, str]:
    """(text, encoding): UTF-8, or Latin-1 for older files with e.g. 'mm²' in one byte."""
    b = p.read_bytes()
    try:
        return b.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return b.decode("latin-1"), "latin-1"


def _read_text(p: Path) -> str:
    return read_text(p)[0]


def _natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


@dataclass
class Collection:
    """A set of opened soundings, like the file list of the HTML tool."""
    settings: Settings = field(default_factory=Settings)
    cpts: list = field(default_factory=list)          # CPT objects
    dissipations: list = field(default_factory=list)  # Dissipation objects
    errors: list = field(default_factory=list)        # 'file: message'

    def __iter__(self):
        return iter(self.cpts)

    def __len__(self):
        return len(self.cpts)

    def __getitem__(self, key):
        """By index or by test id / file base name."""
        if isinstance(key, int):
            return self.cpts[key]
        for c in self.cpts + self.dissipations:
            if c.test_id == key or base_name(c.file) == key:
                return c
        raise KeyError(key)

    def all(self):
        return self.cpts + self.dissipations

    def process(self):
        """Recalculate everything (call after changing settings or raw values)."""
        for c in self.cpts:
            process_cpt(c, self.settings)
        for d in self.dissipations:
            process_diss(d, self.settings, self.cpts)
        return self

    def dissipations_for(self, c: CPT) -> list[Dissipation]:
        b = base_name(c.file).lower()
        return [d for d in self.dissipations if d.parent and base_name(d.parent).lower() == b and d.depth is not None]

    def add(self, obj):
        (self.dissipations if obj.kind == "diss" else self.cpts).append(obj)

    def open(self, *paths) -> Collection:
        """Open files and folders (folders are searched recursively)."""
        files: list[Path] = []
        for p in paths:
            p = Path(p)
            if p.is_dir():
                files += sorted(q for q in p.rglob("*") if q.is_file() and is_supported(q.name))
            elif p.exists():
                files.append(p)
            else:
                self.errors.append(f"{p}: file not found")
        files = [f for f in files if is_supported(f.name)]
        settings_files = []
        # pair GME header (.0xx) and data (.1xx) files
        gme: dict = {}
        for f in files:
            if is_gme(f.name):
                key, which = gme_pair_key(f.name)
                gme.setdefault((str(f.parent), key), {})[which] = f
        for g in gme.values():
            try:
                if "0" not in g or "1" not in g:
                    raise ValueError("needs both the .0 header and .1 data file")
                self.add(parse_gme(_read_text(g["0"]), _read_text(g["1"]), g["1"].name))
            except Exception as e:  # noqa: BLE001 – report and carry on with the other files
                self.errors.append(f"{(g.get('1') or g.get('0')).name}: {e}")
        for f in files:
            if is_gme(f.name):
                continue
            if f.suffix.lower() == ".json":
                settings_files.append(f)
                continue
            try:
                if re.search(r"\.xlsx?$", f.name, re.I):
                    obj = parse_xlsx(f, f.name)
                else:
                    text, enc = read_text(f)
                    is_gef = f.suffix.lower() == ".gef" or re.match(r"^\s*#GEFID", text, re.I)
                    obj = parse_gef(text, f.name) if is_gef else parse_delimited(text, f.name)
                    obj.encoding = enc
                self.add(obj)
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"{f.name}: {e}")
        # <name>.cptset.json attaches to the CPT with the same base name, otherwise it becomes the global settings
        for f in settings_files:
            try:
                st = Settings.load(f)
                b = re.sub(r"\.cptset\.json$|\.json$", "", f.name, flags=re.I).lower()
                target = next((c for c in self.cpts if base_name(c.file).lower() == b), None)
                if target:
                    target.settings = st
                else:
                    self.settings = st
            except Exception as e:  # noqa: BLE001
                self.errors.append(f"{f.name}: {e}")
        self.cpts.sort(key=lambda c: _natural(c.test_id))
        self.dissipations.sort(key=lambda c: _natural(c.test_id))
        return self.process()


def load(*paths, settings: Settings | str | Path | None = None) -> Collection:
    """Open GEF, GME, CSV, Excel and settings files (or whole folders) and process them.

    >>> import cpt_analyser as ca
    >>> col = ca.load("data/")            # every supported file in the folder
    >>> cpt = col[0]                      # or col["CPT-01"]
    >>> cpt.data["Ic"], cpt.layers
    """
    if isinstance(settings, (str, Path)):
        settings = Settings.load(settings)
    return Collection(settings=settings or Settings()).open(*paths)


def read(path, settings: Settings | None = None):
    """Open and process a single file; returns the CPT or Dissipation."""
    col = load(path, settings=settings)
    if col.errors:
        raise ValueError("; ".join(col.errors))
    items = col.all()
    if not items:
        raise ValueError(f"{path}: nothing found")
    return items[0]
