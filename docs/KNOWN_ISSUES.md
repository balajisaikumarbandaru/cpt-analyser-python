# Known issues and differences from the HTML version

## Shared with the HTML version (kept identical on purpose, so both tools agree)

1. **Semicolon CSV with decimal commas is read wrongly.** In a file like `1,25;3,40;…` there are more commas than
   semicolons, so the separator is detected as `,` and qc comes out as 0 – without an error. Workaround: save the CSV
   with a full stop as decimal separator, or use Excel. Fix: detect `;` first when every line has the same number of
   semicolons (`readers/tabular.py → parse_delimited`, and `parseDelimited` in the HTML).
2. **Spike filter can disturb the sample next to a spike.** Each sample is judged against its neighbours *before* the
   pass, so the reading beside a large spike can look like a negative spike and be replaced by roughly half the spike
   value. Fix: judge neighbours against the already-filtered values, or exclude samples next to a detected spike in the
   same pass (`processing.spike_filter` and `spikeFilter`).

## Fixed in Python only

3. **Dissipation marker label.** The HTML labels the marker on the pore-pressure graph with the text after the *first*
   "D" of the test id, so a test called `DEMO-01 D1 @5 m` is shown as `DEMO-01`. Python uses the `D…` before the `@`.
4. **GEF files that are not UTF-8.** Older files can hold characters such as `mm²` as a single Latin-1 byte. The
   browser reads files as UTF-8 and writes such characters back as `�` when a GEF is saved. Python reads these files
   as Latin-1 and writes them back byte-for-byte (`save_gef`).

## Not ported from the HTML version

- Interactive plot (hover read-out, drag to zoom) – the Streamlit app shows static images
- DXF and JPG plot export (PNG, SVG and PDF are available)
- New CPT dialog, projects folder management, header copy to all CPTs
- Dutch / German / custom translations (English only)

## Not included in either version

- Soil classification from the Robertson Qt–Bq chart
- GME `.Dxx` dissipation files
- Inclination from GME raw data (calibration differs per cone)
