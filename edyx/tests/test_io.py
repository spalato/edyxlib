import numpy as np
import pytest

from edyx.io import (
    FILE_AXIS,
    load_asc_series,
    load_npz,
    load_txt,
    read_ta_dat,
    save_txt,
    stack_traces,
    write_ta_dat,
)

T = np.array([0.0, 1.0, 2.0, 3.0])
WL = np.array([500.0, 510.0, 520.0])
S = np.arange(12, dtype=float).reshape(3, 4)  # (W, T)


def write_asc(path, wl, signal):
    rows = "\n".join(f"{w},{v}" for w, v in zip(wl, signal))
    path.write_text(rows + "\n\n\nDate and Time: x\n")


def test_ta_dat_round_trip(tmp_path):
    fn = tmp_path / "a.dat"
    write_ta_dat(fn, T, WL, S)
    t, wl, s = read_ta_dat(fn)
    assert np.allclose(t, T) and np.allclose(wl, WL) and np.allclose(s, S)


def test_ta_dat_masked_and_header(tmp_path):
    fn = tmp_path / "a.dat"
    m = np.ma.masked_array(S, mask=np.zeros_like(S, dtype=bool))
    m[1, 2] = np.ma.masked
    write_ta_dat(fn, T, WL, m, header="some header\nsecond line")
    t, wl, s = read_ta_dat(fn)
    assert np.isnan(s[1, 2])
    s[1, 2] = S[1, 2]
    assert np.allclose(s, S)


def legacy_file(fn):
    cnt = np.full((5, 4), np.nan)
    cnt[1:, 0] = T[::-1]  # descending delays
    cnt[0, 1:] = WL
    cnt[1:, 1:] = S.T[::-1]  # (T, W), matching descending delays
    np.savetxt(fn, cnt)


def test_load_txt_legacy(tmp_path):
    fn = tmp_path / "a.txt"
    legacy_file(fn)
    t, wl, s = load_txt(fn)
    assert np.allclose(t, T) and np.allclose(wl, WL)
    assert s.shape == (3, 4)
    assert np.allclose(s, S)


def test_save_load_txt_round_trip(tmp_path):
    fn = tmp_path / "a.txt"
    save_txt(fn, T, WL, S)
    t, wl, s = load_txt(fn)
    assert np.allclose(t, T) and np.allclose(wl, WL) and np.allclose(s, S)


def test_save_txt_masked(tmp_path):
    fn = tmp_path / "a.txt"
    m = np.ma.masked_array(S, mask=S == 5)
    save_txt(fn, T, WL, m)
    _, _, s = load_txt(fn)
    assert np.isnan(s[1, 1]) and np.isnan(s).sum() == 1


def test_load_npz_unsorted(tmp_path):
    fn = tmp_path / "a.npz"
    order = [2, 0, 3, 1]
    np.savez(fn, delays=T[order], wl=WL, trace=S.T[order])
    t, _, s = load_npz(fn)
    assert np.allclose(t, T) and np.allclose(s, S)


def test_load_npz(tmp_path):
    fn = tmp_path / "a.npz"
    np.savez(fn, delays=T[::-1], wl=WL, trace=S.T[::-1])
    t, wl, s = load_npz(fn)
    assert np.allclose(t, T) and np.allclose(wl, WL)
    assert s.shape == (3, 4)
    assert np.allclose(s, S)


def test_stack_traces():
    t, wl, stack = stack_traces((T, WL, S + i) for i in range(5))
    assert stack.shape == (5, 3, 4)
    assert np.allclose(stack[2], S + 2)


def test_stack_traces_mismatch():
    with pytest.raises(ValueError, match="Wavelengths"):
        stack_traces([(T, WL, S), (T, WL + 1, S)])
    with pytest.raises(ValueError, match="Delays"):
        stack_traces([(T, WL, S), (T + 1, WL, S)])
    with pytest.raises(ValueError, match="Delays"):  # length 1 would broadcast
        stack_traces([(T[:1], WL, S[:, :1]), (T, WL, S)])
    with pytest.raises(ValueError, match="No traces"):
        stack_traces([])


def test_stack_traces_keeps_masks():
    m = np.ma.masked_invalid(np.where(S == 5, np.nan, S))
    _, _, stack = stack_traces([(T, WL, m), (T, WL, S)])
    assert np.ma.isMaskedArray(stack)
    assert stack.mask[0, 1, 1] and not stack.mask[1, 1, 1]


def test_axis_constants():
    stack = np.zeros((2, 3, 4))
    assert np.mean(stack, axis=FILE_AXIS).shape == (3, 4)
    with pytest.raises(np.exceptions.AxisError):
        np.mean(S, axis=FILE_AXIS)


@pytest.fixture
def asc_files(tmp_path):
    wl = np.array([500.0, 510.0, 520.0, 530.0])
    fns = []
    for i in range(3):
        fn = tmp_path / f"x_s100_{i:04d}.asc"
        signal = np.array([0.5 * i, 1.0 + i, 2.0 + i, 3.0 + i])  # first pixel = delay
        write_asc(fn, wl, signal)
        fns.append(str(fn))
    return wl, fns


def test_load_asc_series_first(asc_files):
    wl, fns = asc_files
    t, w, s = load_asc_series(fns)
    assert np.allclose(t, [0, 0.5, 1.0])
    assert np.allclose(w, wl)
    assert s.shape == (4, 3)
    assert np.allclose(s[1], [1, 2, 3])


def test_load_asc_series_step(asc_files):
    _, fns = asc_files
    t, _, s = load_asc_series(fns, step=0.1)
    assert np.allclose(t, np.arange(3) * 0.1)
    assert s.shape == (4, 3)


def test_load_asc_series_filename(asc_files):
    _, fns = asc_files
    t, _, _ = load_asc_series(fns, step="filename")
    assert np.allclose(t, np.arange(3) * 100)
