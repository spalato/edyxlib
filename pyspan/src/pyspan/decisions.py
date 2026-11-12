"""Plain functions for rejection decisions (no widgets).

Stacks have shape (F, W, T): files, wavelengths, delays. Linear spectra use the same
layout: (L files, M wavelengths, N repetitions).
"""
import sys

import numpy as np
from edyx.io import WL_AXIS


def _as_index(entry):
    """Convert one rejection entry (None, int or (start, stop)) to an index."""
    if entry is None:
        return slice(None)
    if isinstance(entry, tuple):
        return slice(*entry)
    return entry


def rejection_mask(shape, rejections):
    """Boolean mask of `shape` (F, W, T), True where rejected.

    Parameters
    ----------
    shape : tuple of int
        Shape (F, W, T) of the stack.
    rejections : list of tuple
        Entries `(file, wl, t)`. Each item is `None` (all), an int index, or a
        `(start, stop)` pair meaning `slice(start, stop)` (stop excluded, either
        may be None).

    Returns
    -------
    mask : (F, W, T) np.ndarray of bool
    """
    mask = np.zeros(shape, dtype=bool)
    for rej in rejections:
        if len(rej) != 3:
            raise ValueError(f"Rejection must be (file, wl, t), got: {rej!r}")
        mask[tuple(_as_index(r) for r in rej)] = True
    return mask


def rmsd_vs_median(data, axis):
    """Distance of every spectrum to the median spectrum.

    Called RMSD in the lab, but it is the Euclidean norm over wavelengths, as in
    the legacy code (no division by W), so thresholds typed in existing notebooks
    keep their meaning. Masks are ignored.

    Parameters
    ----------
    data : (F, W, T) array
        Stack of spectra.
    axis : int
        Axis of the median: 0 (median of the files, TA/FLUPS) or -1 (median of
        the repetitions, linear spectra).

    Returns
    -------
    rmsd : (F, T) np.ndarray
    """
    d = np.ma.getdata(data)
    med = np.median(d, axis=axis, keepdims=True)
    return np.sqrt(np.sum((d - med) ** 2, axis=WL_AXIS))


def above_threshold(rmsd, threshold):
    """Rejections for every spectrum whose rmsd exceeds the threshold.

    Parameters
    ----------
    rmsd : (F, T) np.ndarray
    threshold : float or (F,) array
        One threshold for all files, or one per file.

    Returns
    -------
    rejections : list of tuple
        Entries `(f, None, t)`, usable with `rejection_mask`.
    """
    rmsd = np.asarray(rmsd)
    thr = np.asarray(threshold)
    if thr.ndim == 1:
        thr = thr[:, np.newaxis]
    f, t = np.nonzero(rmsd > thr)
    return [(int(i), None, int(j)) for i, j in zip(f, t)]


def format_literal(name, value):
    """Text `name = <value>` that can be pasted in a cell and evaluated back.

    Evaluation needs `import numpy as np` in scope for arrays.
    """
    if isinstance(value, np.ndarray):
        txt = np.array2string(
            value, separator=", ", threshold=sys.maxsize, floatmode="unique",
            max_line_width=88, prefix="    ",
        )
        return f"{name} = np.array({txt})"
    return f"{name} = {value!r}"
