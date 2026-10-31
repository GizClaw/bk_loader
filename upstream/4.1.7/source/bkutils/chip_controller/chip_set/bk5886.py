import time
from .bk7231N import BK7231N
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...common.common import safe_data
from ..reg_controller import RegController

class BK5886(BK7231N):
    CHIP_ID = 22662
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()

    def set_baudrate_correct(self):
        regctrl = RegController(self.ser)
        cnt = 5
        while cnt > 0:
            if regctrl.write_reg(8413952, 36123):
                break
            cnt -= 1
        if cnt <= 0:
            return False
        cnt = 5
        while cnt > 0:
            if regctrl.write_reg(8413956, 21772):
                break
            cnt -= 1
        if cnt <= 0:
            return False
        return True
