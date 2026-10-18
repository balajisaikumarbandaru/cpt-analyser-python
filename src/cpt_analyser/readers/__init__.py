"""File readers. Use :func:`cpt_analyser.load` to open files and folders in one go."""
from .gef import parse_gef
from .gme import is_gme, parse_gme
from .tabular import parse_delimited, parse_xlsx, rows_to_cpt

__all__ = ["parse_gef", "parse_gme", "is_gme", "parse_delimited", "parse_xlsx", "rows_to_cpt"]
