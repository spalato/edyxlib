# Mock PI stage
from time import time, sleep
from math import copysign
from typing import AnyStr, Tuple
import logging
logger = logging.getLogger(__name__)

class MockPIStage(object):
    def __init__(self, port_name: str, axis: AnyStr, 
            timeout: float=0.5, **kwargs):
        super().__init__(**kwargs)
        self._velocity = 200_000
        self._start_pos = 0
        self._start_t = time()
        self._target = 0
        self._current_pos = 0
        self._is_moving = False

    def connect(port_name, timeout=0.5):
        pass

    def _update(self):
        logger.debug("Updating, self._is_moving: "+repr(self._is_moving))
        if self._is_moving:
            dt = time() - self._start_t
            logger.debug(f"Elapsed time: {dt:.03f}")
            dist = self._target - self._start_pos
            moved = self._velocity*dt
            #logger.debug(f"Moved {int(moved):d} of {int(abs(dist)):d}")
            if moved > abs(dist):
                logger.debug("Move done.")
                self._current_pos = int(self._target)
                self._is_moving = False
            else:
                self._current_pos = int(self._start_pos + copysign(moved, dist))
            logger.debug(f"Current pos: %s", self._current_pos)
            

    def flush(self):
        pass

    def stop(self):
        logger.info("Stopping")
        self._update()
        self._is_moving = False

    def get_status_code(self) -> int:
        return 1

    def get_status(self) -> Tuple[bool, ...]:
        return (self._is_moving, False, False, False, False, False, False, False)


    def is_moving(self) -> bool:
        self._update()
        return self._is_moving

    def wait(self, dt=0.01, timeout=20) -> bool:
        start_t = time()
        while self.is_moving() :
            if ((time()-start_t) > timeout):
                return False
            sleep(dt)
        return True

    def get_pos(self) -> int:
        self._update()
        return self._current_pos

    def get_target(self) -> int:
        return self._target

    def get_velocity(self) -> int:
        return self._velocity

    def set_velocity(self, value):
        logger.debug(f"Setting velocity to {value}")
        self._velocity = value

    def move_to(self, value):
        self._is_moving = True
        self._target = value
        self._start_pos = self._current_pos
        logger.info("Moving to "+repr(self._target)+" from "+repr(self._start_pos))
        self._start_t = time()


    def find_max_edge(self):
        self.move_to(1_000_000)

    def find_min_edge(self):
        self.move_to(-200_000)

    def define_home(self):
        self._current_pos = 0

