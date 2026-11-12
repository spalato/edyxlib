# TA and FLUPS workflow redesign: discussion notes

Status: design discussion, nothing implemented yet. Started 2026-10-29.
Updated 2026-11-12 with the notebooks in `edyx/scratch/` (TA, FLUPS, linear).

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
- Calibrations are necessary on a daily basis. Reuse might be limited, but that 
  is a scientific constraint.
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
- New rejection form: wavelength rows in a single file (`sig_masked[-1,[282,283],:]`,
  a cosmic in the background). Rejection must cover files, delays and wavelengths,
  alone or combined. This was due to the background signal, which likely had a
  cosmic there.
- Scan subsets by acquisition order again: early/late averages with
  `np.arange(n) % 4 < 2` (FLUPS). Acquisition index should be explicit, not taken
  from list order.
- Masks are lost silently: the masked average goes through `np.interp` before the
  shift, which uses the data under the mask (checked). This matters wherever a point
  is masked in every file. NaN survives the same calls.
- t0 curve is a polynomial in eV in both, but:
  - Point source differs. TA clicks points. FLUPS fits `conv_exp` + constant on
    2 nm bands of a reference dye, in two passes (tau free, then tau fixed to the
    weighted mean), which gives t0 *with errors*. Both then do "points to polynomial".
  - FLUPS fits the polynomial with weights 1/t0_err and chooses the order by
    reduced chi² (orders 1-4 tried, 2 kept). It also fits the cross-correlation
    (Gaussian at 266 nm) to get the IRF width.
    The attempt at multiple orders was a trial. In general, user should
    determine. Newer versions will try to use `a+b/wl**2+c/wl**4`
  - Coefficient conventions differ. TA saves `Polynomial(...).convert().coef`
    (low order first) in `.npz`, together with the sampled `t0_corr`, and reuses
    the sampled values. FLUPS saves `np.polyfit` output (high order first) to `.txt`
    and evaluates it on the current grid with `np.poly1d(p)(nm2eV(wl))`. The FLUPS
    notebook ends with "save parameters instead, look at TA".
  - Fitted points get a manual adjustment
    (`timings.loc[..., "t0"] -= 0.02`, "compensate for slight overlap"): an
    override that should be logged.
- Edge policy in use: FLUPS disables clipping (`t_c = t`, NaN edges kept), then
  crops a time window (-1 to 5.5 ps) just before saving. Confirms `edges="nan"` and
  adds an explicit crop step.
- N = 1 shape problems in FLUPS too (`np.atleast_2d(axes)`,
  `'Axes' object is not iterable`).
- Colour limits set per notebook in both. FLUPS mixes fixed limits and percentiles.
  This is ok, depends on the dataset.
- `spectra_view` (delay slider, overlay of 2 datasets, 3 in `some_functions.py`) is
  copied into two FLUPS notebooks and `some_functions.py`, each with a different
  hard-coded `xlim`. It is the scan comparison view applied
  to processed results (with/without PCF, first/last scan).
  Spectra view, allowing comparison of spectra or kinetics, it is a useful
  interactive tool.
- Helpers redefined locally although they are in the library: `between`, `nm2eV`,
  `shift_kin`. TA reimplements `edyx.fana.shift_trace`.

### TA only (261102)

- Output name concatenated from loose variables (`date`, `sample`, `solvent`,
  `step`, `rel_pol`, `pump_power`, `pump_wl`), with `out_root` sliced from file names
  (`fnames[0][1:-4]`). Structured metadata would give both the name and the header.
- Wavelength crop (`cut_wl`) right after loading.
- Two background subtractions: per file before t0 (`bksub`, used for RMSD and plots),
  then the averaged negative-delay spectrum (`negspec`) after averaging. The average
  is taken over `dod_masked`, built from raw `dod`, not from `bksub`. Same result for
  a plain mean, different when masks remove different points per file. It is done
  twice in order to allow for the next processing steps.
- Single-scan output: the shift code is copied a second time to process `bksub[0]`
  alone. The pipeline must accept one scan without a stack.
- Extra outputs for degradation checks: negative-delay spectra of the first and last
  scans, and `negspec`. Secondary outputs need the same naming and provenance.
- The t0 curve is loaded from another dataset (`250307_s1213_thf_t0corr.npz`) and
  applied as the sampled `t0_corr[i, 1]`, by index. If that file was made on a
  different grid (for example before `cut_wl`), each wavelength silently gets
  another wavelength's t0.
- Notes to self in the notebook: fit and shift buttons, a t0 class, a two-panel
  display (original + polynomial, shifted). This matches the planned t0 picker.
- Polarisation: `rel_pol` (`'m'`, presumably magic angle) in the output name, and
  anisotropy functions in `some_functions.py`. Parallel/perpendicular pairs need a
  combination step, downstream of averaging.

### FLUPS only

- Input layout is transposed: `load_txt` gives t x wl (TA `.dat` is wl x t),
  sometimes with descending t. Both stack-loading notebooks reverse and transpose by
  hand ("this should not be necessary in the future"). Files are named `run##.txt`
  or `run##.dat`. Final outputs are written with `pack_trace` (TA layout),
  intermediate ones with `save_txt` (t x wl) or `np.savetxt(np.column_stack(...))`.
- Signal is counts, positive: mostly sequential colormaps (`Blues`, `plasma`); some
  later plots use `coolwarm` / `RdBu_r` at ±10.
- Spectral axis can be pixels: `if np.allclose(wl, np.arange(wl.size)+1)` triggers a
  linear pixel-to-nm calibration written in the notebook. The constants differ
  between notebooks (slope 0.123 vs 0.171025); which one is current is unknown.
  This is a holdover from a previous apparatus. Now the detector includes the
  wavelength.
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
- Photometric correction function (PCF): a multiplicative spectral calibration,
  made rarely and reused, like t0.
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
  hard-coded in three places. Outputs are saved on `wl_f`. Gate wavelength has
  never changed so far.

### Linear and wavelength calibration

- `261102_linear_template` uses `Linear` as intended (`from_files`, `spectra_dict`,
  one figure and one file per input). No workarounds.
- `ITOS_peak`: peaks on the measured and reference ITOS spectra
  (`edyx.tana.load_itos_spectrum`), paired by order, linear fit, saved to
  `wl_corr.txt`. Then the `*_lin_*dat` data files are **overwritten in place** with
  the corrected axis. Data files should stay immutable: apply calibrations at load
  and log them.

### Downstream analysis (`some_functions.py`)

- `band_integral(deltaA, wl, wl_lim, band_average=False)` is a fork of
  `edyx.tana.band_integral` / `band_average`: different argument order, trapezoid
  instead of Simpson, and NaN handling (all-NaN delays stay NaN, other NaN count as 0).
- Anisotropy: `anis`, `magic`, `anis2theta`, `theta2anis`, `PAS`. Candidates for
  `edyx.tana`, outside the processing pipeline.

### Notebook defects

Evidence for "copy calls, not implementations":
- `wl_u = 0.171025+249,59` is a tuple, not a calibration (only reached for pixel axes).
- `timings["sample"] == "eun03.dat"`: typo, so the manual t0 adjustment is a no-op.
- Degradation output: header says `scan1\scan8` but saves `dod[0]` and `dod[1]`.
- `spectra_view(..., dat2=sig[3])` with 2 files: `IndexError`.
- FLUPS main: `NameError` on `wl_u`, unterminated `'''` in the crop-and-save cells.

## Agreed so far

- Three widgets: **manual rejection**, **scan comparison** (already in the
  "Plot the kinetic transients at specific wavelength" cell, which overlays every
  file at the selected wl), **t0 picker**. Rejection and comparison could share
  one view: select a range, then press "reject".
- **The user stays in control of the pipeline.** No rigid declarative recipe:
  experiments need structural variants (padding, edge policies, interpolation
  instead of masking, whole-file and time-range rejection), and a recipe
  turns into a poor configuration language that blocks the scientist.
- Library code holds the implementations. The template notebook is a short
  sequence of explicit calls. Copying calls is fine; copying implementations is not.
- **Return values and store them on the object** (as `Linear` already does).
  Two requirements:
  1. Staleness: store *decisions* (mask, bg windows, `T0Curve`) and derive
     data (`avg`, `shifted`) as cached properties that are cleared when a
     decision they depend on changes. Calculations are not expensive, consider
     simply recalculating as required.
  2. Workarounds: an explicit override (`proc.avg = padded`) that is logged
     in provenance and used by later steps. Rerunning upstream steps warns
     instead of discarding it. This sounds like a recipe for disaster, consider
     simply recalculating as required.
- Common variants become parameters (`how="mask"|"interpolate"`,
  `edges="clip"|"zero"|"nan"`, `pad=`). One-off workarounds stay in the notebook
  as plain numpy, and move into the library when they recur.
- Provenance is a *descriptive* log (step + params, plus overrides), written
  into the output header.
- No sidecar files for now: notebooks are self-documenting, so decisions live
  in the notebook.
- **Output format: ASCII `.dat`, like the input files.**
  *(2026-11-12: there are two layouts. TA `.dat` is wl x t; FLUPS input is t x wl,
  sometimes also named `.dat`. FLUPS final outputs use the TA layout (`pack_trace`),
  intermediate ones use `save_txt` (t x wl). See open questions.)*
- **Build order: pure functions first.** Wrap them in a stateful object later.

## Proposed from the scratch notebooks (not agreed)

- One core shared by TA and FLUPS. Technique modules add steps around it:
  - TA: pre-t0 background, scatter subtraction, clicked t0.
  - FLUPS: pixel calibration, despiking, t0 fitted on a dye, PCF, fluorescence axis.
    > SP: pixel calibration is not expected to be necessary in the future, due 
      to hardware upgrade.
- One loader per file format, all returning the same in-memory type: ascending
  axes, fixed axis order, signal kind (ΔOD or counts), spectral axis kind (pixel,
  nm, upconverted nm). 
    > SP: Use TA standard.
- A third kind of decision besides rejection and overrides: **repair** (despiking).
  Store its parameters and the positions it replaced, and log them in provenance.
  > SP: correct. A historical version "repaired" the TA shots by interpolation.
        This has a few specific advantages.
- **Calibration objects** share one pattern: made rarely from a reference
  measurement, saved with their source, evaluated on the current grid, referenced by
  file name in provenance.
  - `T0Curve`: polynomial in eV with one fixed coefficient convention.
  - PCF (spectral response): sampled curve, with interpolation and an out-of-range
    policy.
  - Wavelength calibration (pixel to nm, ITOS): polynomial.
    > SP: only Itos will be required in the future.
  - IRF width, if it is reused.
  - Each calibration records the axis it was made on. In FLUPS, the t0 polynomial
    (eV of the upconverted wavelength) and the PCF (sampled on that axis) are applied
    before the `wl_f` conversion, so step order is constrained.
    > SP: Correct. Consider if consolidating the calibrations to a early version
      of a sidecar file would be beneficial. Prefer text-based, toml, if possible.
- t0 points from either source (clicks, or dye fits with errors) go through the
  same fit: weighted polynomial, order chosen by the user with reduced chi² shown.
  This partly answers "assisted t0 picking".
- New functions: `crop(t=, wl=)`, `despike`, `apply_response`,
  `to_fluorescence_wl(gate=)`, and a reduction over delays (dye spectra, linear).
  > SP: generally correct. Avoid overdesigning basic operations (ex: average).
- Metadata (sample, solvent, pump, polarisation, step, gate...) as one structure
  that builds both the output name and the header. Secondary outputs (negative-delay
  spectra, single scans, early/late subsets) go through the same save function.
  > SP: keep for later. Current workflow is fine in this regards (users keep good
  documentation already.)
- Plot defaults follow the signal kind: diverging and symmetric for ΔOD, sequential
  with percentile limits for counts.
  > SP: Yes. Implement utility functions in `edyx/plot` (see `layout.txt`)
      with reasonable defaults. User likely to change limits depending on data,
      and colormap to taste.
- One comparison viewer for both uses: files of a stack, and processed results
  (with/without PCF, first/last scan), with a delay or wl slider.
  > SP: Yes. KISS: start with a slicer comparing spectra or kinetics for a stack
     let the user pass the data himself. Comparison was also the purpose
     of some 3 columns of colormaps: data, filtered, filtered-data. Consider
     utility function.

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

- In-memory data type for the functions (plain arrays vs labelled axes
  `file`, `wl`, `t`). On-disk format is settled: `.dat`.
  > SP: use basic data types as much as possible. Built-ins and numpy arrays, or
    thin wrappers over those. Skilled users found the `{"filename": (t,wl,s)}`
    data structure puzzling at first, but convenient once understood.
- Mask representation (separate mask array vs NaN); `.dat` has no room for a
  separate mask, so NaN is the natural fit. The notebooks show that `np.ma` masks
  get dropped silently by `np.interp`, which supports NaN.
  > SP: masked arrays are for processing only. Replace with nan when saving to file.
    Silent dropping may be a bug.
- Output layout: use the TA layout (wl x t) for all outputs of both techniques,
  including intermediates (FLUPS currently uses both)? Can the FLUPS acquisition
  write it at the source, so the loader only handles legacy files?
  > SP: TA everywhere. FLUPS acquisition uses `collect-asc` as a first step.
- Despiking: which algorithm and threshold (benchmark notes above), and whether
  replaced values should be masked instead.
  > SP: defer. This is a scientific step on the users, not on the agent.
- Outlier rejection: trimmed average (suggested in FLUPS) vs RMSD vs median.
  > SP: defer. This is a scientific step on the users, not on the agent.
- Physics of the FLUPS corrections, to check with the authors: where the Jacobian
  belongs when the data axis is converted to `wl_f`, and why the excluded pixel
  ranges and t0 bands are excluded.
  > SP: FLUPS has multiple jacobians: `wl_u` (as detected) -> `wl_f`. `wl` -> energy, wavenumber (sometimes)
    and conversion from FLUPS to equivalent stimulated emission, for comparison
    with TA. This implies both a factor `wl_f**2` for intensity conversion in 
    FLUPS, and `wl_f**2` for spontaneous vs stimulated. Document clearly.
- Calibration storage: format (text with header vs `.npz`), coefficient convention,
  and how a notebook refers to a calibration made on another day.
  > SP: Further discussion needed. Consider `toml`.
- Placement: shared core in a new `edyx` module vs in `tana`. `fana` already holds
  `shift_trace` and the despike functions. Widgets go to `pyspan`.
   > SP: in `tana`, `fana`. Widgets will go to pyspan.
- Polarisation combination (magic angle, anisotropy): pipeline step or downstream?
  > SP: functions already present, trivial. 
- Naming: `TAStack` (immutable raw data) vs `TAProcessing` (stateful session).
  > SP: Leaning `TAStack` 
- Outlier tests that work for 1 or 2 files (neighbouring delays in the same file,
  pairwise differences between files).
  > SP: later.
- Assisted t0 picking (pre-placed points from `conv_exp` fits or steepest rise,
  then accepted or adjusted by the scientist).
  > SP: later.
- Whether to split `Linear` into model and view the same way.
  > SP: yes.

## Quick fixes, independent of the redesign

- `sorted(glob(...))`.
- `edyx.io.pack_trace` docstring: says trace is (M, N) with M = len(t), but rows are
  wavelengths.
- `edyx.io.load_txt` doesn't sort descending delays; the FLUPS notebooks do it
  by hand.
- `import edyx.fana` fails: `toml` is not a dependency, and
  `refspec_Gerecke_RSI_2016.toml` (read at import, `try` commented out) is not in
  the repo. So `shift_trace` and the despike functions can't be imported right now.
  > SP: file added. Add toml to dependencies.

## Candidate next steps

1. Define the core data type (the file format is `.dat`) and the first pure functions.
   Cover both loaders (TA wl x t, FLUPS t x wl with descending delays).
2. `ScanInspector` widget (cell 15 + range rejection), returning and saving a mask.
   Include wavelength-row rejection.
3. `T0Curve` with an edge policy and save/load. One coefficient convention, a
   weighted fit from points, and two point sources (clicks, dye fits).
4. Regression test: reproduce the 250709 `.dat` outputs (run in env `main`). Add
   one FLUPS dataset once its inputs are located.
5. Extend the calibration pattern to the PCF and the wavelength calibration.
