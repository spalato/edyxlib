import datetime

import numpy as np
import pytest

from edyx.calib import interp_calibration, read_calibration, write_calibration


@pytest.fixture
def cal_file(tmp_path):
    path = tmp_path / "250709_t0_s2027.toml"
    x = np.linspace(275.0, 700.0, 1600)
    y = np.sin(x / 50.0) * 1.234567890123
    y[:3] = np.nan
    write_calibration(
        path, "t0", "wl", x, y,
        units=["nm", "ps"], date=datetime.date(2025, 7, 9), source="s20-s27",
        made_by="ta_s2027.ipynb", notes="",
        fit={"model": "polynomial in eV, low order first",
             "coef": np.array([1.0, -0.5, 0.25]),
             "points": np.array([[321.22, -0.33], [400.0, 0.1]])},
    )
    return path, x, y


def test_round_trip(cal_file):
    path, x, y = cal_file
    cal = read_calibration(path)
    np.testing.assert_array_equal(cal["x"], x)
    np.testing.assert_array_equal(cal["y"], y)  # exact, NaN included
    assert cal["kind"] == "t0" and cal["axis"] == "wl"
    assert cal["units"] == ["nm", "ps"]
    assert cal["date"] == datetime.date(2025, 7, 9)
    assert cal["source"] == "s20-s27" and cal["made_by"] == "ta_s2027.ipynb"
    assert cal["fit"]["coef"] == [1.0, -0.5, 0.25]
    assert cal["fit"]["points"] == [[321.22, -0.33], [400.0, 0.1]]
    assert type(cal["fit"]["coef"][0]) is float


def test_numpy_scalars_in_meta(tmp_path):
    path = tmp_path / "c.toml"
    write_calibration(path, "wl", "wl_raw", [1, 2], [3, 4], slope=np.float64(1.5), n=np.int64(3))
    cal = read_calibration(path)
    assert cal["slope"] == 1.5 and cal["n"] == 3


def test_non_ascii_and_backslashes(tmp_path):
    path = tmp_path / "c.toml"
    write_calibration(path, "t0", "wl", [1, 2], [3, 4], units=["\u00b5m", "\u00b0C"],
                      made_by=r"D:\exp\xanthene\nb.ipynb")
    cal = read_calibration(path)
    assert cal["units"] == ["\u00b5m", "\u00b0C"]
    assert cal["made_by"] == r"D:\exp\xanthene\nb.ipynb"


def test_none_is_refused(tmp_path):
    with pytest.raises(TypeError):
        write_calibration(tmp_path / "c.toml", "t0", "wl", [1, 2], [3, 4], notes=None)


def test_bad_shapes(tmp_path):
    with pytest.raises(ValueError):
        write_calibration(tmp_path / "c.toml", "t0", "wl", [1, 2, 3], [1, 2])


def test_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_calibration(tmp_path / "nope.toml")


CAL = {"x": np.array([0.0, 1.0, 2.0]), "y": np.array([10.0, 20.0, 40.0])}


def test_interp_by_value():
    np.testing.assert_allclose(interp_calibration(CAL, [0.5, 1.5, 2.0]), [15.0, 30.0, 40.0])


def test_interp_unsorted_calibration():
    cal = {"x": CAL["x"][::-1], "y": CAL["y"][::-1]}
    np.testing.assert_allclose(interp_calibration(cal, [0.5, 1.5]), [15.0, 30.0])


def test_interp_outside_error():
    with pytest.raises(ValueError, match="outside"):
        interp_calibration(CAL, [-1.0, 1.0])


def test_interp_outside_constant():
    np.testing.assert_allclose(interp_calibration(CAL, [-1.0, 3.0], outside="constant"),
                               [10.0, 40.0])


def test_interp_outside_nan():
    y = interp_calibration(CAL, [-1.0, 1.0, 3.0], outside="nan")
    np.testing.assert_array_equal(y, [np.nan, 20.0, np.nan])


def test_interp_bad_policy():
    with pytest.raises(ValueError):
        interp_calibration(CAL, [1.0], outside="clip")


def test_interp_keeps_shape():
    x = np.array([[0.5, 1.5], [1.0, 2.0]])
    assert interp_calibration(CAL, x).shape == (2, 2)
