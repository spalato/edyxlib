"""Plotting helpers."""
from math import ceil

import matplotlib.pyplot as plt
import numpy as np


def plot_maps(t, wl, maps, titles=None, ncols=2, diverging=True, **kwargs):
    r"""Plot several (wavelength x delay) maps on a grid with one shared scale.

    Parameters
    ----------
    t : array, shape (T,)
        Delays.
    wl : array, shape (W,)
        Wavelengths.
    maps : sequence of arrays (W, T), or array (F, W, T)
        Maps to plot. Masked arrays and NaN are supported.
    titles : sequence of str, optional
        Text placed in the top-right corner of each axes.
    ncols : int, default 2
        Number of columns (reduced to the number of maps if smaller).
    diverging : bool, default True
        True for signed data (symmetric limits from the 99th percentile of
        ``|maps|``, "coolwarm"). False for positive data (1st to 99th
        percentile, "Blues").
    **kwargs
        Passed to `pcolormesh`. ``vmin``, ``vmax`` and ``cmap`` override the
        defaults.

    Returns
    -------
    fig : Figure
    axes : ndarray of Axes, shape (nrows, ncols)

    Examples
    --------
    Compare a despike result. The difference may need its own scale: call
    twice, or pass ``vmin``/``vmax``.

    >>> plot_maps(t, wl, [raw, filtered, raw - filtered],
    ...           titles=["raw", "filtered", "removed"], ncols=3)
    """
    maps = [np.ma.masked_invalid(m) for m in maps]
    n = len(maps)
    ncols = min(ncols, n)
    nrows = ceil(n / ncols)
    values = np.concatenate([m.compressed() for m in maps])
    if diverging:
        vmax = np.percentile(np.abs(values), 99)
        defaults = dict(vmin=-vmax, vmax=vmax, cmap="coolwarm")
    else:
        vmin, vmax = np.percentile(values, [1, 99])
        defaults = dict(vmin=vmin, vmax=vmax, cmap="Blues")
    opts = dict(shading="auto", **defaults)
    opts.update(kwargs)

    fig, axes = plt.subplots(
        nrows, ncols, sharex=True, sharey=True, squeeze=False,
        layout="constrained", figsize=(4 * ncols, 3 * nrows),
    )
    for i, ax in enumerate(axes.flat):
        if i >= n:
            ax.set_visible(False)
            continue
        mesh = ax.pcolormesh(t, wl, maps[i], **opts)
        if titles is not None:
            ax.text(0.95, 0.95, titles[i], transform=ax.transAxes,
                    va="top", ha="right")
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$\lambda$ / nm")
    for j in range(ncols):
        visible = [ax for ax in axes[:, j] if ax.get_visible()]
        visible[-1].set_xlabel("delay / ps")
    fig.colorbar(mesh, ax=list(axes.flat[:n]))
    return fig, axes
