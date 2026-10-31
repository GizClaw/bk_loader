import time
from serial import Timeout
from .bk7236_security import BK7236_Security
from ...bk_log import BKLog
from ...common.common import user_operate, bytes_reverse, BIT, BFD
from ..reg_controller import RegController

class BK7259_Security(BK7236_Security):

    def __init__(self, serial_instance):
        super().__init__(serial_instance)
        self.ser = serial_instance
        self.security_efuse_base = 1149566992
        self.security_efuse_vddpos = 31
        self.security_otp_enable_addr = 1140916288
        self.security_otp_enable_pos = 2
        self.security_efuse_start_addr = 0
        self.security_efuse_end_addr = 31
        self.security_efuse_length = 32
        self.security_otp_base = 1108344832
        self.security_otp_apb_start_addr = 1108345856
        self.security_otp_apb_end_addr = 1108346876
        self.security_otp_apb_length = 512
        self.security_otp_ahb_start_addr = 1107361792
        self.security_otp_ahb_end_addr = 1107364860
        self.security_otp_ahb_length = 768
        self.security_otp_busy_addr = 1108345540
        self.security_otp_busy_pos = 0

    def is_otp_addr(self, addr):
        return self.security_otp_apb_start_addr <= addr <= self.security_otp_apb_end_addr or self.security_otp_ahb_start_addr <= addr <= self.security_otp_ahb_end_addr

    def is_efuse_addr(self, addr):
        return self.security_efuse_start_addr <= addr <= self.security_efuse_end_addr or self.security_efuse_base <= addr <= self.security_efuse_base + 63
