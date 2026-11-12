"""Plotting helpers."""
from math import ceil

import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter

try:
    import colorcet as cc
    flups_default_cmap = cc.cm.CET_L17
except ImportError:
    flups_default_cmap = "inferno"


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
    opts = {"shading": "auto", **defaults, **kwargs}

    fig, axes = plt.subplots(
        nrows, ncols, sharex=True, sharey=True, squeeze=False,
        layout="constrained", figsize=(4 * ncols, 3 * nrows),
    )
    for i, (ax, m) in enumerate(zip(axes.flat, maps)):
        mesh = ax.pcolormesh(t, wl, m, **opts)
        if titles is not None:
            ax.text(0.95, 0.95, titles[i], transform=ax.transAxes,
                    va="top", ha="right")
        if i + ncols >= n:  # lowest map in its column
            ax.set_xlabel("delay / ps")
    for ax in axes.flat[n:]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$\lambda$ / nm")
    fig.colorbar(mesh, ax=list(axes.flat[:n]))
    return fig, axes


def plot_flups(t, wl, z,
               vmin=0, vmax=None, cmap=flups_default_cmap,
               levels=None, scatter_mask = None, filter=[3,1], lev_colors=None,
               ax=None):
    assert z.shape == (wl.size, t.size)
    ax = plt.gca() if ax is None else ax
    vmax = np.percentile(z, 99) if vmax is None else vmax
    scatter_mask = np.full_like(wl, True) if scatter_mask is None else scatter_mask
    art = []
    art.append(
        plt.pcolormesh(t, wl, z, vmin=vmin, vmax=vmax, cmap=cmap)
    )
    cb = plt.colorbar(label=r"$S_\mathrm{F}$")
    art.append(cb)
    if levels is None:
        # try to provide a default
        step = (vmax-vmin)/10
        levels = np.arange(0, 20)*step+vmin
    if len(levels)>0:
        if filter is not None and len(filter)>0:
            cnt = gaussian_filter(z, filter)
        else:
            cnt = z
        cnt = cnt.compress(scatter_mask, axis=0)
        wl_cnt = wl.compress(scatter_mask)
        if lev_colors is None:
            lev_colors = ["w"] * len(levels)
            lev_colors[0] = "0.85"
        lines = plt.contour(t, wl_cnt, cnt, levels=levels, colors=lev_colors, linewidths=0.5)
        cb.add_lines(lines)
        art.append(lines)
    return art

