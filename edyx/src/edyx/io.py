import numpy as np
from itertools import dropwhile
import re
import logging

logger = logging.getLogger(__name__)

# Axes of a trace (W, T) or a stack of traces (F, W, T). Negative, so they work for both.
# FILE_AXIS = -3 raises on a 2D trace instead of silently averaging the wrong axis.
FILE_AXIS = -3
WL_AXIS = -2
TIME_AXIS = -1


def unpack_trace(data):
    """
    Extract axes and data from a packed data matrix.

    Returns
    -------
    t     (T,) np.ndarray
    wl    (W,) np.ndarray
    trace (W, T) np.ndarray
        Rows are wavelengths.
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
    t : (T,) np.ndarray
        Times arrays
    wl : (W,) np.ndarray
        Wavelength arrays
    trace : (W, T) np.ndarray
        Intensity trace. Rows are wavelengths.
    """
    packed = np.empty([i+1 for i in trace.shape])
    packed.fill(np.nan)
    packed[1:,1:] = trace
    packed[1:,0] = wl
    packed[0, 1:] = t
    return packed


def write_ta_dat(fname, t, wl, s, header="", fmt="%.6e"):
    """
    Write a TA `.dat` file: the inverse of `read_ta_dat`.

    Masked points are written as NaN. Header lines are written as `#` comments
    (`np.loadtxt` skips them).

    Parameters
    ----------
    fname : str, path-like
        Output file.
    t : (T,) np.ndarray
        Delays.
    wl : (W,) np.ndarray
        Wavelengths.
    s : (W, T) np.ndarray
        Signal. Rows are wavelengths.
    header : str, optional
        Header text, written as `#` comment lines.
    fmt : str, optional
        Format of each number.
    """
    filled = np.ma.filled(np.ma.asarray(s, dtype=float), np.nan)
    np.savetxt(fname, pack_trace(t, wl, filled), fmt=fmt, header=header)


def stack_traces(traces):
    """
    Stack traces sharing the same axes.

    Parameters
    ----------
    traces : iterable of (t, wl, s)
        Traces from any reader. Masks are kept if any `s` is a masked array.

    Returns
    -------
    t : (T,) np.ndarray
    wl : (W,) np.ndarray
    stack : (F, W, T) np.ndarray
        One trace per file.

    Raises
    ------
    ValueError
        If the delays or wavelengths differ between traces.

    Examples
    --------
    >>> t, wl, stack = stack_traces(read_ta_dat(fn) for fn in sorted(glob("s*.dat")))
    """
    traces = list(traces)
    if not traces:
        raise ValueError("No traces to stack.")
    t, wl, _ = traces[0]
    for i, (ti, wli, _) in enumerate(traces):
        if np.shape(ti) != np.shape(t) or not np.allclose(ti, t):
            raise ValueError(f"Delays of trace {i} differ from the first trace.")
        if np.shape(wli) != np.shape(wl) or not np.allclose(wli, wl):
            raise ValueError(f"Wavelengths of trace {i} differ from the first trace.")
    ss = [s for _, _, s in traces]
    if any(np.ma.isMaskedArray(s) for s in ss):
        return t, wl, np.ma.stack(ss)
    return t, wl, np.array(ss)

def read_ta_dat(fname, sort_t=True):
    "Read a `.dat` file TA measurement from OMAFEMTO."
    dat = np.loadtxt(fname)
    t = dat[0,1:]
    wl = dat[1:,0]
    z = dat[1:,1:]
    if sort_t:
        # This is overkill. We should just reverse
        srt_idx = np.argsort(t)
        t = t[srt_idx]
        z = z[:,srt_idx]
    return t, wl, z


def read_ab_dat(fname):
    "Read a `.dat` file absorption spectrum from OMAFEMTO"
    dat = np.loadtxt(fname)
    wl = dat[1:,0]
    z = dat[1:,1:]
    return wl, z


def read_ab_stack(fnames):
    """Read multiple `.dat` file absorption spectra from OMAFEMTO.

    Checks the wavelengths the same in all files.
    """
    dat = [read_ab_dat(fn) for fn in fnames]
    all_wl = np.array([d[0] for d in dat])
    assert np.allclose(all_wl[0], all_wl) # fails if they have different wl
    wl = all_wl[0]
    od = np.array([d[1] for d in dat])
    return wl, od


# TODO: add a function to correct the data (intensity correction)
# TODO: make sure it's easy to save the corrected data. (Make function, make CLI)
def read_cary_uv(fname):
    """Read spectra from Cary in csv format.

    Parameters
    ----------
    fname : str
        Input file name

    Returns
    -------
    header : list of list
        Header lines, currently unprocessed
    data : (N, M) np.ndarray
        Data with N rows and M columns. N is the number of wavelength values, and there are M/2 measurements.
    """
    N_HEADER_LINES = 2
    # open file, find the end of the data record.
    with open(fname, "r") as f:
        data = f.read()
    end = data.find("\n\n") # double newline indicate end of data and start of metadata.
    data = data[:end].splitlines()
    header = data[:N_HEADER_LINES]
    data = data[N_HEADER_LINES:]
    data = np.loadtxt(
        (ln.rstrip(", \t") # strip those characters from the end: comma, space, tab
         for ln in data),
        delimiter = ","
    )
    return header, data


def read_asc(fname):
    """
    Read a single `asc` file, the ASCII format from Andor Solis.

    Parameters
    ----------
    fname : str, path-like
        File to open.

    """

    logger.debug("Loading `.asc` file: %s", fname)
    with open(fname) as f:
        contents = f.read()
    meta_start = contents.find("Date and Time")
    logger.debug("  Metadata at %i", meta_start)
    if meta_start == 0:
        start = contents.find("\n"*3)
        end = None
    else:
        start = None
        end = contents.find("\n"*3)

    # def __fixup(line): # Uncomment in case of emergency...
    #     """huh.. The wavelength is saved using , as decimal separator, while the value uses `.`"""
    #     if line.count(",") > 1:
    #         line = line.replace(",", ".", 1)
    #     return line
    # return np.loadtxt((__fixup(ln) for ln in contents[start:end].splitlines() if ln), delimiter=",")
    return np.loadtxt((ln for ln in contents[start:end].splitlines() if ln), delimiter=",")


def _ascending_wl_t(delays, trace):
    """Legacy (T, W) trace to the standard: sorted delays, (W, T)."""
    order = np.argsort(delays, kind="stable")
    return delays[order], trace[order].T


def load_asc_series(fnames, step="first"):
    """
    Load a series of Andor Solis `asc` files. Computes the delays and wl.

    Parameters
    ----------
    fnames: iterable of filenames.
        The list of files to load.
    step: float, or str in {"first", "filename"}. Default: "first".
        The timestep, in ps.
        If "first" (default), the position is read from the first pixel of each spectrum.
        If "filename", the timestep will be found from the filename as `_sNNN_`.

    Returns
    -------
    delays : (T,) np.ndarray
        Delays, as read from the files (or computed from `step`). Ascending.
    wl : (W,) np.ndarray
        Wavelengths, nm.
    trace : (W, T) np.ndarray
        Signal intensity
    """
    # read the data
    # TODO: ensure it can read files obtained both with and without the spectrograph.
    nfiles = len(fnames)
    logger.debug(f"nfiles: {nfiles}")
    fnames = iter(fnames)
    first_name = next(fnames)
    first = read_asc(first_name)
    wl = first[:, 0]  # we are reading the first file twice, but whatever
    logger.debug(f"wl.size: {wl.size}")
    trace = [first[:,1]]
    for fn in fnames:
        trace.append(read_asc(fn)[:, 1])
    # TODO: change to proper error.
    assert np.allclose([t.size for t in trace], trace[0].size)  # check they all have the same length
    trace = np.array(trace)
    logger.debug(f"Trace shape: {trace.shape}")
    assert trace.shape == (nfiles, wl.size)
    # compute time axis
    # TODO: test these cases.
    if step == "first":
        delays = trace[:,0]
    elif step == "filename":
        step = float(re.search(r"_s(\d+)_", first_name).group(1))
        delays = np.arange(0, trace.shape[0])*step
    else:
        try:
            step = float(step)
        except ValueError:
            raise ValueError("step argument not understood. Must be a float, convertible to a float, or in "
                             "{'first', 'filename'}.")
        delays = np.arange(0, trace.shape[0]) * step
    assert trace.shape == (delays.size, wl.size)
    delays, trace = _ascending_wl_t(delays, trace)
    return delays, wl, trace


def load_npz(fname):
    """
    Load data from an npz archive.

    The file stores `delays`, `wl` and `trace` with `trace` as (T, W).

    Parameters
    ----------
    fname : str
        Path to the archive.

    Returns
    -------
    delays : (T,) np.ndarray
        Delays, as stored in the file. Ascending (reversed if stored descending).
    wl : (W,) np.ndarray
        Wavelengths, nm.
    trace : (W, T) np.ndarray
        Signal intensity
    """
    df = np.load(fname)
    delays = df["delays"]
    trace = df["trace"]
    wl = df["wl"]
    delays, trace = _ascending_wl_t(delays, trace)
    return delays, wl, trace


def load_txt(fname):
    """
    Load data from a legacy FLUPS ".txt" file.

    The first element is discarded (ie: top left corner), the first column 
    contains the delays, the first row contains the wavelength, and the rest 
    contains the signal intensity, as (T, W) in the file.

    Parameters
    ----------
    fname : str
        Path to the archive.

    Returns
    -------
    delays : (T,) np.ndarray
        Delays, as stored in the file. Ascending (reversed if stored descending).
    wl : (W,) np.ndarray
        Wavelengths, nm.
    trace : (W, T) np.ndarray
        Signal intensity
    """
    cnt = np.loadtxt(fname)
    delays = cnt[1:,0]
    wl = cnt[0,1:]
    trace = cnt[1:,1:]
    delays, trace = _ascending_wl_t(delays, trace)
    return delays, wl, trace


def save_txt(fname, delays, wl, trace):
    """
    Saves the data in a legacy FLUPS `.txt` file.

    The first element is undefined, the first column contains the delays, the 
    first row contains the wavelengths and the rest contains the signal
    intensity, written as (T, W). `trace` is given in the standard (W, T)
    orientation. See `write_ta_dat` for the standard writer.

    Parameters
    ----------
    fname : str
        Path to the archive.
    delays : (T,) np.ndarray
        Delays.
    wl : (W,) np.ndarray
        Wavelengths, nm.
    trace : (W, T) np.ndarray
        Signal intensity

    See also
    --------
    edyx.io.load_txt
    """
    # pack_trace with the axes swapped gives the (T, W) layout
    trace = np.ma.filled(np.ma.asarray(trace, dtype=float), np.nan).T  # masked -> NaN
    np.savetxt(fname, pack_trace(wl, delays, trace), fmt="%.06g")

# TODO: add support for Picoquant's phu files, via the phufile module.
def read_oceanview(fname):
    """Read spectra from saved using OceanView

    Parameters
    ----------
    fname: str
        File name

    Returns
    -------
    wl : np.ndarray
        Wavelength
    counts : np.ndarray
        Signal
    """
    with open(fname) as f:
        ln = next(
            dropwhile(
                lambda ln: "Pixels in Spectrum" not in ln, 
                f
            )
        ).strip().split(" ")
        npix = int(ln[-1])
        dat = np.loadtxt(dropwhile(lambda ln: "Begin Spectral Data" not in ln, f), skiprows=1)
        assert dat.shape[1] == 2 # not sure how multiple columns are handled
        return dat[:,0], dat[:,1]
