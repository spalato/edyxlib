# TA and FLUPS workflow redesign: discussion notes

Status: first round implemented on branch `feature-processing_reorg` (2026-11-12):
io layout, `collect-asc`, shared trace functions, `plot_maps`. Started 2026-10-29.
Updated 2026-11-12 with the notebooks in `edyx/scratch/` (TA, FLUPS, linear), then
with SP's answers.

## Guiding principles (2026-11-12)

- The design's job is code consistency, streamlining and usability.
- Choices with scientific impact belong to the users and are evaluated carefully
  later: despike method and threshold, outlier test, t0 model and order, Jacobians,
  excluded ranges, calibration reuse. They are explicit parameters, never silent
  defaults.
- Weigh every new function: its benefit against its cost in maintenance and
  learning. Small helpers that encode a convention are good, for example
  `def avg_spectra(data): return np.mean(data, axis=TIME_AXIS)`.
- Conventions:
  - TA layout (wl x t, ascending axes);
  - named axis constants (`FILE_AXIS`, `WL_AXIS`, `TIME_AXIS`);
  - one argument order (see "Code consistency").
- Clear names: a name says what the function does, in the lab's own terms.
- Dependency isolation:
  - all interactive widgets (slicers included) go in `pyspan`, a sibling of `edyx`;
  - `edyx/plot` is for matplotlib-only, non-interactive plots.

## Context

- `utils.py`, `io.py`: simple numerical functions. Fine as is, out of scope.
- Interactive workflows:
  - Linear spectra: `inspect.Linear` widget (`demo/linear/`).
  - TA: semi-interactive notebook, copied per dataset
    (`demo/ta_v0/ta_dirty_notebook.ipynb`; real use in
    `C:\work\data\ta\2025\250709\ta_s*.ipynb`, conda env `main`).
- TA steps: load repeated scans (wl x t), background subtraction, inspect and
  compare scans (bad pulses, degradation), reject, average, pick t0 by clicking,
  fit a polynomial in eV, shift, save. The t0 curve is picked about once a day
  and reused.
- FLUPS: same kind of semi-interactive notebooks (`edyx/scratch/250827_FLUPS_*`,
  `250825_FLUPS_average-dyes`). Steps: load repeated scans (counts, t x pixel),
  despike, inspect and reject, average, t0 correction (curve fitted on a reference
  dye), photometric correction (PCF), convert to fluorescence wavelength, crop, save.
- Calibrations are needed on a daily basis. How far they can be reused is a
  scientific constraint, decided by the users.
- Step order is well controlled in both experiments.
- The scratch notebooks import from the old packages (`pyspan.io`, `pyspan.utils`,
  `flups.io`, `flups.analysis`). Most of these functions now live in `edyx.io`,
  `edyx.units`, `edyx.utils`, `edyx.models` and `edyx.fana`.

## Findings from 250709 (11 notebooks)

The workarounds were needed because of the sample (fast degradation), not user error.

- RMSD vs median rejection was disabled (`threshold = np.inf`) in 9 of 11
  notebooks. With 1 or 2 files it can't discriminate (median of 2 = mean).
  Manual rejection did all the work.
- Manual rejections took several forms: single delay (`[4,:,221]`), late times
  for all files (`[:,:,253:]`), whole files (`[0:2,:,:]`, which depends on glob order).
- Scan subsets by direction: `glob(...)[::2]` / `[1::2]` (depends on glob order).
- One t0 curve (from the 20 fs scan, -0.8 to 6.2 ps) was reused for the
  200 fs and 8 ps scans. This is correct: t0 is a property of the experimental
  setup, independent of step size, so its handling does not change. The
  polynomial spans about 2 ps (+0.9 ps at 690 nm, -1.2 ps at 276 nm). The
  consequences belong in the shift function (edge policy, interpolation), not in
  the t0 curve:
  - It runs past the start of the 20 fs data, so clipping is driven by the worst
    wavelength. That needed `npad = 50` zero padding.
  - With 8 ps steps, a sub-step shift by linear interpolation mostly smears the rise.
- The wl grid was identical (512 points) for all scans. Saving t0 as sampled
  values (`t0_corr`) instead of polynomial coefficients is still fragile when
  grids differ.
- Shape workarounds for N = 1 or 2 files (`np.atleast_2d(axes)`,
  `np.atleast_2d(rmsd > threshold)`). Colour limits are tweaked in every notebook;
  two notebooks moved to percentile limits.
- The README in the data folder already works as a manifest (output, files,
  exclusions, notes).

## Findings from `edyx/scratch/` (2026-11-12)

Sources:
- TA: `261102_ta_dirty_notebook` (a newer variant of the template).
- FLUPS: `250827_FLUPS_corrections_main` (main pipeline), `250827_FLUPS_t0-correction`
  (t0 curve from a dye), `250827_FLUPs_determine-pcf` (photometric correction),
  `250825_FLUPS_average-dyes` (dye spectra for the PCF).
- Linear: `261102_linear_template` (uses `Linear`), `ITOS_peak` (wavelength calibration).
- `some_functions.py`: viewers, band integral, anisotropy.
- Only code was read, not plots. Some cell outputs are stale (they don't match the
  code above them). File name dates don't match the dates used inside the notebooks.

### Shared by TA and FLUPS

- Same skeleton, copied cell for cell: load the stack, assert identical axes,
  per-file maps, RMSD vs median, per-wl transient overlay with a range slider,
  manual slice rejection on a masked array, `np.ma.mean`, shift per wl with
  `shift_kin`, then `pack_trace` + `np.savetxt`. This confirms a shared core, with
  technique-specific steps around it.
- RMSD rejection is not useful in FLUPS either ("this does not seem necessary ever
  in flups"). The author suggests a trimmed average instead: median and std over
  repetitions, reject above a threshold.
- New rejection form: wavelength rows in a single file (`sig_masked[-1,[282,283],:]`),
  because the background likely had a cosmic there. Rejection must cover files,
  delays and wavelengths, alone or combined.
- Scan subsets by acquisition order again: early/late averages with
  `np.arange(n) % 4 < 2` (FLUPS). Acquisition index should be explicit, not taken
  from list order.
- Masks are lost silently: the masked average goes through `np.interp` before the
  shift, which uses the data under the mask (checked). This matters wherever a point
  is masked in every file. Treated as a bug (see "Agreed").
- t0 curve:
  - Point source differs. TA clicks points. FLUPS fits `conv_exp` + constant on
    2 nm bands of a reference dye, in two passes (tau free, then tau fixed to the
    weighted mean), which gives t0 *with errors*. Both then do "points to curve".
  - FLUPS fits a polynomial in eV with weights 1/t0_err. Comparing orders 1-4 by
    reduced chi² was a trial: the model is the user's choice. Newer versions will
    try `a + b/wl**2 + c/wl**4`, so the model is not always a polynomial in eV.
  - FLUPS also fits the cross-correlation (Gaussian at 266 nm) to get the IRF width.
  - Coefficient conventions differ. TA saves `Polynomial(...).convert().coef`
    (low order first) in `.npz`, together with the sampled `t0_corr`, and reuses
    the sampled values. FLUPS saves `np.polyfit` output (high order first) to `.txt`
    and evaluates it on the current grid with `np.poly1d(p)(nm2eV(wl))`. The FLUPS
    notebook ends with "save parameters instead, look at TA".
  - Fitted points get a manual adjustment
    (`timings.loc[..., "t0"] -= 0.02`, "compensate for slight overlap").
- Edge policy in use: FLUPS disables clipping (`t_c = t`, NaN edges kept), then
  crops a time window (-1 to 5.5 ps) just before saving. Confirms `edges="nan"` and
  adds an explicit crop step.
- N = 1 shape problems in FLUPS too (`np.atleast_2d(axes)`,
  `'Axes' object is not iterable`).
- Colour limits are set per notebook in both, and FLUPS mixes fixed limits and
  percentiles. This is fine: they depend on the dataset.
- `spectra_view` (delay slider, overlay of 2 datasets, 3 in `some_functions.py`) is
  copied into two FLUPS notebooks and `some_functions.py`, each with a different
  hard-coded `xlim`. It compares spectra or kinetics of processed results
  (with/without PCF, first/last scan) and is a useful interactive tool.
- Helpers redefined locally although they are in the library: `between`, `nm2eV`,
  `shift_kin`. TA reimplements `edyx.fana.shift_trace`.

### TA only (261102)

- Output name concatenated from loose variables (`date`, `sample`, `solvent`,
  `step`, `rel_pol`, `pump_power`, `pump_wl`), with `out_root` sliced from file names
  (`fnames[0][1:-4]`). Fine for now: users already document well (see "Later").
- Wavelength crop (`cut_wl`) right after loading.
- Two background subtractions, on purpose: one per file before t0 (`bksub`, used for
  RMSD and plots), then the averaged negative-delay spectrum (`negspec`) after
  averaging. The second one enables the later steps. The average is taken over
  `dod_masked`, built from raw `dod`.
- Single-scan output: the shift code is copied a second time to process `bksub[0]`
  alone. The functions must accept one scan without a stack.
- Extra outputs for degradation checks: negative-delay spectra of the first and last
  scans, and `negspec`.
- The t0 curve is loaded from another dataset (`250307_s1213_thf_t0corr.npz`) and
  applied as the sampled `t0_corr[i, 1]`, by index. If that file was made on a
  different grid (for example before `cut_wl`), each wavelength silently gets
  another wavelength's t0.
- Notes to self in the notebook: fit and shift buttons, a t0 class, a two-panel
  display (original + polynomial, shifted). This matches the planned t0 picker.
- Polarisation: `rel_pol` (`'m'`, presumably magic angle) in the output name, and
  anisotropy functions in `some_functions.py`.

### FLUPS only

- Input layout is transposed: `load_txt` gives t x wl (TA `.dat` is wl x t),
  sometimes with descending t. Both stack-loading notebooks reverse and transpose by
  hand ("this should not be necessary in the future"). Files are named `run##.txt`
  or `run##.dat`. Final outputs are written with `pack_trace` (TA layout),
  intermediate ones with `save_txt` (t x wl) or `np.savetxt(np.column_stack(...))`.
- Signal is counts, positive: mostly sequential colormaps (`Blues`, `plasma`); some
  later plots use `coolwarm` / `RdBu_r` at ±10.
- Spectral axis can be pixels: `if np.allclose(wl, np.arange(wl.size)+1)` triggers a
  linear pixel-to-nm calibration written in the notebook. This is a holdover from
  the previous detector: the current one reports wavelength, so no pixel
  calibration is needed.
- Despiking (cosmic rays) per file, before averaging:
  `despike_median(sig, (15, 5), threshold)`, with a raw/filtered/removed plot.
  The notebook's benchmark notes: `despike_median` (absolute threshold) eats the
  cross-correlation and misses many cosmics; `despike_median_p` (relative to
  p95-p5) works but takes about 40 s per file; proposed fix: the fast filter with a
  threshold from the noise of a background region. Despiking *replaces* values; it
  does not mask them.
- Excluded pixel ranges are not documented: the RMSD excludes pump scatter and
  other ranges, and a commented-out despike threshold excludes pixels 614-680
  ("Why excluding ...? Guess pump?").
- Background subtraction before t0 is commented out (only needed when a cosmic
  falls before t0).
- Photometric correction function (PCF): a multiplicative spectral calibration made
  from reference measurements, reused within limits set by the users.
  - `average-dyes` averages scans and then delays into one spectrum per dye
    (PBBO, C6H, C153).
  - `determine-pcf` converts reference spectra (csv files) to the upconverted axis
    (`wl_f = 1/(1/wl - 1/1340)`, Jacobian `wl_f**2/wl_u**2`), takes the ratio
    reference/measured inside per-dye validity windows, stitches the curves with
    fitted scale factors (pairwise RMSD, Nelder-Mead, PBBO fixed), and smooths
    (spline + Savitzky-Golay; a degree-7 polynomial is also tried). Saved as `.npz`
    (`wl`, `pcf`), NaN outside the valid range.
  - Applied in the main notebook with `np.interp` onto the data grid. Unlike the t0
    curve it is a sampled curve: evaluation needs interpolation and an out-of-range
    policy (`np.interp` holds the end values).
  - Notebook comments: the inner-filter effect makes the red edge more reliable;
    C6H showed reabsorption; dye references should be measured on the lab
    fluorimeter. `edyx.fana.ref_spec_wl` (lognormal references, Gerecke 2016)
    exists but isn't used.
- Fluorescence wavelength axis: `wl_f = 1/(1/wl - 1/1340)`, gate wavelength
  hard-coded in three places. Outputs are saved on `wl_f`. The gate wavelength has
  never changed, so it can be a parameter with default 1340 nm.

### Linear and wavelength calibration

- `261102_linear_template` uses `Linear` as intended (`from_files`, `spectra_dict`,
  one figure and one file per input). No workarounds.
- `ITOS_peak`: peaks on the measured and reference ITOS spectra
  (`edyx.tana.load_itos_spectrum`), paired by order, linear fit, saved to
  `wl_corr.txt`. Then the `*_lin_*dat` data files are **overwritten in place** with
  the corrected axis. Data files should stay immutable: apply calibrations at load.

### Downstream analysis (`some_functions.py`)

- `band_integral(deltaA, wl, wl_lim, band_average=False)` is a fork of
  `edyx.tana.band_integral` / `band_average`: different argument order, trapezoid
  instead of Simpson, and NaN handling (all-NaN delays stay NaN, other NaN count as 0).
- Anisotropy: `anis`, `magic`, `anis2theta`, `theta2anis`, `PAS`. Trivial; move to
  `edyx.tana`.

### Notebook defects

Evidence for "copy calls, not implementations":
- `wl_u = 0.171025+249,59` is a tuple, not a calibration (only reached for pixel axes).
- `timings["sample"] == "eun03.dat"`: typo, so the manual t0 adjustment is a no-op.
- Degradation output: header says `scan1\scan8` but saves `dod[0]` and `dod[1]`.
- `spectra_view(..., dat2=sig[3])` with 2 files: `IndexError`.
- FLUPS main: `NameError` on `wl_u`, unterminated `'''` in the crop-and-save cells.

## Code consistency (2026-11-12, from `edyx/io.py`)

- All loaders return `(t, wl, s)` in that order, but the orientation of `s` differs:
  - wl x t (TA standard): `read_dat`, `unpack_trace`;
  - t x wl: `load_txt`, `load_npz`, `load_asc_series`.
- So `collect-asc` (`scripts/collect_asc.py`, via `save_txt`) writes t x wl. It is
  the first step of FLUPS acquisition, so "TA layout everywhere" starts there.
  *(Done 2026-11-12: all readers return wl x t; `collect-asc` writes `.dat`.)*
- Argument order is mixed: `pack_trace(t, wl, s)`, `save_txt(fname, t, wl, s)`,
  `shift_trace(t, z, t0)`, `tana.band_integral(wl, da, bounds)`,
  `spectra_view(wl, t, dat)`. Proposed convention: axes in `(t, wl)` order, then
  data, then options. File name first for writers.
- `load_asc_series`: the docstring says delays are in fs (the notebooks use ps), and
  `step="filename"` indexes `fnames[0]` after `fnames = iter(fnames)`, which fails.

## Agreed so far

- Three widgets: **manual rejection**, **scan comparison** (already in the
  "Plot the kinetic transients at specific wavelength" cell, which overlays every
  file at the selected wl), **t0 picker**. Rejection and comparison could share
  one view: select a range, then press "reject". All three live in `pyspan`.
- **The user stays in control of the pipeline.** No rigid declarative recipe:
  experiments need structural variants (padding, edge policies, interpolation
  instead of masking, whole-file and time-range rejection), and a recipe
  turns into a poor configuration language that blocks the scientist.
- Library code holds the implementations. The template notebook is a short
  sequence of explicit calls. Copying calls is fine; copying implementations is not.
- **Store decisions, recompute data** (revised 2026-11-12). A stateful object
  stores *decisions* (mask, bg windows, repairs, calibrations) and recomputes derived
  data (`avg`, `shifted`) when asked. Calculations are cheap, so no cache and no
  invalidation. No overrides of derived data: a workaround is plain numpy whose
  result is passed to the next function.
- Common variants become parameters (`how="mask"|"interpolate"`,
  `edges="clip"|"zero"|"nan"`, `pad=`). One-off workarounds stay in the notebook
  as plain numpy, and move into the library when they recur.
  First round (2026-11-12): `shift_trace(edges="clip"|"nan")` only. Zero padding
  stays plain numpy (`np.nan_to_num`, `np.pad`) until it recurs.
- Provenance is a *descriptive* log (step + params, repairs, calibration files),
  written into the output header.
- No sidecar files for decisions: notebooks are self-documenting, so decisions live
  in the notebook. Exception under discussion: calibrations (see open questions).
- **Output format: ASCII `.dat` in the TA layout everywhere** (wl x t, ascending
  axes), intermediates included (2026-11-12). FLUPS t x wl files need a legacy
  reader.
- **Build order: pure functions first.** Wrap them in a stateful object later.

Added 2026-11-12:
- **One shared core**, with technique steps in `edyx.tana` and `edyx.fana`:
  - TA: pre-t0 background, scatter subtraction, clicked t0.
  - FLUPS: despiking, t0 fitted on a dye, PCF, fluorescence axis.
- **Basic data types**: built-ins and numpy arrays, or thin wrappers over them. The
  `{fname: (t, wl, s)}` dict stays (puzzling at first, convenient once understood),
  with `s` always wl x t.
- **Masks**: masked arrays during processing, NaN when saving. Functions must keep
  masks; dropping them silently (the shift via `np.interp`) is a bug.
- **Repair** is a decision kind alongside rejection (despiking; a historical version
  also repaired TA shots by interpolation). Store its parameters and the replaced
  positions, and log them in provenance.
- **Calibration objects** share one pattern: made from a reference measurement,
  saved with their source and the axis they were made on, evaluated on the current
  grid, referenced by file name in provenance. Settled 2026-11-13 in
  [calibration_design.md](calibration_design.md): one toml file per calibration
  holding a sampled curve, applied by value (`edyx.calib`).
  - t0 curve: the fit (a model the user chooses: polynomial in eV,
    `a + b/wl**2 + c/wl**4`, ...) stays in the notebook, which writes the sampled
    curve; model and coefficients are kept in the file for information. No `T0Curve`
    class.
  - PCF: a sampled curve, with an out-of-range policy.
  - Wavelength calibration: ITOS only (`tana.itos_calibration`).
  - IRF width, if it is reused.
- **New functions**, each with its benefit:
  - `crop(t, wl, s, t_lim=None, wl_lim=None)`: replaces `cut_wl` and the
    crop-before-save cells.
  - ~~`despike(...)` wrapper~~: dropped (2026-11-12). The `fana` functions are
    already one call; the replaced positions are `out != data`.
  - `pcf_correct(wl, s, pcf_wl, pcf)`: multiplies by the photometric correction
    function, interpolated onto `wl`. Replaces the interp-and-multiply cell.
  - `fluo_wl(wl_u, gate=1340)`: converts the detected (upconverted) axis to the
    fluorescence wavelength. Returns an axis, not data.
  - Convention helpers such as `avg_spectra` (mean over delays: dye spectra,
    linear), where they replace repeated `axis=` arithmetic.
- **`edyx/plot`** (planned in `layout.txt`, not yet created), matplotlib only:
  - defaults by signal kind: diverging and symmetric for ΔOD, sequential with
    percentile limits for counts. Users change limits per dataset and colormap to
    taste.
  - map grid: N maps side by side. Covers the per-file maps (TA cells 10, 11 and 19)
    and the data / filtered / difference columns of the FLUPS despike plot.
- **`pyspan`**: every interactive tool. Start with a KISS comparison slicer (spectra
  or kinetics over a stack, with the user passing the data), then `ScanInspector`
  and the t0 picker.
- **Split `Linear`** into model and view. Naming: leaning towards `TAStack`.

## Still proposed

- t0 points from either source (clicks, or dye fits with errors) go through the
  same weighted fit, with a model the user chooses and the fit statistics shown.

## Deferred: scientific choices, on the users

- Despiking: algorithm, threshold, and whether replaced values should be masked
  instead (benchmark notes above).
- Outlier rejection: trimmed average vs RMSD vs median.
- t0 model and order.
- Excluded pixel ranges and t0 bands.
- Jacobians, to document clearly. FLUPS has several:
  - `wl_u` (as detected) to `wl_f`;
  - `wl` to energy or wavenumber (sometimes);
  - FLUPS to equivalent stimulated emission, for comparison with TA.
  SP notes a factor `wl_f**2` for the FLUPS intensity conversion and another for
  spontaneous vs stimulated. Exponents to be confirmed when written up.

## Later

- Metadata structure (sample, solvent, pump, polarisation, ...) for output names and
  headers. The current workflow is fine: users already document well.
- Outlier tests that work for 1 or 2 files (neighbouring delays in the same file,
  pairwise differences between files).
- Assisted t0 picking (pre-placed points from `conv_exp` fits or steepest rise,
  then accepted or adjusted by the scientist).

## Unix-like design (latest point)

Small tools, one job each, connected by a common self-describing format.

- Pros: maximum control (a variant is another tool, a workaround is a script
  inserted in the chain); intermediate files give make/snakemake
  invalidation for free; provenance can accumulate in file headers; interactive
  steps are tools that open a native window (no ipywidgets install problems).
- Cons: intermediate files in data folders; less fluid exploration across
  steps; the interchange format becomes the critical decision (axes, file
  names, acquisition order, mask, provenance).
- Decision: Unix-like at the **function level**. A core of small pure
  functions on basic data types. Start with these only. A stateful `TAProcessing`
  object (notebook sessions) can wrap them later. CLI wrappers (batch,
  make/snakemake) are YAGNI.

## Related tools considered

- snakemake / make: right model (dependency graph, invalidation) but file- and
  batch-oriented, so a poor fit inside the interactive session. Good fit for
  reprocessing a whole day from raw files plus sidecars. Try papermill first.
- marimo: reactive cell graph handles staleness for plain variables, but doesn't
  track attribute mutation. Choose either marimo with returned values, or Jupyter
  with a stateful object, not both. Worth trying on the linear workflow first.
- pyqtgraph / Qt app: best interaction, highest maintenance cost.
- Native matplotlib window for the t0 picker: cheap and robust.
- Streamlit / Dash / Panel: poor fit for click-heavy work.

## Open questions

- `TAStack` as the name, now that FLUPS uses the same stack?

Resolved 2026-11-12:
- Shared functions (`shift_trace`, `crop`, `subtract_pre_t0`, `avg_scans`,
  `avg_spectra`) live in `edyx.tana`. `fana` imports from it (`fana` reads a toml at
  import, `tana` doesn't). Axis constants live in `edyx.io`, next to the layout.
- `collect-asc` writes `<date>_<run>.dat` in the TA layout, with a
  `# layout: wl x t` header comment. `.txt` stays the legacy t x wl format, read
  with `load_txt`.
- All readers (`read_dat`, `load_txt`, `load_npz`, `load_asc_series`) return
  `s` as wl x t with ascending t. File layouts are unchanged.
- `T0Curve` waits for the calibration storage decision. `shift_trace` only needs a
  `t0` array.

Resolved 2026-11-13 ([calibration_design.md](calibration_design.md)):
- Calibration storage: one toml file per calibration (sampled curve, axis, source,
  fit for information), applied by value with an explicit out-of-range policy. Files
  from another day are copied or named by path. The sidecar is postponed. `T0Curve`
  is dropped.

## Quick fixes, independent of the redesign

- `sorted(glob(...))` in the notebook templates (still to do).
- Done 2026-11-12:
  - `toml` added to `edyx` dependencies; `import edyx.fana` works (reference file
    added by SP).
  - `pack_trace` docstring; `load_txt` sorts descending delays;
    `load_asc_series` docstring and `step="filename"` branch.

## Usage notes (first round)

- Files store masked points as NaN, and readers return plain arrays. Re-mask with
  `np.ma.masked_invalid` before averaging or `subtract_pre_t0`; otherwise a single
  NaN at a negative delay turns a whole wavelength row into NaN.
- `stack_traces` raises if the axes differ, which also catches stray files in a
  glob (e.g. `s00_ITOS_ab_*.dat` matched by `s00*.dat`).

## Candidate next steps

Done 2026-11-12:
- Quick fixes above.
- Loaders to the TA standard; `collect-asc` writes the TA layout; `load_txt` is the
  legacy reader.
- Axis constants (`edyx.io`), `shift_trace` (masks kept, `edges="clip"|"nan"`),
  `crop`, `subtract_pre_t0`, `avg_scans`, `avg_spectra` (`edyx.tana`);
  `pcf_correct`, `fluo_wl` (`edyx.fana`).
- `edyx.plot.plot_maps`.

Remaining:
- Argument-order convention for the older functions (`band_integral`, ...), when
  they are next touched.
- Notebook templates (TA, FLUPS) as short sequences of calls.

5. `pyspan`: comparison slicer, then `ScanInspector` (cell 15 + range rejection,
   including wavelength rows), returning a mask. Done 2026-11-12 (`Overlay`,
   `ScanInspector`, `T0Picker`; see `pyspan_design.md`).
6. ~~`T0Curve`~~: dropped (2026-11-13). The fit stays in the notebook, which writes
   the sampled curve with `write_calibration`.
7. Regression test: reproduce the 250709 `.dat` outputs (run in env `main`). Add
   one FLUPS dataset once its inputs are located.
8. Extend the calibration pattern to the PCF and the ITOS calibration. Done
   2026-11-13 (`edyx.calib`, `tana.itos_calibration`).
