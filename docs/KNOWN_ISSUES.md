# Known issues and differences from the HTML version

## Fixed in both versions

1. **Semicolon CSV with decimal commas was read wrongly.** In a file like `1,25;3,40;…` there are more commas than
   semicolons, so the separator was detected as `,` and qc came out as 0 – without an error. Now `;` is used when
   (nearly, ≥ 90 %) every line of the first 30 has the same non-zero number of semicolons
   (`readers/tabular.py → parse_delimited`, and `parseDelimited` in the HTML).
2. **Spike filter disturbed the sample next to a spike.** Each sample was judged against its neighbours *before* the
   pass, so the reading beside a large spike looked like a negative spike and was replaced by roughly half the spike
   value. Now a detected peak is only replaced if neither neighbour is a bigger detected peak in the same pass; the
   neighbour is judged again in the next pass against the filtered values (`processing.spike_filter` and
   `spikeFilter`). With the default of 1 pass, results of files with spikes change slightly against older versions.

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
