# pyspan rewrite: use cases and plan

Status: implemented on branch `feature-pyspan` (2026-11-12), steps 1-8 of the plan
below. Changes made during implementation are listed under "Implemented".

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
- **RMSD threshold** (decided 2026-11-12: available everywhere): an optional panel
  shows the RMSD of each spectrum against the median of the files, with a threshold.
  Rejections above the threshold join the manual ones.
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
  trace, see the points on the map, delete or move a point.
- **Output**: points only (decided 2026-11-12), as an array of `(wl, t0)` rows. The fit
  is a separate step in the notebook, with the model the user chooses.
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
- **Interim method** (SP, 2026-11-12), until a sidecar file is designed: each tool
  prints its final decisions as a plain Python literal, ready to paste:
  ```python
  rejections = [(4, None, (221, 222)), (None, None, (253, None))]
  ```
  - Index-based (decided 2026-11-12). Each rejection is `(file, wl, t)`; each entry is
    `None` (all), an index, or a `(start, stop)` range, stop excluded, as in a Python
    slice. The examples above: delay 221 of file 4; delays from 253 on, in all files.
  - Printed once, on a "Done" button (or when the tool is closed), not on every click.
  - Each edit is also logged (`logging`, INFO level), so a trail exists in the cell
    output when the user wants it.
  - The printed output is saved with the notebook. Pasting it into the next cell makes
    the notebook re-run without clicking.
  - A sidecar file can later read and write the same literals.

### UC6. Opening an old notebook in the new environment

- **When**: once the new `pyspan` replaces the legacy one in `edyxenv`.
- **Problem**: old notebooks import `pyspan.io.read_ta_dat`, `pyspan.utils.*`,
  `pyspan.itos` and `from pyspan import Linear`. A new package with the same name breaks
  these imports.
- **Decided** (2026-11-12): legacy compatibility imports. `pyspan.io`, `pyspan.utils`
  and `pyspan.itos` re-export the `edyx` functions under their old names
  (`read_ta_dat` is identical to `edyx.io.read_dat`), with a `FutureWarning` naming
  the new import. `from pyspan import Linear` keeps working.

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

## Decisions (2026-11-12)

1. t0 picker: points only. The fit is a separate notebook step.
2. RMSD threshold view: available for all (TA, FLUPS stacks and linear spectra).
3. Old notebooks: legacy compatibility imports (UC6).
4. Rejection literal: index-based (UC5).
5. Display: ipywidgets with ipympl (`%matplotlib widget`).

## Plan

### Package

```
pyspan/
├── pyproject.toml      # uv_build, Python >= 3.11, version 0.3.0 (legacy was 0.2)
├── uv.lock
├── src/pyspan/
│   ├── __init__.py     # Linear, ScanInspector, Overlay, T0Picker
│   ├── decisions.py    # rejection literal -> mask, RMSD, printing of literals
│   ├── overlay.py      # UC2
│   ├── inspector.py    # UC1 (+ RMSD panel)
│   ├── t0.py           # UC3
│   ├── linear.py       # UC4, ported Linear
│   ├── io.py, utils.py, itos.py   # UC6, legacy re-exports only
├── tests/
└── examples/
```

- Dependencies: `edyx>=0.2`, `ipywidgets>=8`, `ipympl`, `matplotlib`, `numpy`,
  `attrs` (kept for the `Linear` port). Dev: `pytest`. During development, `edyx` is
  taken from `../edyx` (editable path source).
- The legacy env pinned `ipywidgets<8`. The new one uses current JupyterLab 4,
  ipywidgets 8 and ipympl; to be checked on a lab machine early (step 1).

### Shape of each tool

- Logic in plain functions (`decisions.py`): no widgets, unit tested.
- One small class per tool. It holds the data and the decisions, has one method per
  user action (`reject(...)`, `add_point(...)`, `done()`), and builds its widgets in
  a `show()` method. Tests call the action methods with the Agg backend; only
  `show()` needs a browser.
- Each tool accepts its earlier decisions (`rejections=`, `points=`) and prints them
  as a literal on "Done". Edits are logged at INFO level.

### `decisions.py`

- `rejection_mask(shape, rejections)`: boolean (F, W, T) mask from the literal.
- `rmsd_vs_median(data, axis)`: RMSD of each spectrum against the median along
  `axis` (files for TA and FLUPS, repetitions for linear spectra).
- `above_threshold(rmsd, threshold)`: rejections for the spectra above a threshold.
- `format_literal(name, value)`: `name = [...]` text, arrays included, ready to paste.

### Steps

Each step ends with tests passing and a commit. Executors write code; I review.

1. **Skeleton and legacy imports** (UC6). `pyproject.toml`, `uv.lock`, the
   re-export modules with a `FutureWarning`, `Linear` moved over unchanged. Test: the
   imports used by the old notebooks work (`read_ta_dat`, `pack_trace`, `between`,
   `nm2ev`, `load_itos_spectrum`, `Linear`). Check `%matplotlib widget` in JupyterLab.
2. **`decisions.py`** with tests, including the four rejection forms from 250709.
3. **`Overlay`** (UC2): datasets with their own axes, spectra or kinetics mode, slider
   by value. Replaces `spectra_view` and `transients_view`.
4. **`ScanInspector`** (UC1): `Overlay` on one stack, a delay span selector, buttons
   "reject in this file", "reject in all files", "reject file", "reject wl rows",
   an undo, the optional RMSD panel, "Done".
5. **`T0Picker`** (UC3): wavelength stepping, click to add, delete, existing points
   shown, "Done". Acceptance: opened with the 53 points of `s2027_t0corr.npz`, "Done"
   returns them unchanged, and a cubic fit in eV in the notebook gives the stored
   `pol_coeff`.
6. **`Linear`** (UC4): use `decisions.rmsd_vs_median`, add printing of thresholds on
   "Done". The linear notebook stays unchanged.
7. **Examples**: TA rejection and t0 review on the `edyx/examples/data` files (s40,
   s44, stored t0 points), and the comparison viewer on the FLUPS example.
8. **Docs**: README (install into `edyxenv`, `%matplotlib widget`), and the TA
   design doc updated.

### Implemented (2026-11-12)

Differences from the plan, from review and user testing:
- `Overlay`: the view (spectra or kinetics) is set at construction, no toggle. An
  "Autoscale" button fits the y axis to the curves shown (user request).
- `ScanInspector`: kinetics view only. "Reject in all files" removed (user request);
  `(None, ...)` literals are still accepted in `rejections=`. Reject without a
  selection does nothing (warning); the selection is cleared after each reject.
  Default threshold with `rmsd`: `max(rmsd)`, which rejects nothing.
- `T0Picker`: points kept in click order (the stored 53 points come back unchanged).
  One point per wavelength row; clicking again moves it. Clicks are ignored in
  zoom/pan mode.
- `Linear`: `threshold=` input (also through `from_files`). Decided by SP: the
  default threshold is applied at once to all files (legacy: only to files visited
  or edited, so re-running from the "Done" literal could differ). A large value
  rejects nothing. This changes `mean_spectra` of existing notebooks that relied on
  the default.
- `T0Picker`: `tlim=` delay range (both panels, kinetic y scale fitted within it).
- File order: notebooks use `sorted(glob(...))`, so file-index literals keep their
  meaning (SP).
- Checked in JupyterLab and VS Code by SP: widgets, span selection, clicks.

### Not in this round

- Sidecar files (decisions are printed literals for now).
- Assisted t0 picking. (t0 fits: in the notebook, no `T0Curve`; see
  `calibration_design.md`.)
- Outlier tests for 1 or 2 files.
