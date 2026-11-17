# edyx and pyspan: design of the processing (TA, FLUPS, calibrations)

Status 2026-11-16: milestone, released as edyx 0.3.1 and pyspan 0.4.0. Done:
- the core of TA processing in `edyx`;
- the interactive tools in `pyspan`;
- calibration files in `edyx`;
- the TA templates;
- FLUPS: the `flups` CLI, the PCF chain and the templates.

This file replaces `ta_workflow_design.md`, `pyspan_design.md` and `calibration_design.md`
(full discussion in git history, up to commit `30c6ab1`), and `flups_design.md` (up to
commit `7153608`). Package structure and install profiles: [uv_monorepo.md](uv_monorepo.md).

## Principles

- **Code is ours, science is the users'.** The library provides consistency,
  streamlining and usability. Choices with scientific impact are explicit parameters,
  never silent defaults. Examples: despiking, outlier test, t0 model, excluded
  ranges, Jacobians, peak picking, which calibration goes with which data.
- **The user controls the pipeline.**
  - No declarative recipe: experiments need structural variants, and a recipe turns
    into a poor configuration language.
  - A notebook is a short sequence of explicit calls. Copying calls is fine; copying
    implementations is not.
  - Examples are templates to start from. The user is responsible for using them
    correctly, so they carry no safeguards.
- **Don't get in the way.** No automatic steps, and no checks that block the user.
  Data must be in a valid range, nothing more. When a check is needed, it raises with
  a clear message (wrong peak count, value outside a calibration). Missing
  calibrations never block a run.
- **Unix-like at the function level.** Small pure functions on basic data types:
  numpy arrays (masked during processing), built-ins, the `{fname: (t, wl, s)}` dict.
  A stateful wrapper comes only if it is needed. CLI wrappers for batch processing
  are not needed (YAGNI). The `flups` CLI automates only the preparation (collecting
  runs, fluorimeter references), which has no decisions when the data is good.
- **Store decisions, recompute data.**
  - Decisions (rejections, t0 points, thresholds) are literals in the notebook.
  - Derived data is recomputed, with no cache and no overrides. A workaround is plain
    numpy whose result goes to the next call.
  - A workaround that recurs becomes a parameter (e.g. `edges="clip"|"nan"`).
- **Weigh every new function**, its benefit against its cost in maintenance and
  learning. Small helpers that encode a convention are good (`avg_spectra`). Names
  say what a function does, in the lab's terms (`pcf_correct`, `fluo_wl`).
- **Raw data files are never rewritten.** Calibrations are applied when the data is
  read.
- **Dependency isolation.**
  - `edyx`: I/O, analysis and static matplotlib plots.
  - `pyspan`: every interactive tool (ipywidgets, ipympl), the fragile dependencies.

## Conventions

- **Layout.** A trace is `(t, wl, s)`, with `s` as wl x t and ascending axes. A stack
  is (file, wl, t). The axis constants are in `edyx.io`: `FILE_AXIS = -3`,
  `WL_AXIS = -2`, `TIME_AXIS = -1`. They are negative, so they work on both traces and
  stacks.
- **Argument order.** The axes the function uses, in `(t, wl)` order, then the data,
  then options; writers take the file name first. Only the axes that are needed:
  `band_integral(wl, da, bounds)`. All of `edyx/src` follows this.
- **Files.**
  - ASCII `.dat` in the TA layout everywhere, intermediates included (`write_dat`,
    `read_dat`).
  - Legacy FLUPS `.txt` files (t x wl) are read with `load_txt`.
  - `flups collect-asc` writes `<date>_<run>.dat` (names: see FLUPS).
  - All readers return wl x t with ascending `t`.
- **Masks.** Masked arrays during processing, NaN on save. Functions keep masks;
  dropping one silently is a bug. `read_dat` masks NaN, the inverse of `write_dat`.
- **File order.** `sorted(glob(...))`, so file indices in decision literals keep their
  meaning.
- **Outputs.** Names start with the date (`250709_s4044.dat`), and files go next to
  the notebook. The header is a descriptive log: scans, parameters, calibration files.

## edyx: the processing core

| Module | Contents |
| --- | --- |
| `io` | `read_dat`, `write_dat`, `stack_traces` (checks the axes), `load_txt`, `load_npz`, `load_asc_series`, `read_ab_dat`/`read_ab_stack`, axis constants |
| `tana` | shared by TA and FLUPS: `shift_trace(t, s, t0, edges="clip"\|"nan")`, `shift_kin`, `crop`, `subtract_pre_t0`, `avg_scans`, `avg_spectra`, `band_integral`, `band_average`; ITOS: `load_itos_spectrum`, `itos_calibration` |
| `fana` | FLUPS: `despike_median`, `despike_median_p`, `pcf_correct(wl_u, s, cal)`, `pcf_scales`, `fluo_wl(wl_u, gate=1340)` and its inverse `upconv_wl(wl_f, gate=1340)`, `jacobian(wl_u, gate=1340)`, `upconvert(wl_f, sig, gate=1340)` and `downconvert(wl_u, sig, gate=1340)`, reference spectra |
| `calib` | `write_calibration`, `read_calibration`, `interp_calibration` |
| `plot` | `plot_maps` (N maps side by side, defaults by signal kind), `plot_flups` |
| `units`, `utils` | `nm2ev`, ...; `between`, `argnear`, ... |

TA and FLUPS share one core, with the technique steps around it:
- TA: pre-t0 background, scatter subtraction, clicked t0, ITOS wavelength calibration.
- FLUPS: despiking, t0 fitted on a dye, photometric correction (PCF), fluorescence
  axis.

`fana` imports the shared functions from `tana`.

## pyspan: decision tools

A tool helps the user make a decision and returns it as plain data. The next step is
an ordinary `edyx` call or plain numpy.

| Tool | For | `print_decisions()` prints | Result |
| --- | --- | --- | --- |
| `Overlay` | comparing datasets (each on its own axes): spectra at a delay, or kinetics at a wavelength | nothing | nothing |
| `ScanInspector` | rejecting scan data: delay ranges in a file, whole files, wavelength rows; optional RMSD threshold | `rejections`, `threshold` | `masked()`, `mask` |
| `T0Picker` | clicking t0 points, one wavelength row at a time (`tlim`, "Next after click") | `t0_points` | `points` |
| `Linear` | linear spectra: repetitions, RMSD threshold (applied to all files at once), means | `threshold` | `mean_spectra` |

- **Shape of a tool.** A small class, with one method per user action. These methods
  are tested without a browser. `show()` builds the widgets. The tool accepts earlier
  decisions as input, and edits are logged at INFO level.
- **Re-running without clicking** (2026-11-16). A decisions cell holds the pasted
  literal. The tool is initialized from it, and the next step uses the tool's result
  (`insp.masked()`, `picker.points`, `lin.mean_spectra`), not a copy of its logic.
  - The tool copies its input, so clicks never change the literal; nothing else
    changes it either (no globals mutated by widgets).
  - "Run all", with no clicks, gives the result recorded in the decisions cell.
  - After clicking, the result follows the clicks, not the record: paste the
    printout and re-run before saving.
  - **No "Done" button** (2026-11-17). A button that only prints is forgotten. The
    cell after the tool, which uses its result, calls `print_decisions()`, so the
    printout always matches what was used.
- **Rejection literal.** A list of `(file, wl, t)`. Each entry is `None` (all), an
  index, or a `(start, stop)` range with stop excluded. Plain functions in
  `pyspan.decisions`: `rejection_mask`, `rmsd_vs_median`, `above_threshold`,
  `format_literal`.
- **Legacy imports.** `pyspan.io`, `pyspan.utils` and `pyspan.itos` re-export the
  `edyx` functions, with a `FutureWarning`.
- **Not interactive:** ITOS calibration (automatic), the despike check (`plot_maps`),
  scan subsets (plain code), downstream figures.

## Calibrations

| Experiment | Calibrations |
| --- | --- |
| TA | wavelength (ITOS, `itos_calibration`), t0 (clicked points, fitted in the notebook) |
| FLUPS | t0 (dye fits), PCF. The wavelength is calibrated by the hardware. |

- **File.** One toml file per calibration, named `<date>_<kind>_<source>.toml`. It
  holds:
  - a sampled curve `x, y`;
  - `kind` and `axis`. `axis` is the axis of `x`: `wl` (calibrated), `wl_raw` (TA
    measured) or `wl_u` (FLUPS upconverted);
  - plain metadata (`units`, `date`, `source`, `made_by`, `notes`);
  - optionally a `[fit]` table (model, coefficients, points), kept for information and
    never used for evaluation.

  Written with `tomli_w` (UTF-8), read with `tomllib`. Arrays and NaN round-trip
  exactly.
- **Apply by value**, never by index: `interp_calibration(cal, x, outside="error")`.
  `"constant"` holds the end values, `"nan"` gives NaN outside. There is no other
  check, so any grid within range is accepted.
- **TA order.** The wavelength calibration comes right after reading, so t0 is picked
  on the calibrated axis. The fit is the user's choice, in the notebook; the notebook
  writes the sampled curve. There is no `T0Curve` class.
- **Manual offsets** (the FLUPS Raman `t0_offset`, point adjustments) stay as numbers
  in the notebook.
- **Missing calibration.** No function needs one. The templates assume their files
  exist (well-formed data only); to skip a step, the user edits the notebook, e.g.
  with the `None` pattern in `edyx/README.md`.
- **Old files** (`_t0corr.npz`, `wl_corr.txt`, `_t0_curve.txt`, `_FLUPS_t0_corr.txt`,
  `pcf_final.npz`, the fluorimeter `EmCorr` csv):
  converted once with the snippets in `edyx/README.md`.
- **Finding:** TA data recorded so far is on the measured axis. `ITOS_peak` rewrote
  only the linear files. At 276 nm the measured axis is 2.3 nm below the calibrated
  one (250709).

## FLUPS

| Task | Input | Output | Where |
| --- | --- | --- | --- |
| Collect the runs | Andor `.asc`, one per delay | `<date>_<run>.dat` | `flups collect-asc` |
| Fluorimeter references | Cary Eclipse csv (replicas) | `<date>_<stem>_corr.dat` | `flups prep-fluo` |
| t0 | runs on a dye (no PCF) | `<date>_t0_<source>.toml`, axis `wl_u` | `flups_1_t0` |
| PCF | PCF runs per dye, references | `<date>_PCF_<dye>_mean.dat`, `<date>_pcf_<source>.toml`, axis `wl_u` | `flups_2_pcf` |
| Processing | measurement runs, t0 and PCF files | `<date>_<root>.dat`, axis `wl_f` | `flups_3_processing` |

- **Preparation is automated, decisions stay in the templates.** From the FLUPS dated
  folder, `flups collect-asc` then `flups prep-fluo`, with no options when the data is
  good. `flups help` prints the order of a day and the templates.
- **Which runs are what** (t0 dye, measurement, PCF trial) is the user's knowledge,
  written as file lists in the notebook. Runs listed together must stack. The library
  never infers it.
- **Preferences differ** (t0 bands, model, one or two passes; smoothing). A template
  shows one way, in plain code the user edits. The library provides the steps that
  encode a lab convention, not the fits.

### Axes

- `wl_u` comes from the device: no calibration, and it can change between days. Every
  FLUPS calibration is on `axis = "wl_u"`, applied by value.
- `wl_f = fluo_wl(wl_u, gate)` is computed when needed. Only the processed measurement
  is saved on `wl_f`.
- Jacobian, analytic: `d wl_f / d wl_u = wl_f**2 / wl_u**2`. A reference per unit `wl_f`
  times `wl_f**2 / wl_u**2` is per unit `wl_u`; a FLUPS signal (per unit `wl_u`) times
  `wl_u**2 / wl_f**2` is per unit `wl_f`. `jacobian(wl_u, gate)` gives the factor;
  `upconvert(wl_f, sig, gate)` and `downconvert(wl_u, sig, gate)` return the other axis
  and the signal times or divided by the Jacobian, for a `(W,)` spectrum, a `(W, T)`
  trace or a `(..., W, T)` stack, masks kept. Neither interpolates: that step is the
  user's.

### Files and names

Lab data: FLUPS in `_DATA\FLUPS\YYYY\YYMMDD`, fluorimeter in `_DATA\Fluo\YYYY\YYMMDD`.
Raw files are never touched.

- **Runs:** `runNN\runNN_sigNNNN.asc`, delay in pixel 0; PCF runs in `PCF\<dye>\runNN`.
  Collected next to the run folder, named by the path below the dated folder:
  `260605_run03.dat`, `PCF\PBBO\260605_PCF_PBBO_run01.dat`. The dated folder is the
  nearest parent whose name starts with 6 digits, used as is (`260605b`). None: named
  `<parent>_<run>.dat`, with a warning.
- **References:** `PCF\<date>_<stem>_corr.dat` (`wl, intensity`). The date is the
  file name's own leading date, else the nearest dated parent folder; none:
  `<stem>_corr.dat`, with a warning.
- The templates' outputs go next to the notebook. The notebook pairs each dye with its
  reference explicitly (a dict), so raw names that break the pattern still work.
- Headers are a descriptive log: inputs, replicas, calibration files, parameters.
- Files collected before edyx 0.3 hold the delays as a fake first row: collect the day
  again with `--force`.

### The `flups` CLI

One typer app, `edyx.scripts.flups:app`; each subcommand lives in its own module. The
`collect-asc` entry point stays as an alias. With no arguments, each command acts on
the current day. It prints what it read, wrote and skipped (with the reason). A failing
file does not stop the others; the exit code is then 1.

- **`collect-asc`:** every `run*` folder (any case) below the arguments, each once. An
  existing `.dat` is never overwritten; `--force` collects it again.
- **`prep-fluo`:**
  - Sources: by default the fluorimeter folder of the same date (`FLUPS\YYYY\YYMMDD`
    to `Fluo\YYYY\YYMMDD`), or explicit folders and files.
  - Replicas: those with the grid and settings of the majority are averaged; the
    others are excluded with a warning naming the reason and `--use`. No majority, or
    a saturated replica (1000, out of range: the one check that blocks), fails the
    file; `--use 2,3` chooses (1-based, by position: names repeat).
  - Intensity calibration: `emcorr_cary-eclipse.toml`, static package data, multiplied
    by value (`outside="error"`), valid for all settings. `--emcorr FILE`,
    `--no-emcorr` (warning). One fluorimeter in the lab: no instrument check.
  - The selection and averaging are the CLI's policy, kept in its module. The reader
    is a library function: `read_cary_fluo` (replicas, ragged columns, metadata).
    `read_cary_uv` (absorption, another instrument) is unchanged.

### Templates

Shared first steps, as in TA plus despiking: `stack_traces`, `despike_median` (size and
threshold literals; the recipe, ~2 x (p95 - p5) of a region without signal, as a
comment), a `plot_maps` check, `ScanInspector` (or `Linear` for the PCF runs), average.
Despiking replaces values, it does not mask them. `despike_median_p` (relative
threshold, slow) stays in `fana`.

- **`flups_1_t0`:** bands are a literal (dye bands, and CC/Raman lines if any). Fits in
  the template with lmfit: Gaussian + constant for CC/Raman (t0 = center), `conv_exp`
  + constant for the dye, optional second pass with tau fixed. The band fits omit NaN
  (rejected points). Points `(wl_u, t0, t0_err)` of all bands, of all dyes if several.
  Curve `a0 + a1/wl_u**2 + a2/wl_u**4`, i.e. `Polynomial.fit` of degree 2 in
  `wl_u**-2`, weighted by `1/t0_err**2`. Written with the model, coefficients and
  points in `[fit]`. No new `edyx` function: each step is a few lines.
- **`flups_2_pcf`**, two steps, two decisions:
  1. per dye, `Linear` on the despiked runs (runs as files, frames as repetitions),
     mean over the runs, saved (`<date>_PCF_<dye>_mean.dat`);
  2. the reference (the `prep-fluo` output; fallback: the Gerecke lognormals,
     `ref_spec_wl`, none for PBBO) on `wl_u` with the Jacobian, both normalized; per
     dye, reference / measurement within **bounds** (decision 1); `pcf_scales`
     (closed form, the lab's objective solved exactly, first dye fixed to 1; raises if
     the dyes do not form one overlapping group); spline + Savitzky-Golay
     **smoothing** (decision 2); written on `wl_u`, NaN outside the valid range.
- **`flups_3_processing`:** optional pre-t0 subtraction; t0 by value and
  `shift_trace`; `t0_offset` (Raman) a number; `pcf_correct` (masked outside the PCF);
  times `wl_u**2 / wl_f**2`; saved on `wl_f`, rows without a PCF cropped.
- The templates assume well-formed data: the files of a stack share their axes, and
  the calibration files exist. Other cases are the user's.
- **Regression:** `edyx/tests/test_regression_240619.py` runs the chain on 240619
  (legacy `.txt`, t0 curve and PCF of the lab) and reproduces the lab's `sig_U` and
  `sig_F` to the 6 digits of their files.

## Templates and examples

- The templates are in `pyspan/examples`; `edyx` has no example notebooks
  (2026-11-16). Converting the legacy calibration files: `edyx/README.md`.
- `pyspan/examples/TA`, run in this order:
  1. `ta_1_linear_itos`: `Linear`, the ITOS calibration with a plot of the paired
     peaks, the calibration file, spectra saved on the calibrated axis.
  2. `ta_2_processing`: read, calibrate wl, `Overlay`, `ScanInspector`, average,
     pre-t0 subtraction, `T0Picker`, t0 fit and calibration file, shift, save.
- `pyspan/examples/FLUPS`, on 260605: `flups_1_t0`, `flups_2_pcf`, then
  `flups_3_processing` (see FLUPS).
- Data: `edyx/examples/<date>/`, one folder per day as in the lab (`250709` TA, `260605`
  and `240619` FLUPS):
  copies of lab data, unchanged, with the lab's outputs for checks (see each README).

## Why: what the lab notebooks showed

- The same skeleton was copied cell by cell in TA and FLUPS: load, per-file maps,
  RMSD, kinetic overlay, manual masking, mean, shift, save. Copied implementations
  carried defects (typos making steps no-ops, an `IndexError` with 2 files, tuples
  passed as calibrations).
- RMSD rejection against the median can't tell 1 or 2 files apart, and it was disabled
  in 9 of 11 notebooks. Manual rejection did the work, in four forms: single delays,
  late delays in all files, whole files, wavelength rows.
- Decisions depended on glob order (`[::2]`, `[0:2]`), and masks were lost silently
  (`np.interp` before the shift).
- Interactive widgets mutated notebook globals: results depended on side effects of
  clicks, which "Run all" did not reproduce.
- The t0 curve was applied by index, so on another grid each wavelength silently got
  another wavelength's t0. TA and FLUPS stored their coefficients in opposite orders.
- `ITOS_peak` overwrote data files in place. FLUPS files were t x wl, and both
  techniques transposed them by hand.

## Next

- **TA regression test in CI.** FLUPS has one (240619). For TA, `ta_1` checks only the
  linear spectra; the data for the full chain is kept (`250709/s4044*.dat`). A pytest
  that runs the same steps, as for FLUPS.
- **Better FLUPS example data.** 260605 has trial runs and no CC/Raman line; with a
  better day, the templates' literals (runs, bounds, thresholds) need a pass.

## Provenance and sidecars (discussed 2026-11-14, not implemented)

Settled:
- **No merged calibration file.** Calibrations stay one file each.
- **Decisions stay in the notebook.** No decisions sidecar that the tools read or
  write: it would be a second source of truth, and hidden state.
- **The output header names calibration files**, never their contents, so it stays
  readable. For example, the t0 points stay in the t0 file.

Plan, in this order:
1. **`provenance(**items)` in `edyx.io`**, plus a counterpart that reads it back.
   - One `key = literal` line per item, in the format `print_decisions()` prints (`format_literal`);
     file paths become names.
   - Read back with `ast.literal_eval`, which runs no code.
   - The user passes what they used in one call:
     `provenance(scans=names, wl_calibration=wl_file, rejections=rejections, t_pre=t_pre, t0_calibration=t0_file)`.
   - The TA templates use it in their save cell.
2. **A light wrapper for TA, only if the templates show the same decisions passed
   around repeatedly.** It holds raw data and decisions only, and its methods mirror
   the functions (`np.mean(a)` / `a.mean()`). Its rules:
   - **State:** raw `t`, `wl_raw`, stack and file names, plus the decisions as plain
     attributes (`wl_calibration`, `rejections`, `threshold`, `t_pre`,
     `t0_calibration`). The user sets them explicitly, from pasted literals.
   - **No derived data stored, no cache.** `wl`, `data` and the method results are
     recomputed on each call.
   - **Thin methods.** Each method is a one-line call to an existing `edyx` function,
     which stays the primary API (tests, docs).
   - **No mutation.** Methods never change the object.
   - **Calibrations by file name**, read when used.
   - **`header()`** uses `provenance()`, and `decisions` is a plain dict. That keeps a
     record file per output and papermill parameters possible later.
   - **Escape hatch.** Results are plain arrays: workarounds continue in plain numpy,
     outside the object. The header doesn't record them; the notebook is the full
     record.
   - **pyspan is unchanged.** The tools keep taking arrays.
   - **Containment.** Values that change the saved numbers are attributes; display
     options are arguments. One class per technique, each with a short fixed list of
     decisions, never a generic class with an open dict: otherwise this becomes the
     declarative recipe already rejected.
3. **FLUPS:** the templates' decisions are despike size and threshold, rejections,
   `t_pre`, the t0 file, `t0_offset`, the PCF file and the gate (PCF: runs, bounds,
   smoothing). They will show whether one shape fits both techniques.

Kept open:
- a record file per output, written once at save (inputs, calibration names,
  decisions). It is a record, not a driver: plain-numpy workarounds aren't in it.
- papermill parameters: tag the decisions cells, to reprocess in batch.

## Open points

- **Splitting `Linear`** into model and view: only if testing needs it.
- **Repair as a decision kind** (despiking: parameters and replaced positions,
  `out != data`), logged in the output header. Not implemented.
- **Shift edge cases.** A sub-step shift by linear interpolation smears the rise with
  coarse steps (8 ps). Zero padding stays plain numpy until it recurs.
- **Scientific, for the users:**
  - despiking algorithm and threshold, and whether replaced values are masked
    instead;
  - outlier rejection (trimmed average, RMSD or median), and tests that work with 1
    or 2 files;
  - the t0 model;
  - excluded ranges;
  - the conversion from the FLUPS signal to the equivalent stimulated-emission signal,
    to compare with TA. The Jacobians between `wl_u` and `wl_f` (analytic,
    `d wl_f / d wl_u = wl_f**2 / wl_u**2`) and wavelength to energy are settled.
- **FLUPS, later:** a pyspan tool for the PCF bounds or smoothing (literals for now);
  one `flups prep` (collect + references) only if the two are always run together.
- **Later:**
  - a metadata structure for output names and headers (users document well today);
  - assisted t0 picking (pre-placed points, accepted or moved by the user);
  - papermill or snakemake to reprocess a whole day;
  - marimo, to try on the linear workflow.
