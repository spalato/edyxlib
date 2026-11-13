"""Calibration files: a sampled curve `x, y` and its metadata, in toml.

A calibration (t0 curve, wavelength calibration, PCF) is made by a notebook from a
reference measurement and applied explicitly, by value, in the processing notebooks.
The file holds the curve and plain metadata; how it was made stays in the notebook.

Example::

    write_calibration("250709_t0_s2027.toml", "t0", "wl", wl, t0,
                      units=["nm", "ps"], source="s20-s27", made_by="ta_s2027.ipynb")
    cal = read_calibration("250709_t0_s2027.toml")
    t0 = interp_calibration(cal, wl)
"""
import tomllib
from pathlib import Path

import numpy as np
import toml

OUTSIDE = ("error", "constant", "nan")


def _plain(value):
    """Convert numpy values (also inside dicts and lists) to standard types."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def write_calibration(path, kind, axis, x, y, **meta):
    """
    Write a calibration curve and its metadata to a toml file.

    Parameters
    ----------
    path : str or Path
        Output file, e.g. `<date>_<kind>_<source>.toml`. Overwritten if present.
    kind : str
        What the curve is: "t0", "wl", "pcf", ... (free text, not checked).
    axis : str
        Axis of `x`: "wl" (calibrated), "wl_raw" (TA measured), "wl_u" (FLUPS
        upconverted), ... (free text, not checked).
    x, y : (N,) array-like
        The sampled curve. NaN is allowed in `y`.
    **meta
        Other entries: `units`, `date`, `source`, `made_by`, `notes`, ... A dict
        becomes a table, e.g. `fit={"model": ..., "coef": ..., "points": ...}`
        (for information only). Numpy values are converted to standard types.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.ndim != 1 or x.shape != y.shape:
        raise ValueError(f"x and y must be 1D of the same length, got {x.shape} and {y.shape}")
    cal = {"kind": kind, "axis": axis, **meta, "x": x, "y": y}
    Path(path).write_text(toml.dumps(_plain(cal)))


def read_calibration(path):
    """
    Read a calibration file written by `write_calibration`.

    Returns
    -------
    dict
        `x` and `y` as float arrays; the other entries as read (str, float, list,
        date, dict for tables).
    """
    with open(path, "rb") as f:
        cal = tomllib.load(f)
    cal["x"] = np.asarray(cal["x"], dtype=float)
    cal["y"] = np.asarray(cal["y"], dtype=float)
    return cal


def interp_calibration(cal, x, outside="error"):
    """
    Evaluate a calibration curve at `x`, by linear interpolation.

    Parameters
    ----------
    cal : dict
        From `read_calibration` (needs `x` and `y`).
    x : array-like
        Where to evaluate, on the axis of `cal["x"]` (see `cal["axis"]`).
    outside : "error", "constant" or "nan"
        Values of `x` outside the range of `cal["x"]`: raise a ValueError, hold the
        end values, or give NaN.

    Returns
    -------
    np.ndarray
        Same shape as `x`.
    """
    if outside not in OUTSIDE:
        raise ValueError(f"outside must be one of {OUTSIDE}, got {outside!r}")
    cx = np.asarray(cal["x"], dtype=float)
    cy = np.asarray(cal["y"], dtype=float)
    order = np.argsort(cx)
    cx, cy = cx[order], cy[order]
    x = np.asarray(x, dtype=float)
    out = (x < cx[0]) | (x > cx[-1])
    if outside == "error" and np.any(out):
        raise ValueError(
            f"{np.count_nonzero(out)} value(s) of x outside the calibration range "
            f"[{cx[0]:g}, {cx[-1]:g}] ({x.min():g} to {x.max():g}); "
            "pass outside='constant' or 'nan' to accept them"
        )
    y = np.interp(x, cx, cy)
    if outside == "nan":
        y = np.where(out, np.nan, y)
    return np.asarray(y)
