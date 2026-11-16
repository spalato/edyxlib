# edyx and pyspan: design of the processing (TA, FLUPS, calibrations)

Status 2026-11-14: milestone. Done:
- the core of TA processing in `edyx`;
- the interactive tools in `pyspan` (released 0.3.3);
- calibration files in `edyx`;
- the TA templates.

This file replaces `ta_workflow_design.md`, `pyspan_design.md` and `calibration_design.md`.
Their full discussion (findings, alternatives, dates) is in git history, up to commit
`30c6ab1`. Package structure and install profiles: [uv_monorepo.md](uv_monorepo.md).

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
  are not needed (YAGNI).
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
  - `collect-asc` writes `<date>_<run>.dat`.
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
| `fana` | FLUPS: `despike_median` (and variants), `pcf_correct`, `fluo_wl(wl_u, gate=1340)`, reference spectra |
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

| Tool | For | "Done" prints | Result |
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
  - After clicking, the result follows the clicks, not the record: paste "Done" and
    re-run before saving.
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
- **Missing calibration.** No function needs one. In a notebook, the file is a
  parameter, and `None` skips the step with a warning (pattern in `edyx/README.md`).
- **Old files** (`_t0corr.npz`, `wl_corr.txt`, `_t0_curve.txt`, `pcf_final.npz`):
  converted once with the snippets in `edyx/README.md`.
- **Finding:** TA data recorded so far is on the measured axis. `ITOS_peak` rewrote
  only the linear files. At 276 nm the measured axis is 2.3 nm below the calibrated
  one (250709).

## Templates and examples

- `edyx/examples`:
  - `ta_average_t0` and `flups_average_t0_pcf` reproduce the lab's 250709 TA and
    240619 FLUPS outputs;
  - they convert the legacy calibration files.
- `pyspan/examples/TA`, run in this order:
  1. `ta_1_linear_itos`: `Linear`, the ITOS calibration with a plot of the paired
     peaks, the calibration file, spectra saved on the calibrated axis.
  2. `ta_2_processing`: read, calibrate wl, `Overlay`, `ScanInspector`, average,
     pre-t0 subtraction, `T0Picker`, t0 fit and calibration file, shift, save.
- `pyspan/examples/FLUPS`: `flups_compare`, and the lab notebooks collected for the
  next round.
- Data: `edyx/examples/data` holds copies of lab data, unchanged (see its README).

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

- **Release edyx** (0.3.0): `edyx.calib`, `itos_calibration` and `tomli-w` are on
  `main` only. The pyspan TA templates need them, so pyspan should then require
  `edyx>=0.3`. Release with `scripts/release.ps1`.
- **FLUPS templates**, from the collected notebooks. Two of them hardcode a local
  path; use `data_dir = Path(".")`.
- **Regression tests in CI.** The edyx examples reproduce the lab outputs, but pytest
  doesn't run them. Either a pytest that runs the same steps, or executing the
  notebooks.

## Provenance and sidecars (discussed 2026-11-14, not implemented)

Settled:
- **No merged calibration file.** Calibrations stay one file each.
- **Decisions stay in the notebook.** No decisions sidecar that the tools read or
  write: it would be a second source of truth, and hidden state.
- **The output header names calibration files**, never their contents, so it stays
  readable. For example, the t0 points stay in the t0 file.

Plan, in this order:
1. **`provenance(**items)` in `edyx.io`**, plus a counterpart that reads it back.
   - One `key = literal` line per item, in the format "Done" prints (`format_literal`);
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
3. **FLUPS waits** for its templates. Their decisions (despiking parameters,
   `pcf_file`, `t0_offset`, gate) will show whether one shape fits both techniques.

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
  - Jacobians (`wl_u` to `wl_f`, wavelength to energy, FLUPS to stimulated-emission
    equivalent; exponents to confirm).
- **Later:**
  - a metadata structure for output names and headers (users document well today);
  - assisted t0 picking (pre-placed points, accepted or moved by the user);
  - papermill or snakemake to reprocess a whole day;
  - marimo, to try on the linear workflow.
