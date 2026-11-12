import numpy as np
from typer.testing import CliRunner

from edyx.io import read_dat
from edyx.scripts.collect_asc import app


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
    assert s.shape == (4, 3)
    assert np.allclose(t, [1, 2, 3])
