import numpy as np
from scipy.interpolate import UnivariateSpline, RectBivariateSpline
from scipy.optimize import brentq



def argnear(a, v):
    """Return index of value in `a` closest to `v`"""
    return np.argmin(np.abs(a-v))

def nearest(a, v):
    """Return value in `a` closest to `v`"""
    return a[argnear(a, v)]

def between(a, l, u):
    """Boolean mask for values in `a` larger than `l`, smaller than `u`"""
    return (a > l) & (a < u)

def band(a, v, w):
    """Boolean mask for values in `a` in a band centered at `v` of width `w`."""
    hw = w/2
    return between(a, v-hw, v+hw)

def regularize(x, upsample=1):
    """
    Make a new array similar to `x` with equispaced data.
    
    Optionally `upsample`s the grid.
    """
    if x.ndim != 1: raise ValueError("Built for 1d axis")
    return np.linspace(np.min(x), np.max(x), x.size * upsample)


def intrp2d_cmplx(x_org, y_org, z, x_new, y_new, **kwargs):
    """
    Interpolate 2 dimensional complex array `z` from `x_org`, `y_org` to `x_new`, `y_new`.

    This function assumes the initial axes are sorted, and suitable for 
    `RectBivariateSpline`. If that's not the case, see `regrid2d`.

    Parameters
    ----------
    x_org, y_org : np.array_like, 1D.
        original x, y axes. 1D arrays.
    z : array_like
        2D array of complex numbers with shape (x_org.size, y_org.size)
    x_new, y_new : np.array_like, 1D
        new x, y axes. 1D arrays.
    **kwargs : extra keyword arguments
        Passed to `scipy.interpolate.RectBivariateSpline`.

    See also
    --------
    `regrid2d`: Can take `x_org`, `y_org` in reversed order too.
    """
    re = RectBivariateSpline(x_org, y_org, z.real, **kwargs)
    im = RectBivariateSpline(x_org, y_org, z.imag, **kwargs)
    return re(x_new, y_new) + 1j * im(x_new, y_new)


def intrp2d_real(x, y, z, xg, yg):
    """
    Interpolate 2 dimensional array `z` from `x_org`, `y_org` to `x_new`, `y_new`.

    This function assumes the initial axes are sorted, and suitable for 
    `RectBivariateSpline`. If that's not the case, see `regrid2d`.

    Parameters
    ----------
    x_org, y_org : np.array_like, 1D.
        original x, y axes. 1D arrays.
    z : array_like
        2D array of real numbers with shape (x_org.size, y_org.size)
    x_new, y_new : np.array_like, 1D
        new x, y axes. 1D arrays.
    **kwargs : extra keyword arguments
        Passed to `scipy.interpolate.RectBivariateSpline`.

    See also
    --------
    `regrid2d`: Can take `x_org`, `y_org` in reversed order too.
    """
    intrp = RectBivariateSpline(x, y, z)
    return intrp(xg, yg)

def _prepare_axis(x):
    x = np.asarray(x)
    dx = np.diff(x)
    if np.all(dx > 0):
        idx = slice(None, None, 1)
    elif np.all(dx < 0):
        idx = slice(None, None, -1)
    else:
        # could implement using argsort
        raise ValueError("array must be monotonous.")
    return x[idx], idx


def regrid2d(x, y, z, upsample=1):
    """
    Interpolates `z` on an equispaced `x`, `y` grid with equidistant spacing.

    Optionally upsamples the grid.

    Parameters
    ----------
    x, y : 1D array-like
        x, y axes
    z : 2D array-like
        2D array of shape (x.size, y.size)
    upsample: int
        Upsampling factor.

    Returns
    -------
    x_reg, y_reg: 1D array-like
        New x, y axes, sorted, equispaced and upsampled.
    z_reg : 2D array-like
        values interpolated on the new grid.
    """
    x, x_idx = _prepare_axis(x.copy())
    y, y_idx = _prepare_axis(y.copy())
    z = z.copy()[x_idx, y_idx]
    x_reg = regularize(x, upsample)
    y_reg = regularize(y, upsample)
    if np.iscomplexobj(z):
        intrp = intrp2d_cmplx
    else:
        intrp = intrp2d_real
    return x_reg, y_reg, intrp(x, y, z, x_reg, y_reg)


def rescale(x):
    """Divide by max absolute value. Non finite values are ignored."""
    return x / np.max(np.abs(x), initial=0, where=np.isfinite(x))


def extrema(x):
    """Return the max or min of x, whichever has the largest absolute value."""
    amax = np.max(np.abs(x))
    max_ = np.max(x)
    return max_ if max_ == amax else np.min(x)


def sparkline(x):
    """Shift and scale data to the 0-1 range."""
    return rescale(x-np.min(x))


def brent_fwhm(x, amp, shift=True):
    """Obtain FWHM using brent's method to find half max crossings.

    This algoritms works by scaling the data by its max amplitude, then finding
    the points where: 0 = y_s - 0.5. By default, it shifts and scale the data 
    to the [0, 1] interval. The minimum value can be left unchanged if 
    `shift=False`.

    This will not behave well if more than two halfmax crossings are present:
    two of them will be arbitarily selected.

    Parameters
    ----------
    x : (N,) np.ndarray
        Independant variable, in ascending order
    amp : (N,) np.ndarray
        Dependant variable
    shift : bool, default True
        Shift minimum to 0.

    Returns
    -------
    fwhm : float
        Full width at half maximum
    (x1, x2) : (float, float)
        Half max crossing positions.

    See also
    --------
    `largest_fwhm`, `brent_fwtm`.
    """
    assert np.all(np.diff(x) > 0)
    if shift:
        amp = amp - np.min(amp)
    amp = amp/np.max(amp)
    ampf = UnivariateSpline(x, amp-0.5, k=1, s=0)
    t_max = x[np.argmax(amp)]
    x1 = brentq(ampf, x[0], t_max)
    x2 = brentq(ampf, t_max, x[-1])
    return x2-x1, (x1, x2)


def largest_fwhm(x, y):
    """Obtain FWHM using brent's method to find half max crossings.

    This algoritms works by scaling the data by its max amplitude, then finding
    the points where: 0 = y_s - 0.5. By default, it shifts and scale the data 
    to the [0, 1] interval. The minimum value can be left unchanged if 
    `shift=False`.

    If more than two half-max crossings are present, this version attempts t
    find the largest value.

    Parameters
    ----------
    x : (N,) np.ndarray
        Independant variable, in ascending order
    y : (N,) np.ndarray
        Dependant variable
    shift : bool, default True
        Shift minimum to 0.

    Returns
    -------
    fwhm : float
        Full width at half maximum
    (x1, x2) : (float, float)
        Half max crossing positions.

    See also
    --------
    `brent_fwhm`, `brent_fwtm`.
    """
    y = y.copy()
    y -= np.min(y)
    y /= np.max(y)
    g1 = x[np.argmax(y > 0.5)]
    g2 = x[::-1][np.argmax(y[::-1] > 0.5)]
    yf = UnivariateSpline(x, y-0.5, k=1, s=0)
    x1 = brentq(yf, x[0], g1)
    x2 = brentq(yf, g2, x[-1])
    return x2-x1, (x1, x2)


def brent_fwtm(t, amp):
    """Obtain FWHM using brent's method to find 1/10 max crossings.

    This will not behave well if more than two crossings are present.
    """
    amp = amp - np.min(amp)
    amp /= np.max(amp)
    ampf = UnivariateSpline(t, amp-0.1, k=1, s=0)
    t_max = t[np.argmax(amp)]
    x1 = brentq(ampf, t[0], t_max)
    x2 = brentq(ampf, t_max, t[-1])
    return x2-x1, (x1, x2)
