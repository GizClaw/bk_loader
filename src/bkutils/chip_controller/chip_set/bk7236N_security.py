import time
from serial import Timeout
from ...bk_log import BKLog
from ...common.common import user_operate, bytes_reverse, BIT, BFD, bytes_reverse_per4bytes
from ...common.encrypt_helper import decrypt_random, encrypt_random
from .bk7236_security import BK7236_Security

class BK7236N_Security(BK7236_Security):

    def __init__(self, serial_instance):
        super().__init__(serial_instance)
        self.ser = serial_instance
        self.efuse_use_otp_addr = 1259340860
        self.security_aes_key_addr = 1259340864

    def _set_otp_write_enable(self):
        self._set_reg_bit_val(self.security_efuse_base, self.security_efuse_vddpos, 1, 1)
        time.sleep(0.05)
        res = self.read_reg(self.security_otp_enable_addr)
        if res is None:
            BKLog.e(f'Read reg fail, address: 0x{self.security_otp_enable_addr:x}.')
            return False
        res &= -9
        if not self.write_reg(self.security_otp_enable_addr, res):
            BKLog.e(f'Write reg fail, address: 0x{self.security_otp_enable_addr:x}.')
            return False
        elif not self._wait_for_busy_bit(self.security_otp_busy_addr, self.security_otp_busy_pos):
            BKLog.e(f'Wait for busy bit fail, address: 0x{self.security_otp_busy_addr:x}.')
            return False
        return True

    def _read_efuse(self, reg_addr, length):
        """
        'length' is byte numbers
        'reg_addr' is pos of efuse
        """
        if not self._set_otp_write_enable():
            msg = 'set_otp_write_enable fail.'
            return (None, msg)
        (ret, msg) = self._check_otp_permission_oplen(self.efuse_use_otp_addr, 4, read_write=True)
        if not ret:
            return (None, msg)
        (ret, rv) = self._read_otp_by_regaddr(self.efuse_use_otp_addr, 4, False)
        if not ret:
            return (False, None)
        elif length > int(self.security_efuse_length / 8):
            length = int(self.security_efuse_length / 8)
        return (True, rv[reg_addr:reg_addr + length])

    def _write_efuse_by_bit(self, reg_addr, bit, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        msg = None
        (ret, fullreadv) = self._read_efuse(0, 4)
        if not ret:
            msg = f'Read efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        readv = fullreadv[reg_addr]
        readv &= 255
        BKLog.i(f'Read efuse original value: 0x{readv:x}, address: 0x{reg_addr:x}.')
        if value == 0:
            if readv & BIT(bit) == BIT(bit):
                BKLog.i(f'address: 0x{reg_addr:x}, bit {bit}.')
                msg = 'Write efuse ignore, already written to 1.'
                return (False, msg)
            BKLog.i(f'address: 0x{reg_addr:x}, bit {bit}.')
            BKLog.w('Write efuse ignore, already written same data.')
            return (True, None)
        elif readv & BIT(bit) == BIT(bit):
            BKLog.i(f'address: 0x{reg_addr:x}, bit {bit}.')
            BKLog.w('Write efuse ignore, already written same data.')
            return (True, None)
        readv |= BIT(bit)
        writev = fullreadv
        writev[reg_addr] = readv
        if not self._write_otp_by_regaddr(self.efuse_use_otp_addr, writev, False):
            return (False, f'Write efuse fail, address: 0x{reg_addr:x}.')
        (ret, fullreadv) = self._read_efuse(0, 4)
        if not ret:
            msg = f'Read efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        elif writev != fullreadv:
            msg = f'Compare efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        return (True, None)

    def _write_efuse(self, reg_addr, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        msg = None
        (ret, fullreadv) = self._read_efuse(0, 4)
        if not ret:
            msg = f'Read efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        readv = fullreadv[reg_addr]
        readv &= 255
        BKLog.i(f'Read efuse original value: 0x{readv:x}, address: 0x{reg_addr:x}.')
        for bit in range(8):
            if value & BIT(bit) == 0 and readv & BIT(bit) == BIT(bit):
                BKLog.i(f'address: 0x{reg_addr:x}, bit {bit}.')
                return (False, 'Write efuse ignore, already written to 1.')
        if readv == value:
            BKLog.i(f'address: 0x{reg_addr:x}, bit {bit}.')
            BKLog.w('Write efuse ignore, already written same data.')
            return (True, None)
        readv |= value
        writev = fullreadv
        writev[reg_addr] = readv
        if not self._write_otp_by_regaddr(self.efuse_use_otp_addr, writev, False):
            return (False, 'Write efuse fail, address: 0x{reg_addr:x}.')
        (ret, fullreadv) = self._read_efuse(0, 4)
        if not ret:
            msg = f'Read efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        elif fullreadv != writev:
            msg = f'Compare efuse fail, address: 0x{reg_addr:x}.'
            return (False, msg)
        return (True, None)
