import numpy as np
import re
import logging

logger = logging.getLogger(__name__)


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


# TODO: read_ta_stack

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
    delays : (M,) np.ndarray
        Delays, fs. Starts from 0.
    wl : (N,) np.ndarray
        Wavelengths, nm.
    trace : (M,N) np.ndarray
        Signal intensity
    """
    # read the data
    # TODO: ensure it can read files obtained both with and without the spectrograph.
    nfiles = len(fnames)
    logger.debug(f"nfiles: {nfiles}")
    fnames = iter(fnames)
    first = read_asc(next(fnames))
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
        step = float(re.search(r"_s(\d+)_", fnames[0]).group(1))
        delays = np.arange(0, trace.shape[0])*step
    else:
        try:
            step = float(step)
        except ValueError:
            raise ValueError("step argument not understood. Must be a float, convertible to a float, or in "
                             "{'first', 'filename'}.")
        delays = np.arange(0, trace.shape[0]) * step
    if delays[1]<delays[0]:
        delays = delays[::-1]
        trace = trace[::-1,:]
    assert trace.shape == (delays.size, wl.size)
    return delays, wl, trace


def load_npz(fname):
    """
    Load data from an npz archive.

    Parameters
    ----------
    fname : str
        Path to the archive.

    Returns
    -------
    delays : (M,) np.ndarray
        Delays, fs. Starts from 0.
    wl : (N,) np.ndarray
        Wavelengths, nm.
    trace : (M,N) np.ndarray
        Signal intensity
    """
    df = np.load(fname)
    delays = df["delays"]
    trace = df["trace"]
    wl = df["wl"]
    return delays, wl, trace


def load_txt(fname):
    """
    Load data from a ".txt" file.

    The first element is discarded (ie: top left corner), the first column 
    contains the delays, the first row contains the wavelength, and the rest 
    contains the signal intensity.

    Parameters
    ----------
    fname : str
        Path to the archive.

    Returns
    -------
    delays : (M,) np.ndarray
        Delays, fs. Starts from 0.
    wl : (N,) np.ndarray
        Wavelengths, nm.
    trace : (M,N) np.ndarray
        Signal intensity
    """
    cnt = np.loadtxt(fname)
    delays = cnt[1:,0]
    wl = cnt[0,1:]
    trace = cnt[1:,1:]
    return delays, wl, trace


def save_txt(fname, delays, wl, trace):
    """
    Saves the data in a `.txt` file.

    The first element is undefined, the first column contains the delays, the 
    first row contains the wavelengths and the rest contains the signal
    intensity.

    Parameters
    ----------
    fname : str
        Path to the archive.
    delays : (M,) np.ndarray
        Delays, fs. Starts from 0.
    wl : (N,) np.ndarray
        Wavelengths, nm.
    trace : (M,N) np.ndarray
        Signal intensity

    See also
    --------
    edyx.io.load_txt
    """
    cnt = np.full([s+1 for s in trace.shape], np.nan)
    cnt[1:,0] = delays
    cnt[0,1:] = wl
    cnt[1:,1:] = trace
    np.savetxt(fname, cnt, fmt="%.06g")
