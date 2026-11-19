from pistage import PIStage  # noqa: F401  (public import must work without hardware)
from pistage.mock import MockPIStage


def make(velocity=1_000_000):
    s = MockPIStage("Mock", "1")
    s.set_velocity(velocity)
    return s


def test_initial_state():
    s = make()
    assert s.get_pos() == 0
    assert not s.is_moving()


def test_move_to_completes():
    s = make()
    s.move_to(500)
    assert s.is_moving() or s.get_pos() == 500
    assert s.wait(timeout=5)
    assert s.get_pos() == 500
    assert not s.is_moving()


def test_move_negative():
    s = make()
    s.move_to(-300)
    assert s.wait(timeout=5)
    assert s.get_pos() == -300


def test_stop_halts_move():
    s = make(velocity=10)  # slow: cannot finish during the test
    s.move_to(1_000_000)
    s.stop()
    assert not s.is_moving()
    pos = s.get_pos()
    assert pos < 1_000_000
    assert s.get_pos() == pos


def test_velocity_roundtrip():
    s = make()
    s.set_velocity(1234)
    assert s.get_velocity() == 1234


def test_edges_and_home():
    s = make()
    s.find_max_edge()
    assert s.get_target() > 0
    s.stop()
    s.find_min_edge()
    assert s.get_target() < 0
    s.stop()
    s.define_home()
    assert s.get_pos() == 0
