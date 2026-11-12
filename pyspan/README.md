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
- `T0Picker(t, wl, s, points=..., step=10)`: map and kinetic trace of the current
  wavelength. Click on the trace to set the t0 of that wavelength (click again to
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

`examples/` holds notebooks on the `edyx` example data (`../edyx/examples/data`):
TA rejection and t0 review (250709), and FLUPS comparisons (240619).

## Known limits

- RMSD against the median of the files: with 2 files the median is the mean, so
  both files get the same RMSD. The threshold cannot single out one file.
- `Linear`: the default threshold is shown, but applied to a file only once its
  threshold is edited or the file is selected in the dropdown (legacy behaviour).
  The mask then depends on which files were looked at, and pasting "Done" back
  (`Linear.from_files(fnames, threshold=threshold)`, applied at once to all files)
  can differ from the session.
- Literals with file indices (`rejections`, per-file `threshold`) assume the same
  file order on re-run: use `sorted(glob(...))`, not a bare `glob`.

## Legacy imports

Old notebooks keep working: `pyspan.io`, `pyspan.utils`, `pyspan.itos` and
`pyspan.inspect` re-export the functions that now live in `edyx` and emit a
`FutureWarning` naming the new import. `from pyspan import Linear` is unchanged.
