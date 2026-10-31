import time
from .bk7231N import BK7231N
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...common.common import safe_data

class BK3515N(BK7231N):
    CHIP_ID = 13589
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()

    def pre_switch_baudrate(self):
        return True
