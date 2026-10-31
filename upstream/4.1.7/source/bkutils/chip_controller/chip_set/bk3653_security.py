import time
from serial import Timeout
from ...bk_log import BKLog
from ...common.common import user_operate, bytes_reverse, BIT, BFD, bytes_reverse_per4bytes
from ...common.encrypt_helper import decrypt_random, encrypt_random
from ..reg_controller import RegController
from .bk7236Q_security import BK7236Q_Security

class BK3653_Security(BK7236Q_Security):

    def __init__(self, serial_instance):
        super().__init__(serial_instance)
        self.ser = serial_instance
        self.security_permission_ctrl_addr = 1259372660
        self.security_efuse_security_ctrl0 = 1259372564
        self.security_efuse_security_ctrl1 = 1259372656
        self.security_efuse_op_base = 1259339784
        self.security_efuse_vddpos = 3
        self.security_efuse_margin_rd = 5
        self.security_efuse_start_addr = 1259372544
        self.security_efuse_end_addr = 1259372671
        self.security_efuse_length = 64
