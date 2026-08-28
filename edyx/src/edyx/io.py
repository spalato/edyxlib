import numpy as np


def unpack_trace(data):
    """
    Extract axes and data from a packed data matrix.

    Returns
    -------
    t     (M,) np.ndarray
    wl    (N,) np.ndarray
    trace (M, N) np.ndarray
    """
    wl = data[1:,0]
    t = data[0,1:]
    trace = data[1:,1:]
    return t, wl, trace


def pack_trace(t, wl, trace):
    """
    Pack axes and trace as a single array.

    Parameters
    ----------
    t : (M,) np.ndarray
        Times arrays
    wl : (N,) np.ndarray
        Wavelength arrays
    trace : (M,N) np.ndarray
        Intensity trace
    """
    packed = np.empty([i+1 for i in trace.shape])
    packed.fill(np.nan)
    packed[1:,1:] = trace
    packed[1:,0] = wl
    packed[0, 1:] = t
    return packed