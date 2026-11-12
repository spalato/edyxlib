# pyspan rewrite: use cases and plan

Draft 2026-11-12, for review (answer inline with `> SP:`). Use cases first; the build plan
at the end is only a sketch until the use cases are agreed.

## Scope

- `pyspan` holds the interactive tools, and only those (ipywidgets, ipympl). Reading,
  processing, fitting and saving stay in `edyx`.
- A tool helps the user make a **decision**: which points to reject, where t0 is,
  which spectrum to compare. It returns the decision as plain data (numbers, lists,
  boolean masks). The next step is an ordinary `edyx` call or plain numpy.
- Same principles as `edyx`: KISS, few black boxes, basic data types, the user stays in
  control of the pipeline.
- Runs in JupyterLab with `%matplotlib widget`. These dependencies are the fragile part,
  which is why they stay out of `edyx`.

## Sources

- Lab notebooks: 250709 TA (11), `edyx/scratch/` (TA, FLUPS, linear), `some_functions.py`.
- Legacy `pyspan` (`C:\work\src\pyspan`): `inspect.Linear`, plus `io`, `utils`, `itos`.
  All of its functions now exist in `edyx` (`io`, `utils`, `units`, `models`, `tana`).
  The only renamed one is `read_ta_dat`, now `edyx.io.read_dat`.
- `ta_workflow_design.md`: findings, agreed decisions.

## Use cases

Each one gives: when it happens, input, what the user does, output, the notebook cell it
replaces, and the evidence.

### UC1. Manual rejection of scan data (TA, FLUPS)

- **When**: after loading a stack of scans, before averaging.
- **Input**: `t`, `wl`, a stack (F, W, T), file names. F = 1 must work.
- **Interaction**: browse the kinetics of every file at one wavelength (wavelength
  slider), or the spectra at one delay. Select a range on the plot, then reject it
  for one file or for all files.
- **Rejection forms seen**:
  - single delay in one file (`[4, :, 221]`);
  - delay range in all files (late times, `[:, :, 253:]`);
  - whole files (`[0:2, :, :]`);
  - wavelength rows in one file (`[-1, [282, 283], :]`, a cosmic in the background).
- **Output**: the boolean mask (F, W, T) for `np.ma.masked_array`. Also the list of
  rejections as a literal, so the notebook can be re-run without clicking (UC5).
- **Replaces**: the kinetic overlay cell with its range slider (TA cell 15, FLUPS
  cell 24) and the manual masking cells that follow it.
- **Evidence**: did all the rejection work in 250709 (RMSD disabled in 9 of 11
  notebooks); same cells copied in the FLUPS notebooks.

### UC2. Comparison of datasets

- **When**: during processing (scans against each other, first against last scan for
  degradation) and after it (with or without PCF, before and after a correction,
  different samples).
- **Input**: several traces `(t, wl, s)`, or one stack. The axes may differ: a
  clipped shift shortens `t`, a crop shortens `wl`. Each dataset is plotted on its own
  axes, and the slider value is a delay or wavelength, not an index.
- **Interaction**: a slider for the delay (spectra view) or the wavelength (kinetics
  view); the curves of all datasets overlaid, with labels.
- **Output**: none. Optionally, the current delay or wavelength.
- **Replaces**: `spectra_view` and `transients_view` (copied into two FLUPS notebooks and
  `some_functions.py`, each with hard-coded limits), and the comparison half of the
  UC1 cell.
- **Evidence**: three copies; one known bug (`IndexError` with 2 files).
- **Note**: UC1 and UC2 share a view (an overlay with a slider). UC1 adds the
  selection and the reject buttons.

### UC3. t0 picking

- **When**: once per setup or day, on a reference measurement (TA: solvent or sample
  with a sharp rise; FLUPS: dye). The curve is then reused for other scans.
- **Input**: `t`, `wl`, one trace (usually averaged and pre-t0 subtracted). Optionally,
  existing points to review: the clicked points of an earlier session, or FLUPS dye
  fits with errors.
- **Interaction**: step through wavelengths (every n-th), click the t0 on the kinetic
  trace, see the points on the map, delete or move a point. Optionally see a fitted
  curve and the shifted map.
- **Output**: points `(wl, t0)` as an array, plus the fitted curve if a fit is shown.
- **Replaces**: TA cells 27-29 (the largest cell in the notebook, globals and callbacks).
- **Evidence**: in every TA template; notes to self ask for fit and shift buttons, and
  a two-panel display.
- **Acceptance case**: `s2027_t0corr.npz` holds the 53 clicked points (`t0_meas`),
  the fitted coefficients and the sampled curve.

### UC4. Linear spectra: inspection and averaging

- **When**: every linear absorption measurement (before and after TA, ITOS).
- **Input**: `wl`, OD (L files, M wavelengths, N repetitions), file names.
- **Interaction**: per file, browse the repetitions, see the RMSD of each repetition
  against the median, set the rejection threshold.
- **Output**: mask and thresholds; mean spectra per file.
- **Replaces**: `pyspan.inspect.Linear` (works as intended, no workarounds).
- **Evidence** (SP, 2026-11-12): the linear notebook never needs much change; this is
  the one case where the RMSD threshold works well.
- **Plan**: port it with as little change as possible, so the notebook keeps working.
  Low priority. The split into logic and widget (agreed earlier) happens only as far
  as testing needs it.

### UC5. Re-running a finished notebook without clicking

- **When**: reprocessing, checking, or reusing a notebook as the template for the next
  dataset.
- **Need**: decisions live in the notebook (no sidecar files, agreed). Each tool
  takes its decisions as input and returns them as a literal the user can paste into
  the cell, e.g. `rejections = [(4, None, (221, 222)), ...]` or the t0 points array.
- **Consequence**: a tool opened with existing decisions shows them and lets the user
  edit them. The data step that uses them works without the widget.

### UC6. Opening an old notebook in the new environment

- **When**: once the new `pyspan` replaces the legacy one in `edyxenv`.
- **Problem**: old notebooks import `pyspan.io.read_ta_dat`, `pyspan.utils.*`,
  `pyspan.itos` and `from pyspan import Linear`. A new package with the same name breaks
  these imports.
- **Options**: thin shims (`pyspan.io` re-exporting `edyx.io`, with `read_ta_dat` as an
  alias) for a transition period, or a clean break with a note in the README. The user
  decides (open question 3).

## Requirements across use cases

- One file (F = 1) and one repetition work without special cases.
- Masked arrays in, masks kept, masks out.
- Outputs are basic types (arrays, lists, dicts of numbers). No custom objects needed
  downstream.
- Decision logic is in plain functions or small classes, tested without a browser.
  Widgets only wire them to the display.
- Axes are passed explicitly (`t`, `wl`), in the `edyx` order: axes first, then data,
  then options.
- No hard-coded limits: defaults from the data, overridable.

## Not use cases (no interactive tool)

- ITOS wavelength calibration: essentially fully automatic (SP, 2026-11-12): peak
  finding plus a linear fit, static (`edyx` functions plus a plot). Only change:
  apply the calibration at load instead of rewriting data files.
- Despike check: static, `plot_maps` covers it.
- Scan subsets (direction, early/late): plain code (`runs = [...]`, index masks).
- Downstream figures (transient spectra, kinetics, band integrals): static matplotlib.
  The 250709 analysis notebooks use `%matplotlib widget` only for zoom.

## Open questions

1. **t0 fit in the picker**: does the picker show a fitted curve and the shifted map? The
   model is a scientific choice and `T0Curve` is deferred. Options:
   - (a) points only; the fit is a separate `edyx` call;
   - (b) the user passes a fit function (`fit(wl, t0) -> callable`), and the picker
     shows the curve and the shifted map.
2. ~~**RMSD threshold view**: keep it for TA and FLUPS stacks, or only for linear
   spectra?~~ Answered (2026-11-12): linear spectra only (UC4), where it works. TA and
   FLUPS rely on manual rejection (UC1).
3. **Old notebooks**: shims for a transition, or a clean break?
4. **Rejection literal**: index-based (file, wl index range, t index range), or
   value-based (file, wl range in nm, t range in ps)? Values survive a crop or a
   different grid; indices are exact.
5. **Display backend**: ipywidgets with ipympl as now, or the native matplotlib
   window for some tools (cheap and robust, noted in the TA design doc)?

## Plan sketch (after the use cases are agreed)

1. Package skeleton: `pyspan/` with its own `pyproject.toml` and `uv.lock`,
   depending on `edyx>=0.2`, `ipywidgets`, `ipympl`.
2. Shared overlay view with a slider (UC2), then selection and rejection on top of it
   (UC1, UC5).
3. t0 picker (UC3), checked against the 250709 clicked points.
4. `Linear` port with minimal change (UC4).
5. Shims or README note (UC6).
6. Example notebooks using the `edyx/examples/data` files.
