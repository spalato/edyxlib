# edyx

TODO: explain what goes in this module: purpose, structure, etc.

## Calibration files

A calibration (TA t0 curve and ITOS wavelength calibration, FLUPS t0 curve and PCF) is a
sampled curve `x, y` with plain metadata, in a toml file (`edyx.calib`). The notebook of
the reference measurement writes it; the processing notebooks apply it, one explicit line
per calibration. One file per calibration, named `<date>_<kind>_<source>.toml`, e.g.
`250709_t0_s2027.toml`. Raw data files are never rewritten.

Make, in the notebook of the reference measurement:

```python
import datetime
from edyx.calib import write_calibration

write_calibration(
    "250709_t0_s2027.toml", "t0", "wl", wl, t0, units=["nm", "ps"],
    date=datetime.date(2025, 7, 9), source="s20-s27", made_by="ta_s2027.ipynb",
    fit={"model": "polynomial in eV, low order first", "coef": coef, "points": t0_points},
)
```

`axis` names the axis of `x`: `wl` (calibrated), `wl_raw` (TA measured) or `wl_u` (FLUPS
upconverted). `kind`, `axis` and the other entries are free text, not checked. The `fit`
table is for information only (to recompute the curve on another grid); it is never used
to evaluate.

Apply, by value:

```python
from edyx.calib import interp_calibration, read_calibration

t0 = interp_calibration(read_calibration(t0_file), wl)
```

`outside="error"` (default) raises if a value of `wl` is outside the range of the curve;
`"constant"` holds the end values, `"nan"` gives NaN. Within range any grid is accepted:
matching calibrations to data is the user's choice. For TA, apply the wavelength
calibration right after reading, so every later step uses the calibrated axis:
`wl = interp_calibration(read_calibration(wl_file), wl)`.

Missing calibration: no processing function needs one. Keep the file name as a notebook
parameter, and skip the step when it is `None`:

```python
if t0_file is None:
    warnings.warn("no t0 curve: delays not corrected")
    t0 = np.zeros_like(wl)
else:
    t0 = interp_calibration(read_calibration(t0_file), wl)
```

Check what a file holds:

```python
cal = read_calibration(path)
print({k: v for k, v in cal.items() if k not in ("x", "y")})
plt.plot(cal["x"], cal["y"])
```

### Old files

Convert once, explicitly, then use the toml file (examples: `examples/*.ipynb`).

```python
# TA t0 curve, <run>_t0corr.npz (applied by index before: now by value)
d = np.load("s2027_t0corr.npz")
write_calibration("250709_t0_s2027.toml", "t0", "wl_raw", *d["t0_corr"].T,
                  units=["nm", "ps"], date=datetime.date(2025, 7, 9), source="s20-s27",
                  fit={"model": "polynomial in eV, low order first",
                       "coef": d["pol_coeff"], "points": d["t0_meas"]})

# TA wavelength calibration, wl_corr.txt (columns: measured, calibrated)
wl_raw, wl_cal = np.loadtxt("wl_corr.txt").T
write_calibration("250709_wl_itos.toml", "wl", "wl_raw", wl_raw, wl_cal,
                  units=["nm", "nm"], date=datetime.date(2025, 7, 9), source="itos")

# FLUPS t0 curve, <dye>_t0_curve.txt (columns: wl_u, t0)
wl_u, t0 = np.loadtxt("240619_PBBO_t0_curve.txt").T
write_calibration("240619_t0_PBBO.toml", "t0", "wl_u", wl_u, t0,
                  units=["nm", "ps"], date=datetime.date(2024, 6, 19), source="PBBO")

# FLUPS PCF, pcf_final.npz (NaN outside the valid range: kept)
d = np.load("240619_pcf_final.npz")
write_calibration("240619_pcf_dyes.toml", "pcf", "wl_u", d["wl"], d["pcf"],
                  units=["nm", ""], date=datetime.date(2024, 6, 19), source="dyes")
```

The TA scans recorded so far are on the measured axis (`wl_raw`): the ITOS calibration
rewrote only the linear `*_ab_*` files. A t0 curve picked on those scans is on `wl_raw`.
