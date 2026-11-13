# Calibration files: use cases and decisions

Decided 2026-11-13 (SP's answers folded in; the commit before this one has them
inline). Plan at the end.

## Scope

- TA: t0 curve and wavelength calibration (ITOS). FLUPS: t0 curve and photometric
  correction (PCF). FLUPS wavelength: done by the hardware now, out of scope.
- A calibration is made from a reference measurement by a notebook, then applied to
  other measurements. Typically once per day, sometimes more than once per day
  (wl and t0 shift with specific manipulations). Exceptionally, results from other
  days are used.
- TA and FLUPS need not share files. Tools of the same shape are easier to learn, so
  one pattern serves all four.
- Decisions (clicked points, fit model, windows) live in the notebook. The calibration
  file is a *product* of the notebook that made it, like a `.dat` output: re-running
  that notebook rewrites it.
- Missing calibrations must not prevent running (preliminary work, instrument
  development). A warning is fine.
- Don't get in the way of the user: no automatic application, no checks that block a
  calibration the user chose to apply. Matching calibrations to data is the user's
  responsibility.

## Current practice

Seen in TA 250521, 250528, 250709, `edyx/scratch/261102`, and FLUPS 240619.

| Kind | Made by | Stored as | Applied as |
| --- | --- | --- | --- |
| TA t0 | `T0Picker` points, polynomial in eV | `<run>_t0corr.npz`: points `t0_meas`, sampled `t0_corr` (data grid), `pol_coeff` (low order first) | `t0_corr[:, 1]`, by index |
| TA wl | ITOS peaks paired with the reference, linear fit | `wl_corr.txt` (measured, calibrated) | `*_ab_*` files overwritten in place |
| FLUPS t0 | dye fits with errors, weighted fit (polynomial in eV; later `a + b/wl**2 + c/wl**4`) | `np.polyfit` coefficients (high order first), and the sampled `<dye>_t0_curve.txt` (`wl_u`, t0) | sampled curve, after checking the axes are equal; plus `t0_offset` (Raman line) in the notebook |
| FLUPS PCF | dye spectra vs references, stitched, smoothed | `pcf_final.npz` (`wl`, `pcf`), on `wl_u`, NaN outside the valid range | `np.interp` (`pcf_correct`), ends held |

Findings:
- TA data is not on the calibrated axis: on all three TA days, `ITOS_peak` rewrites
  only the linear `*_ab_*` files, and the TA notebooks never read `wl_corr.txt`. At
  276 nm the measured axis is 2.3 nm below the calibrated one (250709). Either a
  mistake, or it was applied later (SP).
- The measured wl axis is approximate (constraints of live use). The calibration
  shifts deterministically, only with specific manipulations; untouched, the axes stay
  identical. t0 is a function of wavelength, not pixel: the t0-wl curve shifts
  independently of the wl-pixel calibration (SP).
- Reuse across days appears in these datasets (`250528/` holds a copy of
  `s1013_t0corr.npz` from 250521; 261102 loads `250307_s1213_thf_t0corr.npz`), but is
  rare in practice. Lab practice: copy the file into the current date folder; dates in
  the file names help.
- Applying a sampled t0 by index silently gives the wrong wavelength's t0 on another
  grid (after a crop, or with another detector range).
- Coefficient conventions differ between TA (low order first) and FLUPS (high order
  first).

## Use cases

- **C1. Make**, from a reference measurement, in a notebook. TA t0: points, then a fit
  the user chooses. TA wl: ITOS peak pairing, linear fit (robust: a candidate for full
  automation). FLUPS t0: dye fits, weighted fit. FLUPS PCF: stitched and smoothed
  curve. Output: one file.
- **C2. Apply** to the other measurements of the same day: one explicit line per
  calibration in the processing notebook.
- **C3. Reuse on another day**: copy the file into the current folder (lab practice),
  or name it from another folder. The data grid may differ (crop, recalibration).
- **C4. Regenerate**: re-run the notebook of C1; the decisions are in its cells.
- **C5. Check**: see what a calibration is (kind, axis, source, how it was made) and
  plot it, without opening the notebook that made it.
- **C6. Old files** (`_t0corr.npz`, `wl_corr.txt`, `_t0_curve.txt`, `pcf_final.npz`):
  phased out. Converted explicitly when needed (snippets in the docs, no functions).

## Decisions (2026-11-13)

1. **Calibrated wl axis for TA.** The wl calibration is applied right after reading a
   scan, before anything else, so t0 points are picked on the calibrated axis. Raw
   files are never rewritten. Application is always explicit (a function call or an
   argument), never automatic.
2. **A sampled curve `x, y`**, evaluated by interpolation. Model and coefficients may
   be stored for information (e.g. `[fit]`), never used to evaluate. They, and the
   points, make it easy to recompute t0 on another wavelength grid.
3. **Applied by value**, never by index, with an explicit out-of-range policy:
   `outside="error"|"constant"|"nan"`, default `"error"` (t0 outside the range is
   typically an error). No other check: within range, any grid is accepted. Each file
   records the axis of `x`: `wl` (calibrated), `wl_raw` (measured, TA) or `wl_u`
   (FLUPS upconverted).
4. **One file per calibration**, several per day when needed.
5. **toml.** Arrays round-trip exactly, NaN included (checked). Metadata reads back as
   standard types (str, float, list, date), easy to copy into output headers.
6. **Manual offsets stay manual**: the FLUPS Raman `t0_offset` and adjustments of
   fitted points are numbers in the notebook. Nothing in the file.
7. **Names**: `<date>_<kind>_<source>.toml`, with `source` chosen by the user, e.g.
   `250709_t0_s2027.toml`, `250709_wl_itos.toml`, `240619_t0_PBBO.toml`,
   `240619_pcf_dyes.toml`. The user passes the path.
8. **Missing calibrations**: no processing function needs one (already true). The
   notebook holds the file name as a parameter; `None` skips the step with a warning.
   `read_calibration` raises if a named file does not exist.
9. **Sidecar later**: a calibration is a flat dict (plus an optional `fit` table), so
   several can be gathered later under named tables of one file (`[t0]`, `[wl]`).
   Not now.

## File

```toml
kind = "t0"                  # t0 | wl | pcf (free text, not checked)
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
points = [[321.22, -0.33], ...]
```

## Plan

Each step ends with tests passing and a commit.

1. **`edyx.calib`**, plain functions on dicts:
   - `write_calibration(path, kind, axis, x, y, **meta)`: numpy values in `meta` are
     converted to standard types;
   - `read_calibration(path)`: a dict, `x` and `y` as arrays, the rest standard types;
   - `interp_calibration(cal, x, outside="error")`: the curve at `x`, by value;
     `"constant"` holds the end values, `"nan"` gives NaN outside.

   Tests: round trip (NaN, metadata, `fit` table), the three policies, an unsorted `x`.
2. **Examples**: the edyx TA and FLUPS notebooks convert the shipped legacy files
   (`s2027_t0corr.npz`, `240619_PBBO_t0_curve.txt`, `240619_pcf_final.npz`) with a
   short snippet, write them to `output/`, and read them back with `interp_calibration`.
   The checks against the lab outputs still pass. The README gets the conversion
   snippets (C6).
3. **ITOS, automated**: `tana.itos_calibration(wl, itos, ...)`: the same peak picking on
   the measured and reference spectra, pairing, linear fit. It returns what
   `write_calibration` needs, with the fit for information. The peak parameters are
   explicit (scientific). Peaks are paired in order; a different number of measured
   and reference peaks is an error (SP, 2026-11-13). Acceptance: reproduces `wl_corr.txt` of 250521, 250528 and
   250709.
4. **Docs**: README (making and applying calibrations, missing ones), and the TA
   design doc (`T0Curve` dropped: the fit stays in the notebook, which writes the file).

Not in this round: the sidecar (decision 9), changes to `pcf_correct` (pass it the
interpolated PCF, or keep its `left`/`right`).
