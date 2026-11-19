import tomllib
import tomli_w
from attrs import define, asdict
#import attr
import logging
from pistage import PIStage
from pistage.mock import MockPIStage

from PySide6.QtWidgets import (QWidget, QPushButton, QSpinBox, QLabel, QFrame,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QMainWindow)
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QObject
from PySide6.QtGui import QFont

from qtlets import HasQtlets
from qtlets.widgets import IntEdit, FloatEdit, TypedLineEdit

logger = logging.getLogger()

@define
class PiguiAppData(HasQtlets):
    port: str  # COM1...
    axis: str
    scandir: int = -1
    time_zero: int = 0
    autoconnect: bool = False
    pos: int = 0  # last known value
    delay: float = 0  # delay
    velocity: int = 0
    ps_per_step = 2/3000

    def __attrs_pre_init__(self):
        super().__init__()

    def pos_to_delay(self, pos):
        return (pos-self.time_zero)*self.scandir*self.ps_per_step

    def delay_to_pos(self, delay):
        return self.scandir*delay/self.ps_per_step+self.time_zero

    def to_toml(self, filename):
        d = asdict(
            self,
            filter = lambda a, v: a.name not in ("pos", "delay", "velocity"),
        )
        if self.port.lower() == "mock":
            # don't save the mock port: keep the one already in the file, if any.
            d.pop("port")
            try:
                with open(filename, "rb") as f:
                    prev_port = tomllib.load(f).get("port")
            except (OSError, tomllib.TOMLDecodeError):
                prev_port = None
            if prev_port is not None:
                d = {"port": prev_port, **d}
        with open(filename, "wb") as f:
            tomli_w.dump(d, f)

    @classmethod
    def from_toml(cls, filename):
        with open(filename, "rb") as f:
            d = tomllib.load(f)
        d.setdefault("port", "Mock")
        return cls(**d)


class RejectableIntEdit(IntEdit):
    changeAborted = Signal()
    changeAccepted = Signal(int)
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.changeAccepted.emit(self.value())
            event.accept()
        elif key == Qt.Key_Escape:
            self.changeAborted.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class RejectableFloatEdit(FloatEdit):
    changeAborted = Signal()
    changeAccepted = Signal(float)
    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.changeAccepted.emit(self.value())
            event.accept()
        elif key == Qt.Key_Escape:
            self.changeAborted.emit()
            event.accept()
        else:
            super().keyPressEvent(event)


class PiguiController(QObject):
    """Controller object for the GUI and stage"""
    moveStarted = Signal()
    moveDone = Signal()

    def __init__(self, appdata, **kwargs):
        super().__init__(**kwargs)
        self.appdata = appdata
        self.timer = QTimer()
        self.update_dt = 100 # ms
        self.stage = None
        self.timer.timeout.connect(self.monitor)
        if appdata.autoconnect:
            self.make_stage()


    def make_stage(self):
        if self.appdata.port.lower() == "mock":
            logger.debug("Making mock stage")
            self.stage = MockPIStage(self.appdata.port, self.appdata.axis)
        else:
            logger.debug("Making PI Stage over serial")
            self.stage = PIStage(self.appdata.port, self.appdata.axis)
        self.update_all()

    def update_all(self):
        self.appdata.pos = self.stage.get_pos()
        self.appdata.velocity = self.stage.get_velocity()
        self.appdata.delay = self.appdata.pos_to_delay(self.appdata.pos)

    def move_to_pos(self, value):
        logger.debug(f"Moving to pos: {value}, ({type(value)})")
        self.stage.move_to(int(value))
        self.start_monitor()

    def move_to_delay(self, value):
        logger.debug(f"Moving to delay: {value}, ({type(value)})")
        pos = int(round(self.appdata.delay_to_pos(value),0))
        self.move_to_pos(pos)

    def move_to_t0(self):
        self.move_to_delay(0)

    def start_monitor(self):
        self.moveStarted.emit()
        self.timer.start(self.update_dt)

    def stop_monitor(self):
        self.timer.stop()
        self.moveDone.emit()

    def monitor(self):
        is_moving = self.stage.is_moving()
        self.appdata.pos = self.stage.get_pos()
        self.appdata.delay = self.appdata.pos_to_delay(self.appdata.pos)
        if not is_moving:
            self.stop_monitor()

    def stop_stage(self):
        self.stage.stop()

    def set_velocity(self, value):
        self.stage.set_velocity(value)

    def seek_low(self):
        self.stage.find_min_edge()
        self.start_monitor()

    def seek_hi(self):
        self.stage.find_max_edge()
        self.start_monitor()

    def define_home(self):
        self.stage.define_home()
        self.update_all()


class PIWidget(QWidget):
    def __init__(self, appdata: PiguiAppData, controller: PiguiController, **kwargs):
        super().__init__(**kwargs)

        self.appdata = appdata
        self.controller = controller

        self.port_edit = QLineEdit("")
        self.axis_edit = QLineEdit("")
        self.axis_edit.setMaxLength(4)
        self.stage_connect_btn = QPushButton("Connect")
        self.pos_edit = RejectableIntEdit(0)
        self.delay_edit = RejectableFloatEdit(0.0, decimals=3, fmt="{:.03f}")
        self.goto_zero_btn = QPushButton("Go to t0")
        self.goto_zero_btn.setToolTip("Go to t0")
        self.velocity_edit = RejectableIntEdit(0, bottom=0)
        self.slow_btn = QPushButton("Slow")
        self.slow_btn.setToolTip("Set speed to slow")
        self.fast_btn = QPushButton("Fast")
        self.fast_btn.setToolTip("Set speed to fast")
        self.t0_edit = IntEdit(0)
        self.t0_here_btn = QPushButton("Here")
        self.t0_here_btn.setToolTip("Set t0 here")
        self.seek_low_btn = QPushButton("⏮")  # <<
        self.seek_low_btn.setToolTip("Seek low stage limit.")
        self.stop_btn = QPushButton("⏹")  # stop
        self.stop_btn.setToolTip("Stop")
        self.seek_hi_btn = QPushButton("⏭") # >>
        self.seek_hi_btn.setToolTip("Seek high stage limit.")
        self.home_here_btn = QPushButton("⌂")  # house
        self.home_here_btn.setToolTip("Set home here.")

        # grid layout
        self.layout = QGridLayout(self)

        # populate layout
        self.layout.addWidget(QLabel("Port"), 0, 0)
        self.layout.addWidget(self.port_edit, 0, 1)
        self.layout.addWidget(self.axis_edit, 0, 2)
        self.layout.addWidget(self.stage_connect_btn, 0, 3)
        self.layout.addWidget(QLabel("pos (steps)"), 1, 0)
        self.layout.addWidget(self.pos_edit, 1, 1)
        self.layout.addWidget(QLabel("delay (ps)"), 2, 0)
        self.layout.addWidget(self.delay_edit, 2, 1)
        self.layout.addWidget(self.goto_zero_btn, 2,2)
        self.layout.addWidget(QLabel("speed"), 3, 0)
        self.layout.addWidget(self.velocity_edit, 3, 1)
        self.layout.addWidget(self.slow_btn, 3, 2)
        self.layout.addWidget(self.fast_btn, 3, 3)
        self.layout.addWidget(QLabel("t0"), 4, 0)
        self.layout.addWidget(self.t0_edit, 4, 1)
        self.layout.addWidget(self.t0_here_btn, 4, 2)
        self.layout.addWidget(self.seek_low_btn, 5, 0)
        self.layout.addWidget(self.stop_btn, 5, 1)
        self.layout.addWidget(self.seek_hi_btn, 5, 2)
        self.layout.addWidget(self.home_here_btn, 5, 3)
        # fine tune layout
        line_edits = [self.port_edit, self.axis_edit, self.pos_edit, self.delay_edit, self.velocity_edit, self.t0_edit]
        for w in line_edits:
            w.setMaximumWidth(100)
            w.setMinimumWidth(60)
            w.setAlignment(Qt.AlignRight)
        for c in range(self.layout.columnCount()):
            self.layout.setColumnMinimumWidth(c, 60)

        self.layout.setColumnStretch(self.layout.columnCount(), 1)
        self.layout.setRowStretch(self.layout.rowCount(), 1)

        appdata.link_widget(self.port_edit, "port")
        appdata.link_widget(self.axis_edit, "axis")
        appdata.link_widget(self.pos_edit, "pos")
        appdata.link_widget(self.delay_edit, "delay")
        appdata.link_widget(self.t0_edit, "time_zero")
        appdata.link_widget(self.velocity_edit, "velocity")
        self.appdata.qtlets["velocity"].data_changed.connect(self.controller.set_velocity)
        self.appdata.qtlets["time_zero"].data_changed.connect(self.controller.update_all)

        self.slow_btn.clicked.connect(self.on_slow_btn)
        self.fast_btn.clicked.connect(self.on_fast_btn)
        self.stage_connect_btn.clicked.connect(self.on_connect)
        self.goto_zero_btn.clicked.connect(self.controller.move_to_t0)
        self.t0_here_btn.clicked.connect(self.on_t0_here)
        self.seek_low_btn.clicked.connect(self.controller.seek_low)
        self.seek_hi_btn.clicked.connect(self.controller.seek_hi)
        self.home_here_btn.clicked.connect(self.controller.define_home)

        self.stop_btn.clicked.connect(self.controller.stop_stage)
        self.pos_edit.changeAccepted.connect(self.controller.move_to_pos)
        self.pos_edit.changeAborted.connect(self.controller.update_all)
        self.delay_edit.changeAccepted.connect(self.controller.move_to_delay)
        self.delay_edit.changeAborted.connect(self.controller.update_all)

        self.controller.moveStarted.connect(self.on_move_started)
        self.controller.moveDone.connect(self.on_move_done)

        # Styling and UI updates
        self.setStyleSheet("""
        QLineEdit {
            background-color: white;
            color: black;
            border: 1px solid #888;
        }
        QLineEdit:read-only {
            background-color: #ddd;
            color: #777;
        }
        QWidget:disabled {
            background-color: #ddd;
            color: #777;
        }
        """)
        self._disable_on_move = [
            self.port_edit, self.axis_edit, self.stage_connect_btn, self.pos_edit, self.delay_edit, self.t0_edit,
            self.t0_here_btn, self.goto_zero_btn,
        ]

    def on_slow_btn(self):
        self.appdata.velocity = 20000

    def on_fast_btn(self):
        self.appdata.velocity = 100000

    def on_connect(self):
        self.controller.make_stage()
        self.controller.update_all()

    def on_t0_here(self):
        self.appdata.time_zero = self.appdata.pos
        self.controller.update_all()

    def on_move_started(self):
        for w in self._disable_on_move:
            if isinstance(w, QLineEdit):
                w.setReadOnly(True)
            else:
                w.setEnabled(False)

    def on_move_done(self):
        for w in self._disable_on_move:
            if isinstance(w, QLineEdit):
                w.setReadOnly(False)
            else:
                w.setEnabled(True)



