from pathlib import Path

from typer.testing import CliRunner

from pigui import launch_pigui as lp

runner = CliRunner()


def test_config_path_prints_and_exits():
    r = runner.invoke(lp.app, ["--config-path"])
    assert r.exit_code == 0
    assert r.stdout.strip() == str(lp.USER_CFG)


def test_user_config_is_flat_under_edyx():
    assert lp.USER_CFG.name == "pigui.toml"
    assert lp.USER_CFG.parent.name == "edyx"


def test_packaged_defaults_load():
    assert Path(lp.PACKAGED_CFG).exists()
    a = lp._load_appdata(str(lp.PACKAGED_CFG), None, None, None, None, None)
    assert a.port


def test_cli_args_override_file(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('port = "COM3"\naxis = "1"\n')
    a = lp._load_appdata(str(f), "COM9", None, None, None, 7)
    assert (a.port, a.axis, a.time_zero) == ("COM9", "1", 7)


def test_bad_file_falls_back_to_defaults(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('bogus = 1\n')
    a = lp._load_appdata(str(f), None, None, None, None, None)
    assert a.port == "Mock"
