import os

import numpy as np
import pytest
from typer.testing import CliRunner

from edyx.io import read_dat
from edyx.scripts.collect_asc import app
from edyx.scripts.flups import app as flups_app


def test_collect_run(tmp_path):
    run = tmp_path / "260910" / "run01"
    run.mkdir(parents=True)
    wl = [500.0, 510.0, 520.0, 530.0]
    for i in (1, 2, 3):
        rows = "\n".join(f"{w},{v}" for w, v in zip(wl, [float(i), 1.0, 2.0, 3.0]))
        (run / f"x_sig{i:04d}.asc").write_text(rows + "\n\n\nDate and Time: x\n")
    result = CliRunner().invoke(app, [str(run), "--no-pbar"])
    assert result.exit_code == 0, result.output
    out = tmp_path / "260910" / "260910_run01.dat"
    assert out.exists()
    t, w, s = read_dat(out)
    assert s.shape == (3, 3)
    assert np.allclose(t, [1, 2, 3])


WL = [500.0, 510.0, 520.0, 530.0]


def make_run(run, delays=(1, 2, 3)):
    run.mkdir(parents=True)
    for i, d in enumerate(delays, start=1):
        rows = "\n".join(f"{w},{v}" for w, v in zip(WL, [float(d), 1.0, 2.0, 3.0]))
        (run / f"x_sig{i:04d}.asc").write_text(rows + "\n\n\nDate and Time: x\n")


@pytest.fixture
def day(tmp_path):
    d = tmp_path / "260605"
    make_run(d / "run01")
    make_run(d / "run02")
    make_run(d / "PCF" / "PBBO" / "run01", delays=(6.5, 6.5, 6.5))
    return d


def outputs(d):
    return [d / "260605_run01.dat", d / "260605_run02.dat",
            d / "PCF" / "PBBO" / "260605_PCF_PBBO_run01.dat"]


def invoke(cli, *args):
    return CliRunner().invoke(cli, [*map(str, args), "--no-pbar"])


def invoke_flups(*args):
    return CliRunner().invoke(flups_app, ["collect-asc", *map(str, args), "--no-pbar"])


@pytest.mark.parametrize("run_cli", [lambda *a: invoke(app, *a), invoke_flups])
def test_collect_day(day, run_cli):
    result = run_cli(day)
    assert result.exit_code == 0, result.output
    for out in outputs(day):
        assert out.exists(), out
    t, w, s = read_dat(outputs(day)[0])
    assert np.allclose(w, WL[1:]) and s.shape == (3, 3)
    assert np.allclose(t, [1, 2, 3])
    # PCF-like: all delays equal.
    t, w, s = read_dat(outputs(day)[2])
    assert np.allclose(t, 6.5) and s.shape == (3, 3)
    header = outputs(day)[0].read_text().splitlines()[0]
    assert "pixel 0 removed" in header


@pytest.mark.parametrize("sub", ["PCF", "PCF/PBBO", "PCF/PBBO/run01"])
def test_collect_subtree(day, sub):
    result = invoke(app, day / sub)
    assert result.exit_code == 0, result.output
    assert outputs(day)[2].exists()
    assert not outputs(day)[0].exists()


def test_collect_no_argument(day, monkeypatch):
    monkeypatch.chdir(day)
    result = CliRunner().invoke(flups_app, ["collect-asc", "--no-pbar"])
    assert result.exit_code == 0, result.output
    assert all(o.exists() for o in outputs(day))


def test_collect_skips_existing_and_force(day):
    assert invoke(app, day).exit_code == 0
    out = outputs(day)[0]
    old = (out.stat().st_mtime_ns, out.read_bytes())
    os.utime(out, ns=(1_000_000_000, 1_000_000_000))
    result = invoke(app, day)
    assert result.exit_code == 0, result.output
    assert out.stat().st_mtime_ns == 1_000_000_000
    assert out.read_bytes() == old[1]
    result = invoke(app, day, "--force")
    assert result.exit_code == 0, result.output
    assert out.stat().st_mtime_ns != 1_000_000_000


def test_collect_outdir(day, tmp_path):
    outdir = tmp_path / "out"
    assert invoke(app, day, "-o", outdir).exit_code == 0
    assert (outdir / "260605_run01.dat").exists()
    assert (outdir / "260605_PCF_PBBO_run01.dat").exists()
    assert not outputs(day)[0].exists()
    # the existence check uses the outdir path.
    target = outdir / "260605_run01.dat"
    target.write_text("keep")
    assert invoke(app, day, "-o", outdir).exit_code == 0
    assert target.read_text() == "keep"
    assert invoke(app, day, "-o", outdir, "--force").exit_code == 0
    assert target.read_text() != "keep"


def test_collect_no_dated_ancestor(tmp_path, caplog):
    make_run(tmp_path / "data" / "run01")
    result = invoke(app, tmp_path / "data")
    assert result.exit_code == 1
    assert "no dated folder" in caplog.text
    assert not (tmp_path / "data" / "data_run01.dat").exists()


def test_flups_help_texts():
    result = CliRunner().invoke(flups_app, ["collect-asc", "--help"], terminal_width=200)
    assert result.exit_code == 0
    assert "--force" in result.output and "paths" in result.output
    result = CliRunner().invoke(flups_app, ["help"])
    assert result.exit_code == 0
    assert "collect-asc" in result.output
