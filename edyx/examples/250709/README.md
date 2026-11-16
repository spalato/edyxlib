# Example data: TA, 250709

Copies of lab data, unchanged, so the templates run anywhere (`pyspan/examples/TA`).

Xolography sample (UDMA matrix, DCPI, coinitiator, MEQ), TA magic angle, 200 fs steps.

- `s40.dat`, `s44.dat`: fresh forward scans.
- `s2027_t0corr.npz`: t0 curve measured on s20-s27 (`t0_corr` columns: wl, t0).
- `s00.dat`, `s01.dat`: linear spectra with repetitions (raw): ITOS filter, sample.

The lab's outputs, for checks:

- `s4044.dat`, `s4044_negdelay.dat`: the averaged, t0-corrected map (`ta_s4044.ipynb`).
- `s00_ITOS_ab_250709.dat`: ITOS filter spectrum (columns: measured wl, mOD).
- `s01_ab_250709.dat`: the sample spectrum, rewritten onto the calibrated axis by
  `ITOS_peak.ipynb`, for the check in `ta_1_linear_itos`.
- `250709_wl_corr.txt`: the wavelength calibration (`ITOS_peak.ipynb`; `wl_corr.txt` in
  the lab folder), for the check of `tana.itos_calibration`.
