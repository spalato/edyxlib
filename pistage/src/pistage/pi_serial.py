import serial
from time import time, sleep
from typing import AnyStr, Tuple
import logging
logger = logging.getLogger(__name__)

# Quick ref
# Abort: nAB
# Stop motion: nST

# Define current: nDC[1-9]

# Define Home: nDH
# Go Home: nGH
# Reset: nRT

# Tell status: nTS -> nTS:[num] # requires parsing bits.

# Set acceleration: nSA[1-500_000]
# tell target acceleraton: nTA -> nTA:[num]

# Set Velocity: nSV[1-200_000]
# Tell Velocity: nTY -> nTY:[num]

# Find edge: nFE[1-3]

# Limit sensor stage: nGL

# Tell position: nTP -> nTP:[num]
# Tell target: nTT -> nTT:[num]
# Move absolute: nMA[+-][1-2_000_000]
# Move relative: nMR[+-][1-2_000_000] # doesn't work?

# Set position: nSP[+-][1-2_000_000]
# Move position: nMP (move to position defined by SP)

# Tell Version: nVE


class PIStage(object):
    eol = b"\n"
    encoding = "ascii"
    def __init__(self, port_name: str, axis: AnyStr, 
            timeout: float=0.5, **kwargs):
        """
        Control of a Physik Instrumente stage over serial port.

        Parameters
        ----------
        port_name : string-like
            Name of the serial port, eg: "COM4".
        axis : string-like
            Axis number, as a string, ex: b'1'
        timeout : float
            Timeout delay, in seconds. Defaults to 0.5.

        Attributes
        ----------
        port : serial.Serial
            Serial port. 
        """
        super().__init__(**kwargs)

        if not isinstance(axis, bytes):
            axis = bytes(axis, self.encoding)
        self.axis = axis
        self.port = None
        if port_name is not None:
            self.connect(port_name, timeout)

    def connect(self, port_name: str, timeout: float=0.5):
        cfg = {
            "baudrate": 9600,
            "bytesize": 8, 
            "parity": "N",
            "stopbits": 1,
        }
        self.port = serial.Serial(
            port=port_name, timeout=timeout, **cfg
        )
        logger.info("Connected to port: %s", port_name)

    def _write(self, msg: AnyStr) -> bytes:
        """Write 'msg' to stage.
        
        The PI stage should echo every request. This is checked and handled."""
        if not isinstance(msg, bytes):
            msg = msg.encode()
        logger.debug("Writing message: %s", msg)
        payload = msg + self.eol
        self.port.write(payload)
        echo = self.port.readline()
        logger.debug("Echo: %s", echo)
        # TODO: check what happens if we write an invalid command.
        # TODO: maybe don't assert, but raise a RuntimeError or ValueError
        assert payload == echo 
        return echo

    def _qry(self, msg: AnyStr) -> bytes: # test changes
        """Query infromation from the stage.

        When querying, the stage will emit two responses: one echo of the query,
        and the actual answer. This method emits only the answer, stripped of
        unecessary header.
        """
        self._write(msg)
        ret = self.port.readline().rstrip(self.eol)
        logger.debug("Reply: %s", ret)
        head, tail = ret.split(b":")
        assert head.lower() == msg.lower()
        return tail

    def flush(self):
        """Flush current readable port content."""
        logger.debug("Flushing read buffer.")
        return self.port.readall()

    def stop(self):
        """Stop stage motion"""
        logger.info("Stage stopping.")
        self._write(self.axis+b"ST")

    def get_status_code(self) -> int:
        """Status code of the stage, as an int."""
        msg = self.axis+b"TS"
        return int(self._qry(msg))

    def get_status(self) -> Tuple[bool, ...]:
        """Status flags, as booleans."""
        # TODO: make a namedtuple?
        code = self.get_status_code()
        return tuple([code & 2**n > 0 for n in range(0, 8)])

    def is_moving(self) -> bool:
        """Is stage moving?"""
        return self.get_status()[0]

    def wait(self, dt=0.01, timeout=20) -> bool:
        "Wait until stage is done. Returns True for normal completion, False for timeout."
        start_t = time()
        while self.is_moving():
            if (time() - start_t) > timeout:
                return False
            sleep(dt)
        return True

    def get_pos(self) -> int:
        """Current stage position"""
        msg = self.axis+b"TP"
        return int(self._qry(msg))

    def get_target(self) -> int: # TODO: test
        """Current target"""
        msg = self.axis+b"TT"
        return int(self._qry(msg))

    def get_velocity(self) -> int:
        """Current velocity"""
        return int(self._qry(self.axis+b"TY"))

    def set_velocity(self, value):
        """Set velocity, in microsteps"""
        self._write(self.axis + "SV{:d}".format(value).encode())

    def move_to(self, value):
        """Move to absolute position, in microsteps"""
        self._write(self.axis + "MA{:d}".format(value).encode())

    def find_min_edge(self):
        """Move to minimum edge."""
        self._write(self.axis + b"FE2")

    def find_max_edge(self):
        """Move to maximum edge."""
        self._write(self.axis + b"FE1")

    def define_home(self):
        """Define home here"""
        self._write(self.axis + b"DH")


