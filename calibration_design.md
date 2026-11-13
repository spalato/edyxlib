# Calibration files: use cases and decisions

Draft 2026-11-13, for discussion (answer inline with `> SP:`).

## Scope

- TA: t0 curve and wavelength calibration (ITOS). FLUPS: t0 curve and photometric
  correction (PCF). FLUPS wavelength: done by the hardware now, out of scope.
- A calibration is made from a reference measurement by a notebook, then applied to
  other measurements. Typically done once per day. Sometimes done more than
  once per day. Exceptionnally uses results from other days.
- TA and FLUPS need not share files. Tools of the same shape are easier to learn, so
  the proposal uses one pattern for all four.
- Agreed earlier: decisions (clicked points, fit model, windows) live in the notebook.
  The calibration file is a *product* of the notebook that made it, like a `.dat`
  output: re-running that notebook rewrites it. ITOS calibration is a candidate
  for full automation.
- Missing calibrations must not prevent running: this happens for preliminary work,
  instrument developpment. Warning is ok.

## Current practice

Seen in TA 250521, 250528, 250709, `edyx/scratch/261102`, and FLUPS 240619.

| Kind | Made by | Stored as | Applied as |
| --- | --- | --- | --- |
| TA t0 | `T0Picker` points, polynomial in eV | `<run>_t0corr.npz`: points `t0_meas`, sampled `t0_corr` (data grid), `pol_coeff` (low order first) | `t0_corr[:, 1]`, by index |
| TA wl | ITOS peaks paired with the reference, linear fit | `wl_corr.txt` (measured, calibrated) | `*_ab_*` files overwritten in place |
| FLUPS t0 | dye fits with errors, weighted fit (polynomial in eV; later `a + b/wl**2 + c/wl**4`) | `np.polyfit` coefficients (high order first), and the sampled `<dye>_t0_curve.txt` (`wl_u`, t0) | sampled curve, after checking the axes are equal; plus `t0_offset` (Raman line) in the notebook |
| FLUPS PCF | dye spectra vs references, stitched, smoothed | `pcf_final.npz` (`wl`, `pcf`), on `wl_u`, NaN outside the valid range | `np.interp` (`pcf_correct`), ends held |

Findings:
- **TA data is not on the calibrated axis.** On all three TA days, `ITOS_peak` rewrites
  only the linear `*_ab_*` files. The TA notebooks never read `wl_corr.txt`, so the TA
  `.dat` outputs, and the t0 points clicked on them, are on the measured axis. At
  276 nm, the measured axis is 2.3 nm below the calibrated one (250709). This is either
  a mistake or it was applied later.
- Reuse across days may occur: `250528/` holds a copy of `s1013_t0corr.npz` from
  250521, and 261102 loads `250307_s1213_thf_t0corr.npz`. Appears common in this
  selection of datasets, but rarely done in reality.
- Applying a sampled t0 by index silently gives the wrong wavelength's t0 on another
  grid (after a crop, or with another detector range). 
- Coefficient conventions differ between TA (low order first) and FLUPS (high order
  first).

## Use cases

- **C1. Make**, from a reference measurement, in a notebook. TA t0: points, then a fit
  the user chooses. TA wl: ITOS peak pairing, linear fit. FLUPS t0: dye fits, weighted
  fit. FLUPS PCF: stitched and smoothed curve. Output: one file.
  Experience says ITOS is highly robust, and is a candidate for full automation.
- **C2. Apply** to the other measurements of the same day: one line per calibration
  in the processing notebook.
- **C3. Reuse on another day**: the notebook names a file from another folder. The
  data grid may differ (crop, recalibration). Lab practice is to copy files in
  the current date folder when needed. Date in the filenames facilitate this.
- **C4. Regenerate**: re-run the notebook of C1; the decisions are in its cells.
- **C5. Check**: see what a calibration is (kind, axis, source, how it was made) and
  plot it, without opening the notebook that made it.
- **C6. Old files**: `_t0corr.npz`, `wl_corr.txt`, `_t0_curve.txt`, `pcf_final.npz`
  will be phased out. THey can always be reused by writing the code explicitly.

## Decisions to settle

### D1. Which wavelength axis TA data uses

Were TA spectra meant to be on the ITOS-calibrated axis?

- Proposal: yes. The wavelength calibration is applied when a scan is read, before
  anything else, so t0 points are picked on the calibrated axis too. Raw files stay
  unchanged (no rewriting in place).
  > SP: Correct. Never rewrite a raw file. Keep application explicit for user
    either by explict function call or argument passing (no automagic).
- Existing t0 files are then on the measured axis. Their axis must be recorded (D3),
  or they must be converted once.
  > SP: the original wl axis is approximate due to constraints of live usage.
    Calibration shifts deterministically: it only changes with specific
    manipulations. Its the user's responsability to match
    calibrations to files. Done correctly, the wl axes are remain identical
    as long as nothing is touched. The t0-wl curve shifts independently of wl-pix. Ie:
    t0 is a function of wl, not pixel. Do not prevent the user to apply calibrations
    of his/her choice.

### D2. What is stored: a sampled curve, or model parameters

- Proposal: always a sampled curve `x, y`, evaluated by interpolation. Model name and
  coefficients are kept as information, not used to evaluate.
- Why:
  - the t0 model is the user's choice, so storing only parameters would mean that edyx
    knows every model;
  - the PCF has no model;
  - one apply function for all kinds.
- Cost: interpolation instead of exact evaluation. This is negligible when sampled on
  the detector grid.

### D3. Apply by value, with an explicit out-of-range policy

Always by value on the data's own axis, never by index. The policy for each kind:
- wl: the raw axis must equal the calibration's `x`, or it is an error. Extrapolating
  a wavelength map is wrong, and holding the ends would duplicate wavelengths.
  > SP: Correct. However, don't get in the way of the user.
- t0: NaN outside `x` (proposal), or hold the end values? *Scientific choice.*
  > SP: Typically an error. Facilitate recalulation of t0 from wavelength.
- PCF: today the ends are held (`np.interp`). Keep that, or NaN outside? *Scientific
  choice.*
  > SP: depends on use case. Suggestion: add a keyword argument: "error|constant|nan".
    The user is likely to manipulate the pcf array in the notebook himself.
- Each file records the axis its `x` is on: `wl` (calibrated), `wl_raw` (measured,
  TA), or `wl_u` (FLUPS upconverted).
  > SP: OK

### D4. One file per calibration, or one file per day

- Proposal: one file per calibration.
- Why: calibrations are made by different notebooks at different times, and reuse
  across days mixes them (today's wl with another day's t0). With one file each, a
  notebook just lists the paths it uses. A file per day would need read-modify-write
  and would mix provenance.
  > SP: correct. There may be multiple calibrations per day: wl and t0 shift
  when we perform specific manipulations.

### D5. Format: toml, or two-column text

- Proposal: toml, one file holding the metadata and the arrays.
  - `toml` is already an `edyx` dependency, and the reference spectra are in toml.
  - Checked: arrays round-trip exactly, NaN included.
  - Size: the 1600-point PCF is 45 kB. Each array is written on one long line:
    readable for the metadata, less so for the numbers.
- Alternative: two-column text with a commented header, like `wl_corr.txt` and
  `_t0_curve.txt`. That is easier to read with `np.loadtxt`, but the metadata needs a
  small header parser.
  > SP: toml accepted. Ensure exporting metadata is easy, ie: the attribute should
    be easily converted to standard datatypes.

### D6. FLUPS details (scientific)

- Is the Raman `t0_offset` part of the t0 calibration (written in the file) or a
  parameter of each measurement (in the notebook)?
- Manual adjustments of fitted points (`t0 -= 0.02`): in the making notebook, before
  writing the file (proposal).
  > SP: These are manual offsets. Keep manual.

### D7. Names

Proposal: `<date>_<kind>_<source>.toml`, e.g. `250709_t0_s2027.toml`,
`250709_wl_itos.toml`, `240619_t0_PBBO.toml`, `240619_pcf.toml`.
> SP: let user specify "source". This allows for multiple calibrations on a
given day.

## Proposed file

```toml
kind = "t0"                  # t0 | wl | pcf
axis = "wl"                  # axis of x: wl (calibrated), wl_raw (TA measured), wl_u (FLUPS)
units = ["nm", "ps"]         # x, y
date = 2025-07-09            # date of the reference measurement
source = "s20-s27"           # reference measurement
made_by = "ta_s2027.ipynb"   # notebook that wrote this file
notes = ""
x = [275.76, 276.57, ...]
y = [-1.19, -1.17, ...]

[fit]                        # optional, for information
model = "polynomial in eV, low order first"
coef = [...]
```
> SP: good. Could they be concatenated into a sidecar file (looking forward)?

## Code (proposal, after the decisions)

- New module `edyx.calib`, plain functions on dicts:
  - `write_calibration(path, kind, axis, x, y, **meta)`, `read_calibration(path)`
    returning a dict with `x` and `y` as arrays;
    > SP: sounds ok.
  - `evaluate(cal, x, outside="nan"|"hold")`: the curve at `x`, by value;
    > SP: function name too generic. Outside=default to `error`.
  - `calibrate_wl(cal, wl_raw)`: the calibrated axis, error unless `wl_raw` equals
    `cal["x"]`.
    > SP: no, use `evaluate` proposal above. Don't block the user from using the code,
       they know better. 
- `shift_trace(t, s, t0)` and `pcf_correct(...)` stay as they are: they take the
  evaluated arrays.
- Old files (C6): one function each to convert to the new file
  (`from_t0corr_npz`, ...), run once, or read in place? *To decide.*
  > SP: explicit conversion.
- `T0Curve` is no longer needed: the fit stays in the notebook (plain numpy), which
  then writes the file. `T0Picker` gives the points.
- `ITOS_peak` becomes: peaks, fit, `write_calibration(..., kind="wl")`. No more
  rewriting of data files.
  > SP: consider full automation. THis is possible by applying the same peak-picking
    algorithm to reference and measured data.
