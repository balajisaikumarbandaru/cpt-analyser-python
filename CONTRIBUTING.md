# Contributing

Changes are welcome – a new correlation, a file format, a plot option, a bug fix.

## Set up

```bash
git clone https://github.com/balajisaikumarbandaru/cpt-analyser-python.git
cd cpt-analyser-python
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"
pytest
```

## Workflow

1. Create a branch: `git checkout -b add-robertson-2016`
2. Make the change. The [code map in the README](README.md#code-map--where-to-change-things) shows where things live.
3. Add or update a test in `tests/`.
4. `pytest` and `ruff check .` must pass (GitHub runs both on every pull request).
5. Open a pull request and describe what changed and why – for a calculation, give the reference (paper, standard).

## Rules

- **No real site data in the repository.** Tests and examples use the synthetic files from `tools/make_demo_data.py`.
  `/data/` is git-ignored – keep your own files there.
- **Calculations must stay in step with the HTML version.** `tests/test_parity_with_html.py` compares every value with
  results from the HTML tool's JavaScript. If you change a calculation on purpose:
  1. make the same change in `CPT_Analyser.html` ([HTML repository](https://github.com/balajisaikumarbandaru/cpt-analyser)),
  2. regenerate the expected files: `pip install -e ".[parity]"` then
     `python tools/html_reference.py path/to/CPT_Analyser.html --update-fixtures`,
  3. mention both changes in the pull request.
  A new parameter that only exists in Python does not break the parity test – it only checks keys the HTML has.
- Keep the settings keys compatible with `.cptset.json` files of the HTML tool.
- Units inside the code: m, MPa (qc, fs, u), kPa (stresses), degrees, seconds.
