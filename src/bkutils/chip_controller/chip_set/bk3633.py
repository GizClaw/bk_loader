import time
from .bk7231N import BK7231N
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...common.common import safe_data

class BK3633(BK7231N):

    CHIP_ID = 0x3633
    # Bootloader 部分板卡/固件读到的 chip id 为 0x381，与 0x3633 同属 BK3633 协议
    CHIP_ID_ALT = 0x381
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()


    