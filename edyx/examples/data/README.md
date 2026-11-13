# Example data

Copies of lab data, unchanged, so the example notebooks run anywhere.

## TA, 250709 

Xolography sample (UDMA matrix, DCPI, coinitiator, MEQ), TA magic angle, 200 fs steps.

- `s40.dat`, `s44.dat`: fresh forward scans.
- `s2027_t0corr.npz`: t0 curve measured on s20-s27 (`t0_corr` columns: wl, t0).
- `s4044.dat`, `s4044_negdelay.dat`: the lab's results (`ta_s4044.ipynb`), for the check.
- `s00.dat`, `s01.dat`: linear spectra with repetitions (raw): ITOS filter, sample.
- `s00_ITOS_ab_250709.dat`: ITOS filter spectrum (columns: measured wl, mOD).
- `s01_ab_250709.dat`: the lab's sample spectrum, rewritten onto the calibrated axis by
  `ITOS_peak.ipynb`, for the check of `pyspan/examples/ta_1_linear_itos`.
- `250709_wl_corr.txt`: the lab's wavelength calibration (`ITOS_peak.ipynb`; `wl_corr.txt`
  in the lab folder), for the check of `tana.itos_calibration`.

## FLUPS, 240619

ZsOMe in hexane. Legacy `.txt` files (delay x pixel).

- `240619_run05.txt`, `_run06`, `_run09`, `_run10`: the "early" scans of runs 05-12.
- `240619_PBBO_t0_curve.txt`: t0 curve measured on PBBO (columns: wl_u, t0).
- `240619_pcf_final.npz`: photometric correction function (`wl`, `pcf`).
- `240619_OMeZs_sig_U.txt`, `240619_OMeZs_sig_F.txt`: the lab's results
  (`run0512.ipynb`, then `240619_OMeZs.ipynb`), for the check.
