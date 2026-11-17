# pyspan

Interactive tools (ipywidgets) for inspecting and processing `edyx` data. Reading,
processing, fitting and saving stay in `edyx`; `pyspan` only helps make decisions
(which points to reject, where t0 is) and returns them as plain data.

Works in JupyterLab and in VS Code notebooks, with `%matplotlib widget` (ipympl).

## Install

Into the shared `edyxenv` environment, editable, from a clone of the repo:

```powershell
uv pip install -e path/to/edyx -e path/to/pyspan
```

For development, from `pyspan/`: `uv sync`, `uv run pytest`, `uv run jupyter lab`.

## Tools

| Tool | For | `print_decisions()` prints |
| --- | --- | --- |
| `Overlay` | comparing datasets: spectra at a delay, or kinetics at a wavelength | nothing |
| `ScanInspector` | rejecting scan data (TA, FLUPS stacks), optional RMSD threshold | `rejections`, `threshold` |
| `T0Picker` | clicking t0 points on kinetic traces | `t0_points` |
| `Linear` | linear spectra: browse repetitions, RMSD threshold, mean spectra | `threshold` |

`Linear` applies its thresholds (default: mean + 3.5 std of the RMSD) to all files
at once; set a large value to reject nothing. Pass the printed `threshold` back with
`Linear.from_files(fnames, threshold=threshold)`.

Each tool is a small class: action methods (`set_value`, `reject_file`,
`add_point`, ...), plus `show()`, which returns the widget to display.

```python
%matplotlib widget
from pyspan import Overlay, ScanInspector, T0Picker
from pyspan.decisions import rejection_mask, rmsd_vs_median

Overlay({"before": (t, wl, s0), "after": (t2, wl2, s1)}, mode="kinetics").show()
```

- `Overlay`: each dataset keeps its own axes (a cropped or clipped dataset is
  fine); the slider runs over delay or wavelength values. A dataset that does not
  cover the current value is not drawn. "Autoscale" fits the y axis to the curves
  shown.
- `ScanInspector(t, wl, stack, labels, rejections=..., rmsd=..., threshold=...)`:
  kinetics of all files at one wavelength. Drag on the plot to select delays, then
  "Reject in file"; "Reject file" and "Reject wl row" need no selection. Turn off
  zoom/pan in the toolbar to select.
- `T0Picker(t, wl, s, points=..., step=10, tlim=(-1, 2))`: map and kinetic trace of
  the current wavelength, over the delays in `tlim`. Click on the trace to set the t0 of that wavelength (click again to
  move it). "Next after click" (or `auto_next=True`) steps to the next wavelength
  after each click. The fit is a separate notebook step, with the model you choose.

## Re-running without clicking

Decisions live in the notebook. `print_decisions()` prints a tool's decisions as a
Python literal. Call it in the cell after the tool, the one that uses the result, so
the printout always matches what was used. Paste it into the cell before the tool,
and pass it back in:

```python
# pasted from print_decisions()
rejections = [(4, None, (221, 222)), (None, None, (253, None))]
threshold = None
```

```python
insp = ScanInspector(t, wl, stack, rejections=rejections)
insp.show()
```

```python
insp.print_decisions()
data = insp.masked()
```

With no clicks, "Run all" gives the result recorded in the decisions cell. After
clicking, the result follows the clicks: paste the printout and re-run before saving.

A rejection is `(file, wl, t)`. Each entry is `None` (all), an index, or a
`(start, stop)` range, stop excluded, as in a slice. Indices refer to the axes the
tool was given: apply the mask to data on the same axes (not after a crop or a
clipped shift).

Each edit is logged at INFO level. To see the trail in the cell output:

```python
import logging; logging.basicConfig(level=logging.INFO)
```

## Examples

`examples/` holds notebooks on the `edyx` example data, one folder per day
(`../edyx/examples/250709`, `../edyx/examples/260605`). They are
templates to start from: copy one into the day folder and set `data_dir = Path(".")`.

- TA (250709), in `examples/TA/`, run in this order:
  1. `ta_1_linear_itos`: linear spectra (`Linear`), ITOS wavelength calibration, spectra
     saved on the calibrated axis.
  2. `ta_2_processing`: scans on the calibrated axis, comparison (`Overlay`), rejection
     (`ScanInspector`), average, t0 points (`T0Picker`), t0 fit and calibration file,
     shift, save.
- FLUPS (260605), in `examples/FLUPS/`, run in this order:
  1. `flups_1_t0`: t0 runs of one dye, despiked, checked (`Overlay`, `ScanInspector`),
     averaged; band fits, t0 curve, calibration file.
  2. `flups_2_pcf`: PCF runs per dye (`Linear`), means saved; with the fluorimeter
     references (`flups prep-fluo`): validity bounds, scales, smoothing, calibration file.
  3. `flups_3_processing`: measurement runs, despike, rejection (`ScanInspector`), average,
     t0 and PCF, saved on the fluorescence wavelength.

## Known limits

- RMSD against the median of the files: with 2 files the median is the mean, so
  both files get the same RMSD. The threshold cannot single out one file.
- Literals with file indices (`rejections`, per-file `threshold`) assume the same
  file order on re-run: use `sorted(glob(...))`, not a bare `glob`.

## Legacy imports

Old notebooks keep working: `pyspan.io`, `pyspan.utils`, `pyspan.itos` and
`pyspan.inspect` re-export the functions that now live in `edyx` and emit a
`FutureWarning` naming the new import. `from pyspan import Linear` is unchanged.
