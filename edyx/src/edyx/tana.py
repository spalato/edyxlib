# itos: wavelength calibration using ITOS filter.
import os.path as pth
import numpy as np
from scipy.integrate import simpson
from edyx.io import FILE_AXIS, TIME_AXIS
from edyx.utils import between


__REF_FNAME = pth.join(pth.dirname(__file__), "itos_190319b_varian.dat")


def load_itos_spectrum(fname = __REF_FNAME):
    """
    Load the absorbance spectrum of ITOS for use as a reference.

    The spectrum is in mOD vs wavelength. Wavelengths are in increasing order.

    Parameters
    ----------
    fname : string, path-like
        The filename with the reference spectrum.

    Returns
    -------
    wl :  (N,) np.ndarray
        Wavelength axis, in ascending nm.
    spectrum : (N,) np.ndarray
        Absorbance spectrum, in mOD.
    """
    wl, spectrum = np.loadtxt(fname, skiprows=1)[::-1, :].T
    spectrum *= 1000 # to mOD
    return wl, spectrum

# ══════════════════════════  BAND INTEGRALS  ═══════════════════════════════

def band_integral(wl, da, bounds):  
    """Compute band integral weighted by 1/λ.

    Computes the band integral I of signal DA over interval λ₁, λ₂,
    exclusive of bounds.

    I = 1/ln(λ₂/λ₁) Int_λ₁^λ₂ ΔA dλ/λ
    Also works with frequency instead of wavelength.

    Parameters
    ----------
    wl : (N,) ndarray
        Spectral axis
    da : (N, M) ndarray
        TA signal.
    bounds: (λ₁, λ₂) 2-tuple
        Bounds of the integral.

    Returns
    -------
    I : (M,) np.ndarray
        Band integral.

    Notes
    -----
    Currently sums over first axis (should be last for better efficiency).
    """
    AXIS = 0
    to_keep = between(wl, *bounds)
    wl_c = wl.compress(to_keep)
    z_c = da.compress(to_keep, axis=AXIS)
    itr = simpson(z_c / wl_c[:, np.newaxis], x=wl_c, axis=AXIS)
    return itr / np.log(bounds[1] / bounds[0])


def band_average(wl, z, bounds):
    """Compute integral over a wl band, without weighting.

    I = 1/(λ₂-λ₁) Int_λ₁^λ₂ ΔA dλ

    Parameters
    ----------
    wl : (N,) ndarray
        Spectral axis
    z : (N, M) ndarray
        TA signal.
    bounds: (lo, hi) 2-tuple
        Bounds of the integral.

    Returns
    -------
    I : (M,) np.ndarray
        Band average.

    Currently sums over first axis (should be last for better efficiency).
    """
    AXIS = 0
    to_keep = between(wl, *bounds)
    wl_c = wl.compress(to_keep)
    z_c = z.compress(to_keep, axis=AXIS)
    itr = simpson(z_c, x=wl_c, axis=AXIS)
    return itr / (bounds[1] - bounds[0])


# ══════════════════════════  TRACE PROCESSING  ═════════════════════════════

def shift_trace(t, s, t0, edges="clip"):
    """Time-zero correction of a trace, one shift per wavelength.

    A feature at delay ``t0[i]`` in row ``i`` is moved to delay 0, by linear
    interpolation: ``out[i] = interp(t + t0[i], t, s[i])``.

    Parameters
    ----------
    t : (T,) ndarray
        Delay axis, ascending.
    s : (W, T) ndarray or masked array
        Trace.
    t0 : (W,) ndarray
        Time-zero for each wavelength. How the curve is evaluated is up to
        the caller, e.g. ``t0 = np.polyval(p, nm2ev(wl))`` (see
        `edyx.units.nm2ev`).
    edges : {"clip", "nan"}
        "clip": keep only the delays valid for every wavelength (computed
        from `t0` alone). "nan": keep the full `t`, with NaN (masked) outside
        the measured range.

    Returns
    -------
    t : (T',) ndarray
        Shifted delay axis (T' = T for ``edges="nan"``).
    out : (W, T') ndarray or masked array
        Shifted trace. Masked in gives masked out (masked points and
        out-of-range points are masked); plain in gives plain out (NaN).
    """
    if edges not in ("clip", "nan"):
        raise ValueError(f"edges must be 'clip' or 'nan', got {edges!r}")
    t = np.asarray(t)
    t0 = np.asarray(t0)
    if s.shape != (t0.size, t.size):
        raise ValueError(f"s has shape {s.shape}, expected {(t0.size, t.size)}")
    masked = np.ma.isMaskedArray(s)
    data = np.ma.filled(np.ma.asarray(s, dtype=float), np.nan) if masked else s
    out = np.empty(s.shape, dtype=float)
    for i in range(s.shape[0]):
        out[i] = np.interp(t + t0[i], t, data[i], left=np.nan, right=np.nan)
    if masked:
        out = np.ma.masked_invalid(out)
    if edges == "nan":
        return t, out
    keep = (t + t0.min() >= t[0]) & (t + t0.max() <= t[-1])
    return t[keep], out[:, keep]


def crop(t, wl, s, t_lim=None, wl_lim=None):
    """Keep delays and wavelengths within inclusive limits.

    Parameters
    ----------
    t : (T,) ndarray
        Delay axis.
    wl : (W,) ndarray
        Wavelength axis.
    s : (..., W, T) ndarray or masked array
        Trace or stack.
    t_lim, wl_lim : (lo, hi) or None
        Inclusive limits. None: no crop on that axis.

    Returns
    -------
    t, wl, s
        Cropped axes and data (masks kept).
    """
    if t_lim is not None:
        keep = (t_lim[0] <= t) & (t <= t_lim[1])
        t, s = t[keep], s[..., keep]
    if wl_lim is not None:
        keep = (wl_lim[0] <= wl) & (wl <= wl_lim[1])
        wl, s = wl[keep], s[..., keep, :]
    return t, wl, s


def subtract_pre_t0(t, s, t_max):
    """Subtract the mean signal before time zero, per wavelength.

    Parameters
    ----------
    t : (T,) ndarray
        Delay axis.
    s : (..., W, T) ndarray or masked array
        Trace or stack (one mean per file and wavelength).
    t_max : float
        Delays ``t < t_max`` (strict) are averaged.

    Returns
    -------
    (..., W, T) ndarray or masked array
        Corrected data. Masked points are ignored in the mean; plain in gives
        plain out.
    """
    mean = np.ma.mean if np.ma.isMaskedArray(s) else np.mean
    return s - mean(s[..., t < t_max], axis=TIME_AXIS, keepdims=True)


def avg_scans(stack):
    """Average a stack (F, W, T) over files; masked points are ignored.

    Returns a (W, T) masked array.
    """
    return np.ma.mean(stack, axis=FILE_AXIS)


def avg_spectra(s):
    """Mean spectrum over delays, (..., W, T) -> (..., W); masked points ignored."""
    return np.ma.mean(s, axis=TIME_AXIS)
