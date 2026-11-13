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

| Tool | For | "Done" prints |
| --- | --- | --- |
| `Overlay` | comparing datasets: spectra at a delay, or kinetics at a wavelength | nothing |
| `ScanInspector` | rejecting scan data (TA, FLUPS stacks), optional RMSD threshold | `rejections`, `threshold` |
| `T0Picker` | clicking t0 points on kinetic traces | `t0_points` |
| `Linear` | linear spectra: browse repetitions, RMSD threshold, mean spectra | `threshold` |

`Linear` applies its thresholds (default: mean + 3.5 std of the RMSD) to all files
at once; set a large value to reject nothing. Pass the "Done" output back with
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

Decisions live in the notebook. Each tool prints its decisions as a Python literal
on "Done". Paste it into the cell before the tool, and pass it back in:

```python
# pasted from "Done"
rejections = [(4, None, (221, 222)), (None, None, (253, None))]
threshold = None

insp = ScanInspector(t, wl, stack, rejections=rejections)
insp.show()
```

The data step uses the literal, not the widget, so "Run all" gives the same result:

```python
data = np.ma.masked_array(stack, mask=rejection_mask(stack.shape, rejections))
```

A rejection is `(file, wl, t)`. Each entry is `None` (all), an index, or a
`(start, stop)` range, stop excluded, as in a slice. Indices refer to the axes the
tool was given: apply the mask to data on the same axes (not after a crop or a
clipped shift).

Each edit is logged at INFO level. To see the trail in the cell output:

```python
import logging; logging.basicConfig(level=logging.INFO)
```

## Examples

`examples/` holds notebooks on the `edyx` example data (`../edyx/examples/data`). They are
templates to start from: copy one into the day folder and set `data_dir = Path(".")`.

- TA (250709), in `examples/TA/`, run in this order:
  1. `ta_1_linear_itos`: linear spectra (`Linear`), ITOS wavelength calibration, spectra
     saved on the calibrated axis.
  2. `ta_2_processing`: scans on the calibrated axis, comparison (`Overlay`), rejection
     (`ScanInspector`), average, t0 points (`T0Picker`), t0 fit and calibration file,
     shift, save.
- FLUPS (240619): `flups_compare`, comparisons with `Overlay`.

## Known limits

- RMSD against the median of the files: with 2 files the median is the mean, so
  both files get the same RMSD. The threshold cannot single out one file.
- Literals with file indices (`rejections`, per-file `threshold`) assume the same
  file order on re-run: use `sorted(glob(...))`, not a bare `glob`.

## Legacy imports

Old notebooks keep working: `pyspan.io`, `pyspan.utils`, `pyspan.itos` and
`pyspan.inspect` re-export the functions that now live in `edyx` and emit a
`FutureWarning` naming the new import. `from pyspan import Linear` is unchanged.
