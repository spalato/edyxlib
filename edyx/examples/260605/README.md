# Example data: FLUPS, 260605

Copies of lab data, for the FLUPS templates (`pyspan/examples/FLUPS`). The runs are
collected with `flups collect-asc` (the raw `.asc` are not copied), the references
made with `flups prep-fluo`. To be replaced by a better day.

- `260605_run01.dat`, `_run02`: t0 runs on PBBO (251 delays, -1.5 to 3.5 ps), for
  `flups_1_t0`.
- `260605_run03.dat`, `_run04`: measurement runs (401 delays, -1.5 to 6.5 ps), for
  `flups_3_processing`.
- `PCF/<dye>/260605_PCF_<dye>_runNN.dat`: PCF runs, 10 frames at a fixed delay, for
  `flups_2_pcf`. C153 and C6H: 3 runs; PBBO: 9 runs, 1-5 are trials (other delays, or
  frames of zeros).
- `Fluo/*.csv`: fluorimeter exports (Cary Eclipse), raw, with a trial replica in each.
- `PCF/260605_*_corr.dat`: the references from `Fluo/`, made by `flups prep-fluo`
  (columns: wl_f, intensity; the header lists the replicas used and excluded).
