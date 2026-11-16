# FLUPS workflow: design draft

Draft 2026-11-16, round 4: all answers folded in. No open questions; ready to
implement.

Once settled, this file is condensed into [design.md](design.md) and removed (as for the
TA design notes). The principles and conventions of `design.md` apply unchanged:
explicit calls, decisions as literals, derived data recomputed, calibrations by value,
raw data never rewritten. This file covers only what is specific to FLUPS.

## The tasks

| Task | How often | Input | Output | Where |
| --- | --- | --- | --- | --- |
| Collect the runs | every day | Andor `.asc` per delay | `<date>_<run>.dat` | `flups collect-asc` |
| Fluorescence references | once per day | fluorimeter csv (replicas) | corrected reference spectra | `flups prep-fluo` (new) |
| t0 determination | once per day | dye runs (regular acquisitions, no PCF) | `<date>_t0_<source>.toml` (axis `wl_u`) | template `flups_1_t0` |
| PCF determination | once per day | PCF runs per dye, reference spectra | `<date>_pcf_<source>.toml` (axis `wl_u`) | template `flups_2_pcf` |
| Processing | every measurement | measurement runs, t0 and PCF files | `<date>_<root>.dat` (axis `wl_f`) | template `flups_3_processing` |

- The preparation is automated (the `flups` CLI): when the data is good, one command
  per step, no options. The decisions stay in the templates.
- The templates go in `pyspan/examples/FLUPS`. The collected lab notebooks there are
  removed once the templates replace them; `flups_compare` is merged into
  `flups_3_processing`.
- Order of work: `flups_3` first (t0 reuses its first steps), then `flups_1`, then the
  `flups` CLI and `flups_2`.
- **Preferences differ between users** (t0 bands, model, 1 or 2 passes; smoothing). The
  template shows one way, in plain code the user edits. The library provides the steps
  that encode a lab convention, not the fits.
- Which runs are what (t0 dye, measurement, PCF trial) is the user's knowledge, written
  as file lists in the notebook. The library never infers it.

## Data

Lab data on the group drive: FLUPS in `_DATA\FLUPS\YYYY\YYMMDD`, fluorimeter in
`_DATA\Fluo\YYYY\YYMMDD`.

Copies for development, not committed:
- `edyx/scratch/260605` (172 MB, git-ignored through `*.asc`):
  - `run01`-`run14`: Andor `.asc`, one file per delay (`runNN_sigNNNN.asc`) and one
    `runNN_bg.asc`, 1600 rows of `wl_u, counts`. The delay is in the first pixel. The
    acquisition subtracts the background: `bg` is a record only.
  - `PCF/<dye>/runNN`: C153 (3 runs), C6H (3), PBBO (9; some are trials). 10 frames
    each at a fixed delay.
  - `wl_u` is identical in all runs (249.95 to 523.59 nm).
- `edyx/scratch/fluo_260605` (git-ignored):
  - `260605_C153_ac_1mm.csv`, `260605_C6H_ac_1mm.csv`, `PBBO_ac_all.csv`: Cary Eclipse
    exports, 4-5 replicas each, one trial replica in each file.
  - `EmCorr_combined_220_800.csv`: the fluorimeter intensity calibration, columns
    `wavelength, pcf`, 220-800 nm in 1 nm steps.
- `edyx/scratch/fluo_261006` (**not** git-ignored yet; `.gitignore` covers only
  `fluo_260605`. Suggest `edyx/scratch/fluo_*/`):
  - `C153_ac_1mm.csv`, `C6H_ac_1mm.csv`, `PBBO_ac_1mm_1.csv`, and a `.FBSW` (Cary
    binary batch file) for each: the csv is the source, the `.FBSW` are ignored.

## Conventions

### Wavelength axis

- `wl_u` comes from the device. No calibration. It can change between measurements, as
  the user chooses.
- So every FLUPS calibration is on `axis = "wl_u"` and applied by value
  (`interp_calibration`), as in TA. A t0 curve or PCF from another measurement works
  as long as the measurement's `wl_u` is within its range.
- `wl_f = fluo_wl(wl_u, gate)` is computed when needed, never stored as the axis of a
  calibration.
- Jacobian, analytic: `d wl_f / d wl_u = wl_f**2 / wl_u**2`. A spectrum per unit `wl_f`
  (the fluorimeter reference) times `wl_f**2 / wl_u**2` is per unit `wl_u`; a FLUPS signal
  (per unit `wl_u`, per pixel) times `wl_u**2 / wl_f**2` is per unit `wl_f`.

### Input files

- FLUPS starts from the `flups collect-asc` output, `<date>_<run>.dat` (wl x t), read
  with `read_dat`, like TA. `load_txt` stays for the legacy `.txt` files.
- **Fix first:** `load_asc_series(step="first")` reads the delay from pixel 0 but keeps
  pixel 0 in the trace: every collected file has a fake first row at 249.95 nm holding
  the delays. Pixel 0 is dropped when the delay is read from it. Files collected so far
  keep the row; `read_dat` users drop it by hand (`wl[1:], s[1:]`).

### File names

Raw files are never touched; everything derived goes in the FLUPS dated folder.

| File | Name | Where | Made by |
| --- | --- | --- | --- |
| fluorimeter, raw | as saved, `[<date>_]<dye>_<extra>.csv` | `_DATA\Fluo\YYYY\YYMMDD` | Cary |
| fluorimeter, processed | `<date>_<stem>_corr.dat`, e.g. `261006_C153_ac_1mm_corr.dat` | `PCF\` in the FLUPS dated folder | `flups prep-fluo` |
| fluorimeter intensity calibration | `emcorr_cary-eclipse.toml` (kind `emcorr`, axis `wl`) | package data in `edyx` (static) | converted once |
| FLUPS PCF runs, raw | `PCF\<dye>\runNN\runNN_sigNNNN.asc` | FLUPS dated folder | acquisition |
| FLUPS PCF runs, collected | `<date>_PCF_<dye>_runNN.dat` | `PCF\<dye>` | `flups collect-asc` |
| FLUPS PCF mean per dye | `<date>_PCF_<dye>_mean.dat` (wl, counts) | next to the notebook | `flups_2` |
| PCF | `<date>_pcf_<source>.toml`, e.g. `260605_pcf_dyes.toml` | next to the notebook | `flups_2` |
| t0 curve | `<date>_t0_<source>.toml`, e.g. `260605_t0_PBBO.toml` | next to the notebook | `flups_1` |
| processed measurement | `<date>_<root>.dat` | next to the notebook | `flups_3` |

- In `<date>_<stem>_corr.dat`, `<date>` is the name of the fluorimeter's dated folder
  and `<stem>` the raw file name without a leading date: 260605 (`260605_C153_...`)
  and 261006 (`C153_...`) give the same pattern.
- The dye name in the PCF file names is the name of the `PCF\<dye>` folder. The
  notebook pairs each FLUPS dye with its reference explicitly (a dict literal), so a
  raw name that breaks the pattern (`PBBO_ac_all.csv`) still works.
- Headers are a descriptive log: inputs, replicas used, calibration files, parameters.

### Example data in the repo (plan, not committed yet)

In `edyx/examples/260605/`, about 25 MB:
- the PCF runs, collected (15 files, ~0.2 MB each);
- one t0 dye run and two measurement runs, collected;
- the fluorimeter csv files.

`240619` stays (legacy `.txt`, the lab's outputs for regression checks). The 261006
fluorimeter files go into the tests of `prep-fluo` (two clean files, one with a trial
replica).

## Shared first steps (all three templates)

Read, despike, reject, average. Same calls as TA, plus despiking.

```python
t, wl_u, stack = stack_traces([read_dat(f) for f in fnames])
despiked = np.array([despike_median(s, despike_size, threshold=despike_threshold) for s in stack])
plot_maps(...)            # despike check: raw, despiked, removed; not interactive
insp = ScanInspector(t, wl_u, despiked, rejections=rejections, ...)
avg = avg_scans(insp.masked())
```

Decisions: `despike_size`, `despike_threshold`, `rejections`, `threshold`.

- **Despiking:** `despike_median`, in all three templates (`flups_2` included). The
  threshold is a number in the template, with the recipe as a comment: ~2 x the
  (p95 - p5) span of a background region.
- `despike_median_p` (threshold relative to the local 5-95 % span; good but slow,
  ~40 s per scan) stays in the library. `_partition`, `_slow` and `_old` are removed
  from `fana`.
- Despiking replaces values; it does not mask them. Recording what was replaced is the
  open "repair as a decision kind" point of `design.md`, not part of this work.

## flups_3_processing

1. Shared first steps.
2. Optional: per-scan background (`t_bg`) against a drift, and pre-t0 subtraction of
   the average (`t_pre`). Both are choices. The acquisition already subtracts the
   background.
3. t0: `t0 = interp_calibration(read_calibration(t0_file), wl_u)`, then
   `t_s, shifted = shift_trace(t, avg, t0)`. `t0_offset` (e.g. from the Raman line) is
   a number in the notebook, up to the user: `t_s = t_s - t0_offset`.
4. PCF: `pcf_correct(wl_u, shifted, read_calibration(pcf_file))`. NaN in the PCF become
   masked points.
5. Fluorescence axis: `wl_f = fluo_wl(wl_u, gate)`; the signal per unit `wl_f` is the
   signal times `wl_u**2 / wl_f**2`, an explicit line.
6. Save on `wl_f`, figure.

Missing calibrations follow `design.md`: `t0_file = None` or `pcf_file = None` skips
the step with a warning.

- **`pcf_correct`** becomes `pcf_correct(wl_u, s, cal, outside="nan")`, through
  `interp_calibration`, so the PCF is applied like every other calibration. Today it
  uses `np.interp`, which holds the end values silently.

## flups_1_t0

1. Shared first steps on the t0 runs of one dye: stacked, rejected and averaged as in TA.
   Which runs belong together is the user's choice (`fnames`). No PCF, no shift.
2. Band kinetics: a dict `{wl_center: band_average(wl_u, avg, (lo, hi))}`, including the
   cross-correlation / Raman band(s). Bands are a decision literal.
3. Fits, in the template with lmfit (already an `edyx` dependency):
   - CC/Raman bands: Gaussian + constant, t0 = center;
   - dye bands: `edyx.models.conv_exp` + constant; second pass optional, with tau fixed
     to the weighted mean of the first.
4. Points: one array of rows `(wl_u, t0, t0_err)`, CC/Raman and dye together.
5. Several dyes (to cover a wider range): the runs of each dye up to the points, then the
   points of all dyes stacked before the curve fit. A note in the template, not code.
6. Curve: `t0 = a0 + a1/wl_u**2 + a2/wl_u**4`, weighted by `1/t0_err`. A polynomial of
   degree 2 in `1/wl_u**2`:
   `Polynomial.fit(points[:, 0]**-2, points[:, 1], 2, w=1/points[:, 2]).convert()`.
   Plotted with the points; reduced chi² as an optional cell.
7. `write_calibration(..., "t0", "wl_u", wl_u, t0, fit={"model": "a0 + a1/wl_u**2 +
   a2/wl_u**4, low order first", "coef": ..., "points": points})`.

- pandas and seaborn are not needed: the points are one array.
- No new `edyx` function: the fits are the users' choices, and each step is a few lines.
  If the same fit loop shows up in every user's copy, it becomes a function later.
- Old t0 files (`np.polyfit` coefficients, highest order first, on `nm2eV(wl)`): a
  conversion snippet in `edyx/README.md`.

## The `flups` CLI

One typer app with subcommands, for discoverability:

```
flups collect-asc     collect the .asc runs of a day into .dat files
flups prep-fluo       prepare the fluorimeter references for the PCF
flups help            the commands, the order of a FLUPS day, where the templates are
```

- `[project.scripts] flups = "edyx.scripts.flups:app"`. The subcommands live in their
  own modules (`collect_asc.py`, `prep_fluo.py`); `flups.py` only assembles them.
- `flups --help` and `flups <cmd> --help` come from typer. `flups help` adds the
  workflow: the order of the steps, the folder layout, the names of the templates.
- The `collect-asc` entry point stays, as an alias of `flups collect-asc`. It is
  FLUPS only (TA uses another instrument).

### Run from the FLUPS dated folder

The user works in `_DATA\FLUPS\YYYY\YYMMDD`. With no arguments, each subcommand acts on
that day:

```
cd \\server\_DATA\FLUPS\2026\261006
flups collect-asc
flups prep-fluo
```

Each command prints what it read and wrote, and the reason for every file it skipped.
A file that fails does not stop the others; the exit code is 1 if any failed (as
`collect-asc` does today).

### `flups collect-asc`

- No argument: the current folder. It collects every `run*` folder and every
  `PCF\<dye>\run*` folder.
- Names follow the path below the dated folder: `run03` gives `261006_run03.dat` next
  to the run folders; `PCF\PBBO\run01` gives `PCF\PBBO\261006_PCF_PBBO_run01.dat`.
- An existing `.dat` is never overwritten: its run is skipped, and reported as
  skipped. `--force` collects it again. (Raw runs are never rewritten, so a collected
  run stays valid.)

### `flups prep-fluo`

Reads the Cary csv files of the day, averages the replicas, applies the intensity
calibration, writes the references in `PCF\`.

What the files show:
- Each csv holds several replicas as column pairs (`Wavelength (nm), Intensity (a.u.)`),
  then a metadata block per replica: collection time, instrument serial number,
  excitation wavelength, slits, PMT voltage, range, "Corrected spectra OFF".
- **261006 is better behaved.** C153 and C6H: 3 replicas each, same grid (325-650 nm),
  same settings, no saturation. PBBO: 3 such replicas, plus a trial taken first
  (400-453 nm, excitation 350 nm, PMT `Medium`, saturated at 1000).
- 260605 has a trial in each file, with the same signature: shorter range, another PMT
  voltage, saturated.
- Replica names repeat (`261006_PBBO_ac_1mm_1` three times), and their case and date
  prefix vary (`c153_ac_1mm_1`, `261006_C6H_ac_1mm_1`). Replicas are identified by
  their position (1-based), not their name.
- The current `read_cary_uv` cannot read these files: the truncated replicas leave empty
  fields, which `np.loadtxt` rejects.

Design:
- **Sources.** By default, the fluorimeter folder of the same date (the usual case):
  `<root>\FLUPS\YYYY\YYMMDD` gives `<root>\Fluo\YYYY\YYMMDD`, printed. An explicit
  folder or file list replaces it: `flups prep-fluo \\server\_DATA\Fluo\2026\261005`.
- **Which replicas.** All replicas with the same grid and settings (excitation, slits,
  PMT voltage, range, interval) as the majority are averaged. The others are excluded
  with a warning that gives the reason and the override:
  `PBBO_ac_1mm_1.csv: replica 1 excluded (PMT Medium, range 400-453); --use to choose`.
  - No majority (a tie, or all different): the file fails with the table; the user
    picks with `--use 2,3,4`.
  - A replica at the top of the scale (1000) is saturated: the file fails, even if it
    is in the majority. Data out of range is the one check that blocks.
  - `--use` overrides the selection for one file.
- **Intensity calibration.** Static, package data in `edyx`
  (`emcorr_cary-eclipse.toml`, converted once from `EmCorr_combined_220_800.csv`).
  Multiplied, by value (`interp_calibration`, `outside="error"`). Valid for all
  settings. `--emcorr FILE` overrides; `--no-emcorr` skips with a warning. (One
  fluorimeter in the lab: no instrument check.)
- **Output.** `PCF\<date>_<stem>_corr.dat`, two columns `wl, intensity`. The header names
  the source file, the replicas used and excluded with the reasons, the calibration
  file and the instrument settings.
- **Table.** Printed for every file: index, name, wl range, points, max, PMT voltage,
  excitation, used or excluded.
- **edyx functions**, usable from a notebook too:
  - `read_cary_fluo(fname)`, for the Cary Eclipse fluorimeter: a list of replicas,
    each `(name, wl, intensity, meta)`; `meta` is the parameter list as a dict.
    Handles ragged columns. A separate function from `read_cary_uv` (Cary UV-Vis,
    absorption, another instrument): different content (replicas and settings vs one
    array), and the user knows which device the file comes from. `read_cary_uv` is
    unchanged: its name already names its device, and a rename would break its users
    (`pyspan.io` re-exports it). If it ever meets ragged columns, it can reuse the
    parser of `read_cary_fluo`.
  - The selection and the averaging stay in the CLI module: they are the CLI's policy,
    not a library function.

With 261006, `flups prep-fluo` writes three files with no options, and reports that the
PBBO trial (replica 1) was excluded.


## flups_2_pcf

Two decisions: the validity bounds of each dye, and the smoothing. Everything else
follows the lab notebook's method.

1. **Measured spectra.** For each dye: read the collected PCF runs, despike, `Linear`
   (runs as files, frames as repetitions; RMSD threshold), then the mean over the runs
   of the dye: `meas[dye]` on `wl_u`. Replaces `average-dyes`.
2. **Reference spectra**, on `wl_f`, one line per dye, the user's choice:
   - the `flups prep-fluo` output (current best practice);
   - fallback: the Gerecke lognormals, `ref_spec_wl(wl_f, "C153")`. The table has C6H,
     C153 and DCM only (BBOT is commented out as suspect), so no fallback for PBBO.
3. **Reference on `wl_u`:** interpolate on `fluo_wl(wl_u)`, times the Jacobian
   `wl_f**2 / wl_u**2`.
4. **Normalization** to the maximum, measured and reference, as in the lab notebook.
5. **Curve per dye:** `pcf[dye] = ref_u / meas[dye]`, NaN outside `bounds[dye]`.
   **Decision 1:** `bounds = {"PBBO": (275, 360), ...}`, with a plot of the reference
   and measured spectra, and of the curves.
6. **Stitching** (new `fana` function, `pcf_scales`):
   - minimizes the sum over dye pairs and overlapping points of
     `(s_i * pcf_i - s_j * pcf_j)**2`, with the first dye fixed to 1;
   - closed form (linear system): the lab's objective (RMSD, Nelder-Mead), solved
     exactly. The lab's bounds on the scales (0 to 10) are dropped;
   - raises if a dye overlaps no other dye;
   - returns the scales; the template plots the scaled curves.
7. **Smoothing**, as in the lab notebook: the scaled points of all dyes, sorted, a
   `UnivariateSpline` (`s = factor * N`), then a Savitzky-Golay filter on the `wl_u`
   grid. **Decision 2:** the spline factor and the filter window and order, with a plot
   of the curves and the result. Plain scipy in the template.
   The lab notebook also fits a degree-7 polynomial, only plotted: dropped.
8. **Write** `<date>_pcf_<source>.toml`, axis `wl_u`, NaN kept outside the valid range.
   `fit`: dyes, bounds, scales, smoothing parameters, reference source per dye.

## Changes to design.md

- Open points, scientific: the Jacobians `wl_u` to `wl_f` and wavelength to energy are
  settled (analytic). What stays open is the conversion from the FLUPS signal to the
  equivalent stimulated-emission signal, to compare with TA. (Done in this branch.)
- Principles: "CLI wrappers for batch processing are not needed" stays true for the
  processing. The `flups` CLI automates the preparation (collecting, references),
  which has no decisions when the data is good.
- After this round: the FLUPS sections (templates, calibrations, the `flups` CLI,
  names).

## New and changed code (summary)

| Where | Change |
| --- | --- |
| `edyx.io.load_asc_series` | drop pixel 0 when the delay is read from it |
| `edyx.io` | `read_cary_fluo` (Cary Eclipse: replicas, ragged columns, metadata); `read_cary_uv` unchanged |
| `edyx.scripts` | `flups` app: `collect-asc` (moved, day folder, PCF names), `prep-fluo` (new), `help` |
| `edyx` package data | `emcorr_cary-eclipse.toml` |
| `edyx/pyproject.toml` | `flups` entry point; `collect-asc` kept as an alias |
| `edyx.fana` | `pcf_correct(wl_u, s, cal, outside)`; `pcf_scales`; remove 3 despike variants (`despike_median_p` stays) |
| `edyx/README.md` | conversion snippet for old t0 coefficient files |
| `edyx/examples/260605/` | example data (plan above) |
| `pyspan/examples/FLUPS/` | `flups_1_t0`, `flups_2_pcf`, `flups_3_processing`; lab notebooks removed |
| tests | `load_asc_series`, `read_cary_fluo`, `flups collect-asc`, `flups prep-fluo`, `pcf_scales`, `pcf_correct`; regression on 240619 for `flups_3` |

pyspan is unchanged: `ScanInspector`, `Overlay` and `Linear` cover the decisions.

## Not in this round

- The provenance header and the light wrapper (`design.md`). The FLUPS decisions,
  listed here, feed that discussion: despike size and threshold, rejections, `t_bg`,
  `t_pre`, t0 file, `t0_offset`, PCF file, gate.
- A pyspan tool for the PCF bounds or smoothing: literals for now.
- One command for the whole preparation (`flups prep` = collect + references): only if
  the two commands are always run together.
