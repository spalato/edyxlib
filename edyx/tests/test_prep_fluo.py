import shutil
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from edyx.calib import interp_calibration, read_calibration, write_calibration
from edyx.io import read_cary_fluo
from edyx.scripts.flups import app

DATA = Path(__file__).parent / "data" / "fluo"
D261006 = DATA / "261006"
EMCORR = Path(__file__).parents[1] / "src" / "edyx" / "emcorr_cary-eclipse.toml"
runner = CliRunner()


def run(*args):
    return runner.invoke(app, ["prep-fluo", *args])


def header(path):
    lines = Path(path).read_text().splitlines()
    return "\n".join(ln for ln in lines if ln.startswith("#"))


def emcorr_factor(wl):
    return interp_calibration(read_calibration(EMCORR), wl)


# read_cary_fluo ---------------------------------------------------------------


def test_read_cary_fluo_pbbo():
    reps = read_cary_fluo(D261006 / "PBBO_ac_1mm_1.csv")
    assert len(reps) == 4
    assert [len(r.wl) for r in reps] == [54, 327, 327, 327]
    assert all(len(r.wl) == len(r.intensity) for r in reps)
    assert reps[0].wl[0] == pytest.approx(400)
    assert reps[0].wl[-1] == pytest.approx(453.03, abs=0.01)
    assert reps[1].wl[0] == pytest.approx(324.92)
    assert reps[1].wl[-1] == pytest.approx(650.86)
    assert reps[0].intensity.max() == 1000
    # repeated names: replicas are told apart by position.
    assert [r.name for r in reps] == [
        "261006_PBBO_ac_1mm_1",
        "261006_PBBO_ac_1mm_1",
        "261006_PBBO_ac_1mm_2",
        "261006_PBBO_ac_1mm_1",
    ]
    assert [r.meta["PMT voltage (V)"] for r in reps] == ["Medium", "Low", "Low", "Low"]
    assert [r.meta["Ex. Wavelength (nm)"] for r in reps] == ["350.00", "320.00", "320.00", "320.00"]
    assert all(r.meta["Instrument Serial Number"] == "MY2441CG03" for r in reps)
    assert reps[1].meta["Collection Time"].startswith("10/6/2026")
    assert "Scan rate (nm/min)" not in reps[0].meta  # key missing in this block
    assert reps[1].meta["Scan rate (nm/min)"] == "600.00"


def test_read_cary_fluo_counts():
    assert len(read_cary_fluo(D261006 / "C153_ac_1mm.csv")) == 3
    reps = read_cary_fluo(DATA / "260605" / "260605_C153_ac_1mm.csv")
    assert len(reps) == 4
    assert [r.meta["PMT voltage (V)"] for r in reps] == ["Low", "Medium", "Low", "Low"]


def test_read_cary_fluo_errors(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("wavelength,pcf\n220.0,1.0\n")
    with pytest.raises(ValueError, match="not a Cary"):
        read_cary_fluo(f)
    text = (D261006 / "C153_ac_1mm.csv").read_bytes().decode().replace("\r\n", "\n")  # CRLF or LF
    i = text.rindex("Collection Time")
    f.write_bytes(text[: text.rindex("\n\n", 0, i)].encode())  # last metadata block removed
    with pytest.raises(ValueError, match="metadata block"):
        read_cary_fluo(f)


# synthetic files --------------------------------------------------------------


def meta_block(name, ex=320.0, pmt="Low", start=300.0, stop=310.0, serial="MY2441CG03"):
    return "\n".join(
        [
            f"{name},",
            name,
            "Collection Time: 10/6/2026 5:32:26 PM",
            "Operator Name  :",
            "Parameter List :",
            f"Instrument Serial Number          {serial}",
            f"Start (nm)                        {start:.2f}",
            f"Stop (nm)                         {stop:.2f}",
            f"Ex. Wavelength (nm)               {ex:.2f}",
            "Ex. Slit (nm)                     5",
            "Em. Slit (nm)                     5",
            "Data interval (nm)                1.0000",
            f"PMT voltage (V)                   {pmt}",
            "Method Log     :",
            "Method Name    : Default",
            "",
        ]
    )


def write_csv(path, replicas):
    """Write a Cary-like csv. replicas: list of (name, wl, intensity, meta kwargs)."""
    n = max(len(r[1]) for r in replicas)
    lines = [
        ",".join(f"{r[0]}," for r in replicas),
        "Wavelength (nm),Intensity (a.u.)," * len(replicas),
    ]
    for i in range(n):
        lines.append("".join(f"{r[1][i]},{r[2][i]}," if i < len(r[1]) else ",," for r in replicas))
    text = "\n".join(lines) + "\n\n" + "\n".join(meta_block(r[0], **r[3]) for r in replicas)
    Path(path).write_bytes(text.replace("\n", "\r\n").encode())


WL = np.arange(300.0, 311.0)


def synth(path, intensities, metas=None):
    metas = metas or [{}] * len(intensities)
    write_csv(path, [(f"rep{i}", WL, y, metas[i]) for i, y in enumerate(intensities)])


@pytest.fixture
def fluo261006(tmp_path):
    d = tmp_path / "in" / "261006"
    shutil.copytree(D261006, d, ignore=shutil.ignore_patterns("*.FBSW"))
    return d


# prep-fluo --------------------------------------------------------------------


def test_prep_day(fluo261006, tmp_path):
    out = tmp_path / "out"
    result = run(str(fluo261006), "--outdir", str(out))
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in out.iterdir()) == [
        "261006_C153_ac_1mm_corr.dat",
        "261006_C6H_ac_1mm_corr.dat",
        "261006_PBBO_ac_1mm_1_corr.dat",
    ]
    # PBBO: replicas 2, 3, 4; replica 1 (the trial) excluded
    pbbo = out / "261006_PBBO_ac_1mm_1_corr.dat"
    reps = read_cary_fluo(fluo261006 / "PBBO_ac_1mm_1.csv")
    got = np.loadtxt(pbbo)
    expected = np.mean([r.intensity for r in reps[1:]], axis=0) * emcorr_factor(reps[1].wl)
    assert np.allclose(got[:, 0], reps[1].wl)
    assert np.allclose(got[:, 1], expected, rtol=1e-5)
    h = header(pbbo)
    assert "replicas used: 2 (" in h and ", 3 (" in h and ", 4 (" in h
    assert "replicas excluded: 1 (PMT voltage Medium (majority Low)" in h
    assert "intensity calibration: emcorr_cary-eclipse.toml" in h
    assert "source: PBBO_ac_1mm_1.csv" in h
    # C153 and C6H: all three
    for stem in ("C153", "C6H"):
        (src,) = fluo261006.glob(f"{stem}_*.csv")
        reps = read_cary_fluo(src)
        target = out / f"261006_{src.stem}_corr.dat"
        got = np.loadtxt(target)
        expected = np.mean([r.intensity for r in reps], axis=0) * emcorr_factor(reps[0].wl)
        assert np.allclose(got[:, 1], expected, rtol=1e-5)
        assert "replicas excluded: none" in header(target)


def test_prep_trial_replica_260605(tmp_path):
    f = DATA / "260605" / "260605_C153_ac_1mm.csv"
    result = run(str(f), "--outdir", str(tmp_path))
    assert result.exit_code == 0, result.output
    out = tmp_path / "260605_C153_ac_1mm_corr.dat"  # the date prefix is not repeated
    h = header(out)
    assert "replicas used: 1 (" in h and ", 3 (" in h and ", 4 (" in h
    assert "replicas excluded: 2 (" in h


def test_prep_skips_then_force(fluo261006, tmp_path):
    out = tmp_path / "out"
    args = [str(fluo261006), "--outdir", str(out)]
    assert run(*args).exit_code == 0
    target = out / "261006_C153_ac_1mm_corr.dat"
    target.write_text("sentinel")
    assert run(*args).exit_code == 0
    assert target.read_text() == "sentinel"
    assert run(*args, "--force").exit_code == 0
    assert target.read_text() != "sentinel"


def test_prep_use(fluo261006, tmp_path):
    f = str(fluo261006 / "PBBO_ac_1mm_1.csv")
    bad = run(f, "--outdir", str(tmp_path / "a"), "--use", "1,2")  # different grids
    assert bad.exit_code == 1
    assert not list((tmp_path / "a").glob("*.dat"))
    ok = run(f, "--outdir", str(tmp_path / "b"), "--use", "2,3")
    assert ok.exit_code == 0, ok.output
    reps = read_cary_fluo(f)
    target = tmp_path / "b" / "261006_PBBO_ac_1mm_1_corr.dat"
    expected = np.mean([reps[1].intensity, reps[2].intensity], axis=0) * emcorr_factor(reps[1].wl)
    assert np.allclose(np.loadtxt(target)[:, 1], expected, rtol=1e-5)
    assert "replicas excluded: 1 (not in --use); 4 (not in --use)" in header(target)
    # --use needs a single file
    assert run(str(fluo261006), "--outdir", str(tmp_path / "c"), "--use", "1,2").exit_code != 0
    # unknown replica
    assert run(f, "--outdir", str(tmp_path / "d"), "--use", "2,9").exit_code == 1


def test_prep_saturation(tmp_path):
    d = tmp_path / "261006"
    d.mkdir()
    y = np.linspace(10, 1000, len(WL))
    synth(d / "sat.csv", [y, y.copy()])
    result = run(str(d / "sat.csv"), "--outdir", str(tmp_path / "out"))
    assert result.exit_code == 1
    assert not list((tmp_path / "out").glob("*.dat"))
    # a saturated replica that is excluded is fine
    low = np.linspace(10, 100, len(WL))
    synth(d / "ok.csv", [y, low, low * 1.01, low * 0.99], metas=[{"pmt": "Medium"}, {}, {}, {}])
    result = run(str(d / "ok.csv"), "--outdir", str(tmp_path / "out"))
    assert result.exit_code == 0, result.output


def test_prep_no_majority(tmp_path):
    d = tmp_path / "261006"
    d.mkdir()
    y = np.linspace(10, 100, len(WL))
    synth(d / "tie.csv", [y, y * 2], metas=[{}, {"ex": 350.0}])
    result = run(str(d / "tie.csv"), "--outdir", str(tmp_path / "out"))
    assert result.exit_code == 1
    assert not list((tmp_path / "out").glob("*.dat"))
    # --use picks one
    result = run(str(d / "tie.csv"), "--outdir", str(tmp_path / "out"), "--use", "2")
    assert result.exit_code == 0, result.output


def test_prep_single_replica(tmp_path):
    d = tmp_path / "261006"
    d.mkdir()
    y = np.linspace(10, 100, len(WL))
    synth(d / "one.csv", [y])
    assert run(str(d / "one.csv"), "--outdir", str(tmp_path / "out")).exit_code == 0
    assert np.allclose(np.loadtxt(tmp_path / "out" / "261006_one_corr.dat")[:, 1],
                       y * emcorr_factor(WL), rtol=1e-5)


def test_prep_no_emcorr(fluo261006, tmp_path):
    f = fluo261006 / "C153_ac_1mm.csv"
    result = run(str(f), "--outdir", str(tmp_path), "--no-emcorr")
    assert result.exit_code == 0, result.output
    reps = read_cary_fluo(f)
    target = tmp_path / "261006_C153_ac_1mm_corr.dat"
    assert np.allclose(np.loadtxt(target)[:, 1], np.mean([r.intensity for r in reps], axis=0),
                       rtol=1e-5)
    assert "intensity calibration: none" in header(target)


def test_prep_emcorr_option(fluo261006, tmp_path):
    f = str(fluo261006 / "C153_ac_1mm.csv")
    wl = np.arange(200.0, 900.0)
    same = tmp_path / "same.toml"
    write_calibration(same, "emcorr", "wl", wl, np.full_like(wl, 2.0))
    result = run(f, "--outdir", str(tmp_path / "b"), "--emcorr", str(same))
    assert result.exit_code == 0, result.output
    reps = read_cary_fluo(f)
    got = np.loadtxt(tmp_path / "b" / "261006_C153_ac_1mm_corr.dat")
    assert np.allclose(got[:, 1], 2 * np.mean([r.intensity for r in reps], axis=0), rtol=1e-5)
    # outside the calibration range: the file fails
    short = tmp_path / "short.toml"
    write_calibration(short, "emcorr", "wl", np.arange(400.0, 500.0), np.ones(100))
    assert run(f, "--outdir", str(tmp_path / "c"), "--emcorr", str(short)).exit_code == 1


def test_prep_failed_file_does_not_stop_others(tmp_path):
    d = tmp_path / "261006"
    d.mkdir()
    shutil.copy(D261006 / "C153_ac_1mm.csv", d)
    (d / "A_not_cary.csv").write_text("wavelength,pcf\n220.0,1.0\n")
    result = run(str(d), "--outdir", str(tmp_path / "out"))
    assert result.exit_code == 1
    assert (tmp_path / "out" / "261006_C153_ac_1mm_corr.dat").exists()


def test_prep_no_date(tmp_path, caplog):
    f = tmp_path / "nodate" / "C153.csv"
    f.parent.mkdir()
    shutil.copy(D261006 / "C153_ac_1mm.csv", f)
    result = run(str(f), "--outdir", str(tmp_path / "out"))
    assert result.exit_code == 0, result.output
    assert "no date" in caplog.text
    assert (tmp_path / "out" / "C153_corr.dat").exists()


@pytest.mark.parametrize(
    "path, name",
    [
        ("Fluo/2026/260605/260604_C153.csv", "260604_C153_corr.dat"),
        ("260605/Fluo/PBBO_ac_all.csv", "260605_PBBO_ac_all_corr.dat"),
        ("261006/C153_ac_1mm.csv", "261006_C153_ac_1mm_corr.dat"),
        ("260605/260605.csv", "260605_corr.dat"),
    ],
)
def test_prep_output_path(tmp_path, path, name):
    from edyx.scripts.prep_fluo import output_path

    assert output_path(tmp_path / path, Path("out")).name == name


def test_prep_default_source(fluo261006, tmp_path, monkeypatch):
    root = tmp_path / "_DATA"
    fl = root / "FLUPS" / "2026" / "261006"
    fl.mkdir(parents=True)
    shutil.copytree(fluo261006, root / "fluo" / "2026" / "261006")  # case-insensitive match
    monkeypatch.chdir(fl)
    result = run()
    assert result.exit_code == 0, result.output
    assert len(list((fl / "PCF").glob("261006_*_corr.dat"))) == 3


def test_prep_default_source_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert run().exit_code == 1  # not a FLUPS dated folder
    fl = tmp_path / "_DATA" / "FLUPS" / "2026" / "261006"
    fl.mkdir(parents=True)
    monkeypatch.chdir(fl)
    assert run().exit_code == 1  # no Fluo folder


def test_flups_help_mentions_prep_fluo():
    result = runner.invoke(app, ["help"])
    assert result.exit_code == 0
    assert "prep-fluo" in result.output and "_corr.dat" in result.output
