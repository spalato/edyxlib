# FLUPS workflow: from raw `.asc` to a processed map

Draft. This explains the whole chain for FLUPS (fluorescence upconversion spectroscopy) data, from the
Andor `.asc` files to the saved map on the fluorescence wavelength axis. The reference for the design
is [design.md](design.md) (section FLUPS); the code is in `edyx` (`fana`, `tana`, `calib`, `io`,
the `flups` CLI) and `pyspan` (interactive tools and the notebook templates).

## Overview

| Step | Input | Output | Tool |
| --- | --- | --- | --- |
| 1. Collect the runs | Andor `.asc`, one per delay | `<date>_runNN.dat` | `flups collect-asc` |
| 2. Fluorimeter references | Cary Eclipse csv (replicas) | `PCF/<date>_<stem>_corr.dat` | `flups prep-fluo` |
| 3. t0 | runs on a dye (no PCF) | `<date>_t0_<dye>.toml`, axis `wl_u` | notebook `flups_1_t0` |
| 4. PCF | PCF runs per dye, references | `<date>_PCF_<dye>_mean.dat`, `<date>_pcf_<dyes>.toml`, axis `wl_u` | notebook `flups_2_pcf` |
| 5. Processing | measurement runs, t0 and PCF files | `<date>_<root>.dat`, axis `wl_f` | notebook `flups_3_processing` |

Steps 1 and 2 are automated: no decisions, so they are command line tools. Steps 3 to 5 contain
scientific choices (despiking threshold, rejected data, bands, models, validity bounds, smoothing), so
they are notebooks that you copy and edit. The library provides the steps; the choices are yours.
Raw files are never modified, and existing outputs are never overwritten unless you ask.

## Axes and conventions

- `wl_u` is the detected (upconverted) wavelength, as given by the device.
- `wl_f` is the fluorescence wavelength. Only the final processed map is saved on `wl_f`.
- Signals are densities. Going between axes needs the Jacobian `d wl_f / d wl_u = wl_f**2 / wl_u**2`:
  a signal per unit `wl_u` times `wl_u**2 / wl_f**2` is per unit `wl_f`.
  `fana.upconvert(wl_f, sig)` and `fana.downconvert(wl_u, sig)` return the new axis and the converted
  signal (masks kept). They do not interpolate; that is up to you.
- Data layout: arrays are `(wavelength, delay)`, a stack of scans is `(file, wl, delay)`.
  `.dat` files hold the delay axis, the wavelength axis and the data (`edyx.io.read_dat`, `write_dat`).
- Calibration files are small `.toml` files holding the sampled curve (`x`, `y`), its `kind` and `axis`,
  and metadata (date, source, who made it). A `[fit]` table keeps the model and coefficients for
  information only. They are applied with `interp_calibration` (`edyx.calib`).

## Folder layout in the lab

```
_DATA\FLUPS\YYYY\YYMMDD\
    runNN\runNN_sigNNNN.asc          measurement runs (delay in pixel 0 of each spectrum)
    PCF\<dye>\runNN\...              PCF runs, one folder per dye
_DATA\Fluo\YYYY\YYMMDD\*.csv         fluorimeter exports (Cary Eclipse)
```

## Step 1: collect the runs

From the FLUPS dated folder:

```powershell
cd _DATA\FLUPS\2026\260605
flups collect-asc
```

Every `run*` folder below the current folder (any case, any depth, including `PCF\<dye>\runNN`) is read
and written next to the run folder, named after the path below the dated folder:

```
260605\run03\...asc          ->  260605\260605_run03.dat
260605\PCF\PBBO\run01\...    ->  260605\PCF\PBBO\260605_PCF_PBBO_run01.dat
```

The dated folder is the nearest parent whose name starts with 6 digits (used as is, e.g. `260605b`).
Without one the file is named `<parent>_<run>.dat`, with a warning.

By default, existing files are skipped. To force a new run, use `--force`.

Useful options: arguments to restrict to a subtree or a single run (`flups collect-asc 260605\PCF`,
`flups collect-asc 260605\run01`, wildcards accepted), `--force` to collect again, `--outdir`,
`--step` (default `first`: the delay is read from pixel 0 of each spectrum and that pixel is removed),
`--pattern` (default `*_sig*.asc`; on Windows write `--pattern=*sig*.asc`). A failing run does not stop
the others; the exit code is then 1.

Files collected before edyx 0.3 contain the delays as a fake first row: collect again with `--force`.

## Step 2: fluorimeter references

```powershell
flups prep-fluo
```

From the FLUPS dated folder this reads the fluorimeter folder of the same date
(`FLUPS\YYYY\YYMMDD` to `Fluo\YYYY\YYMMDD`), or the folders/csv files you give as arguments. For each
csv:

1. The replicas that share the wavelength grid and settings of the majority are averaged. The others
   are excluded, with a warning saying why. A table lists the replicas and their status.
2. The Cary Eclipse emission correction (`emcorr_cary-eclipse.toml`, shipped with edyx) is applied.
3. The result is written to `PCF\<date>_<stem>_corr.dat` (columns: `wl_f`, intensity), with a header
   listing the replicas used and excluded, the settings and the calibration. The date comes from the
   file name, else from a parent folder.

It stops on a file when a replica is saturated (reaches 1000), or when there is no unique majority.
Then choose the replicas yourself: `flups prep-fluo file.csv --use 2,3` (1-based, one file at a time).
Other options: `--outdir`, `--force`, `--emcorr FILE`, `--no-emcorr` (warns).

`flups help` prints a short version of steps 1 and 2.

## Common first steps in the notebooks

The three templates (`pyspan/examples/FLUPS/`) share the same skeleton as the TA ones:

1. `stack_traces` stacks the runs of one measurement into `(file, wl_u, delay)`. Which runs belong
   together (t0 dye, measurement, PCF trials) is your knowledge: list them in `fnames`. Runs listed
   together must stack (same axes).
2. `despike_median(data, size, threshold)` replaces the points that differ from the local median by
   more than `threshold` counts. Both are choices. A recipe for the threshold, written in the
   notebooks as a comment: about 2 x (p95 - p5) of a region without signal. Despiking replaces values;
   it does not mask them. A `plot_maps` figure (raw, despiked, removed) is the check.
3. Compare and reject: `Overlay` to compare scans, `ScanInspector` (or `Linear` for the PCF runs) to
   reject points, delays, wavelength rows or whole files, and to see the RMSD of each scan against
   the median.
4. Average the kept data (`avg_scans`).

**How the interactive tools record decisions.** Each tool is preceded by a *decisions* cell and
followed by a cell calling `print_decisions()`. Click, then paste the printout into the decisions
cell and re-run: the notebook then reproduces your choices with "Run all" and no clicks. Do this
before saving. Rejections are literals `(file, wl, t)`: `None` is all, an index, or a `(start, stop)`
range with stop excluded. The notebooks need `%matplotlib widget` (JupyterLab or VS Code, with
`ipympl`). Choices are marked `# choice`.

Note: with two files the median of the scans is their mean, so both have the same RMSD and the
threshold cannot single one out.

The templates assume well-formed data and existing calibration files. Skipping a step means editing
the notebook.

## Step 3: t0 (`flups_1_t0`)

Goal: the time zero as a function of `wl_u`, from runs on a dye (here PBBO, no PCF, no shift).

1. Read, despike, compare the scans, reject, average (common steps).
2. **Bands.** A dict `{center: (lo, hi)}` in nm of `wl_u`, over the range where the dye emits (here
   2 nm wide bands every 3 nm over 283-346 nm). Kinetics are the band averages (`band_average`).
   A cross-correlation or Raman line, if present, goes in as a band too: fit it with a Gaussian plus a
   constant and take the centre as t0.
3. **Fit each band** with lmfit: `conv_exp` (decay convolved with a Gaussian) plus a constant baseline
   before t0. `t0` is the time of the rise. Optional second pass with `tau` fixed to the weighted
   mean of the first pass, useful when the decay is slow compared to the window. Bands with no
   uncertainty on t0 are dropped and printed. Rejected points (NaN) are left out of the fits.
   This workflow was established with PBBO, you may need to change it when using other dyes.
4. **Fit the curve.** Points `(wl_u, t0, t0_err)` from all bands (of all dyes if several, to cover a
   wider range) are fitted by `t0 = a0 + a1/wl_u**2 + a2/wl_u**4`, weighted by `1/t0_err**2`.
   The reduced chi2 is printed as a check. You can adjust the model if required.
5. **Write** `<date>_t0_<dye>.toml` with `write_calibration(..., "t0", "wl_u", wl_u, t0, ...)`, the
   curve sampled on the whole `wl_u` axis. Model, coefficients and points go in `[fit]`.

The t0 curve is generally quite reproducible: it only changes when the optical path changes
significantly (ex: adding a transmissive optic, changing cell thickness). From day
to day, there may be small shift in t0 due to slight alignment differences, but they
can be applied to all wavelengths equally.

## Step 4: PCF (`flups_2_pcf`)

Goal: the photometric correction function: reference spectrum / measured spectrum, on `wl_u`, so that
a measured spectrum becomes the true one. Each dye is measured on the FLUPS setup (`PCF\<dye>` runs)
and in the fluorimeter (the references from step 2). Several dyes cover the full range and are scaled
to each other.

**Part 1: average the PCF runs of each dye.** A PCF run is one delay with several frames, axes
`(wl_u, frame)`. Read and despike the runs of each dye, then `Linear` (one per dye; runs are the files,
frames the repetitions) rejects bad frames by their RMSD against the median of the run. The mean of the
kept frames of each run, averaged over the runs, is saved as `<date>_PCF_<dye>_mean.dat` (columns
`wl_u`, counts). Choose runs with care: trials at other delays or frames of zeros must not be listed.

**Part 2: PCF from the means and the references.**

1. Reference of each dye: load the `prep-fluo` output, convert with `upconvert`,
   interpolate on the FLUPS measurement axis, normalize. Alternative reference when no measured one exists: the lognormal fits of Gerecke et al. in
   `fana.ref_spec_wl` (C6H, C153, DCM; none for PBBO).
2. Per dye, curve = reference / measured, kept only within **validity bounds** (decision 1): nm of
   `wl_u`, where reference fluo and PCF measurement are above the noise. The red edge of an emission spectrum is the more
   reliable one. Adjust the bounds until agreement is acceptable.
3. `pcf_scales` scales the curves to each other: closed-form minimization of the squared differences
   where two dyes overlap, the first dye fixed to 1. It raises if the dyes do not form one overlapping
   group.
4. **Smoothing** (decision 2): a smoothing spline through all the scaled curves (smoothing factor), then
   a Savitzky-Golay filter (window, degree).
5. **Write** `<date>_pcf_<dyes>.toml`, on `wl_u`, NaN outside the valid range. Dyes, bounds, scales,
   references, gate and smoothing go in `[fit]`.

The two decisions (bounds, smoothing) and the rejected frames are the only choices that move the
result; the template prints and plots everything needed to judge them.

## Step 5: processing (`flups_3_processing`)

Goal: the measurement runs, corrected and on the fluorescence axis. Needs the t0 and PCF files.

1. Read, compare first and last run (sample degradation, drift), despike, reject, average.
2. **Pre-t0 subtraction** (optional): subtract the spectrum before time zero (`subtract_pre_t0`, delays
   `t < t_pre`).
3. **Shift t0.** `interp_calibration(read_calibration(t0_file), wl_u)` evaluates the t0 curve at the
   measured wavelengths, and `shift_trace(t, data, t0)` moves each wavelength so its t0 is at delay 0
   You can then subtract a `t0_offset` if a t0 drift is apparent.
4. **PCF.** `pcf_correct(wl_u, shifted, read_calibration(pcf_file))` multiplies by the PCF. Wavelengths
   outside the PCF range become masked points.
5. **Fluorescence axis.** `wl_f = fluo_wl(wl_u, gate)`, and multiply by `wl_u**2 / wl_f**2` to get the
   signal per unit `wl_f`. Compare with and without PCF in an `Overlay`.
6. **Save** `<date>_<root>.dat` on `wl_f`. Rows with no PCF are cropped; remaining masked points
   (rejected data) are written as NaN. The header logs the scans, despiking, rejections, t0 and PCF
   files, `t_pre`, `t0_offset` and the gate. A PNG of the map is saved next to it.

## A day, in order

1. Measure the PCF dyes (`PCF\<dye>`), the t0 runs on a dye, and the measurement runs; take the
   fluorimeter spectra of the dyes.
2. `cd` to the FLUPS dated folder; `flups collect-asc`; `flups prep-fluo`.
3. Copy `flups_1_t0`, `flups_2_pcf` and `flups_3_processing` next to the data and edit the parameters
   cell (file lists, dye names, gate, thresholds). Outputs go next to the notebook.
4. Run `flups_1_t0` (t0 file), `flups_2_pcf` (PCF file), then `flups_3_processing`.
5. t0 and PCF are calibrations: if they are valid for the next day or sample, reuse the files and
   run only step 5. `wl_u` can change between days, but calibrations are applied by value on `wl_u`,
   so the measurement's `wl_u` must lie within the range of the file (`pcf_correct` masks the rest).

## Files written, summary

| File | From | Content |
| --- | --- | --- |
| `<date>_runNN.dat` | `collect-asc` | one run, `wl_u` x delay |
| `PCF/<dye>/<date>_PCF_<dye>_runNN.dat` | `collect-asc` | one PCF run, `wl_u` x frame |
| `PCF/<date>_<stem>_corr.dat` | `prep-fluo` | reference, `wl_f`, intensity |
| `<date>_t0_<dye>.toml` | `flups_1_t0` | t0 curve on `wl_u` |
| `<date>_PCF_<dye>_mean.dat` | `flups_2_pcf` | mean PCF run of a dye, `wl_u`, counts |
| `<date>_pcf_<dyes>.toml` | `flups_2_pcf` | PCF on `wl_u` |
| `<date>_<root>.dat`, `.png` | `flups_3_processing` | processed map on `wl_f`, per unit `wl_f` |

## Example data and test

- `edyx/examples/260605`: data for the three templates (runs 01-02 t0 on PBBO, 03-04 measurement,
  PCF runs of PBBO, C6H and C153, fluorimeter csv and references). See its README.
- `edyx/examples/240619` and `edyx/tests/test_regression_240619.py`: the chain run on a legacy day
  reproduces the lab's previous results.

## Installation

Install `edyx` (CLI, processing) and `pyspan` (notebooks, interactive tools) in the shared `edyxenv`
environment; see [uv_monorepo.md](uv_monorepo.md).

## Open points

See design.md: better FLUPS example data (260605 has trial runs and no CC/Raman line), a pyspan tool for
the PCF bounds or smoothing (literals for now), and the conversion from the FLUPS signal to the
equivalent stimulated-emission signal.
