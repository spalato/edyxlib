import pytest
from pigui.pigui import PiguiAppData


def make(**kw):
    return PiguiAppData(port="Mock", axis="1", **kw)


def test_pos_delay_roundtrip():
    a = make(time_zero=1000, scandir=-1)
    assert a.pos_to_delay(1000) == 0
    assert a.delay_to_pos(0) == 1000
    for pos in (0, 1000, 123456):
        assert a.delay_to_pos(a.pos_to_delay(pos)) == pytest.approx(pos)


def test_scandir_sign():
    up = make(time_zero=0, scandir=1)
    down = make(time_zero=0, scandir=-1)
    assert up.pos_to_delay(3000) == pytest.approx(2.0)
    assert down.pos_to_delay(3000) == pytest.approx(-2.0)


def test_toml_roundtrip(tmp_path):
    f = tmp_path / "pigui.toml"
    make(time_zero=42, scandir=1, autoconnect=True).to_toml(f)
    b = PiguiAppData.from_toml(f)
    assert (b.port, b.axis, b.time_zero, b.scandir, b.autoconnect) == ("Mock", "1", 42, 1, True)


def test_transient_values_not_saved(tmp_path):
    f = tmp_path / "pigui.toml"
    a = make()
    a.pos, a.delay, a.velocity = 5, 1.5, 100
    a.to_toml(f)
    text = f.read_text()
    for name in ("pos", "delay", "velocity"):
        assert f"{name} =" not in text


def test_mock_port_keeps_saved_real_port(tmp_path):
    f = tmp_path / "pigui.toml"
    PiguiAppData(port="COM7", axis="1").to_toml(f)
    make().to_toml(f)
    assert PiguiAppData.from_toml(f).port == "COM7"


def test_missing_port_defaults_to_mock(tmp_path):
    f = tmp_path / "pigui.toml"
    f.write_text('axis = "2"\n')
    assert PiguiAppData.from_toml(f).port == "Mock"
