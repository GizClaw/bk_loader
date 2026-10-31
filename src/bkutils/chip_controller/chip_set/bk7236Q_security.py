import time
from serial import Timeout
from ...bk_log import BKLog
from ...common.common import user_operate, bytes_reverse, BIT, BFD, bytes_reverse_per4bytes
from ...common.encrypt_helper import decrypt_random, encrypt_random
from ..reg_controller import RegController

class BK7236Q_Security(RegController):

    def __init__(self, serial_instance):
        super().__init__(serial_instance)
        self.ser = serial_instance
        self.security_permission_ctrl_addr = 1259372544
        self.security_efuse_security_ctrl0 = 1259372560
        self.security_efuse_security_ctrl1 = 1259372564
        self.security_efuse_op_base = 1259339784
        self.security_efuse_vddpos = 3
        self.security_efuse_margin_rd = 5
        self.security_efuse_start_addr = 1259372544
        self.security_efuse_end_addr = 1259372799
        self.security_efuse_length = 64

    def _set_efuse_write_enable(self, enable: bool):
        if enable:
            tmp = 1
        else:
            tmp = 0
        if not self._set_reg_bit_val(self.security_efuse_op_base, self.security_efuse_vddpos, 1, tmp):
            return False
        return True

    def _set_efuse_margin_read(self, enable: bool):
        if enable:
            tmp = 1
        else:
            tmp = 0
        if not self._set_reg_bit_val(self.security_efuse_op_base, self.security_efuse_margin_rd, 1, tmp):
            return False
        return True

    def _read_efuse_by_regaddr(self, reg_addr, length, big_endian=False):
        """
        read bytes data from efuse
        'reg_addr' is the efuse reg address
        """
        cnt = length
        idx = 0
        value = bytearray()
        if not self._set_efuse_margin_read(enable=True):
            BKLog.e('_set_efuse_margin_read fail.')
            return (False, None)
        while cnt > 0:
            res = self.read_reg(reg_addr + 4 * idx)
            if res is None:
                return (False, None)
            elif big_endian:
                value.append(res >> 24 & 255)
                value.append(res >> 16 & 255)
                value.append(res >> 8 & 255)
                value.append(res & 255)
            else:
                value.append(res & 255)
                value.append(res >> 8 & 255)
                value.append(res >> 16 & 255)
                value.append(res >> 24 & 255)
            cnt -= 4
            idx += 1
        if not self._set_efuse_margin_read(enable=False):
            BKLog.e('_set_efuse_margin_read fail.')
            return (False, None)
        return (True, value)

    def _write_efuse_by_regaddr(self, reg_addr, value, big_endian=False):
        """
        write bytes data to efuse
        'reg_addr' is the efuse reg address
        """
        cnt = len(value)
        idx = 0
        while cnt > 0:
            if big_endian:
                wrv = value[4 * idx + 3] + (value[4 * idx + 2] << 8) + (value[4 * idx + 1] << 16) + (value[4 * idx] << 24)
            else:
                wrv = value[4 * idx] + (value[4 * idx + 1] << 8) + (value[4 * idx + 2] << 16) + (value[4 * idx + 3] << 24)
            if not self.write_reg(reg_addr + 4 * idx, wrv):
                BKLog.e(f'Write reg fail, address: 0x{reg_addr + 4 * idx:x}.')
                return False
            elif not self._set_efuse_margin_read(enable=True):
                BKLog.e('_set_efuse_margin_read fail.')
                return False
            else:
                res = self.read_reg(reg_addr + 4 * idx)
                if res is None:
                    BKLog.e(f'Read reg fail, address: 0x{reg_addr + 4 * idx:x}.')
                    return False
                elif res != wrv:
                    BKLog.e(f'Compare reg read and write fail, address: 0x{reg_addr + 4 * idx:x}.')
                    return False
                elif not self._set_efuse_margin_read(enable=False):
                    BKLog.e('_set_efuse_margin_read fail.')
                    return False
                else:
                    cnt -= 4
                    idx += 1
        return True

    def _set_efuse_permission(self, reg_addr, permission):
        """
        set efuse permission control
        'reg_addr' is the reg address, minimum operation length is 4 bytes
        'permission' is the permission value
        """
        msg = None
        if reg_addr >= self.security_efuse_start_addr and reg_addr <= self.security_efuse_end_addr:
            offset = int((reg_addr - self.security_efuse_start_addr) / 4)
            pm_addr = self.security_permission_ctrl_addr + int(offset / 16) * 4
            bitoff = offset % 16 * 2
        else:
            msg = 'Error, invalid efuse address: 0x{:x}.'.format(reg_addr)
            return (False, msg)
        if permission == 'wr':
            perm = 0
        elif permission == 'ro':
            perm = 1
        elif permission == 'na':
            perm = 3
        else:
            msg = f'Error, invalid efuse mode: {permission}.'
            return (False, msg)
        if not self._set_efuse_margin_read(enable=True):
            return (False, '_set_efuse_margin_read fail')
        else:
            res = self.read_reg(pm_addr)
            if res is None:
                msg = f'Read reg fail, address: 0x{pm_addr:x}.'
                return (False, msg)
            elif not self._set_efuse_margin_read(enable=False):
                return (False, '_set_efuse_margin_read fail')
            else:
                current_pm = res >> bitoff & 3
                if perm < current_pm:
                    BKLog.i(f'efuse permission address: 0x{pm_addr:x}, value: {current_pm}.')
                    msg = 'Set efuse permission ignore, already written different permission.'
                    return (False, msg)
                elif perm == current_pm:
                    BKLog.i(f'OTP permission address: 0x{pm_addr:x}, value: {current_pm}.')
                    BKLog.w('Set OTP permission ignore, already written same permission.')
                    return (True, None)
                else:
                    res &= ~(3 << bitoff)
                    res |= perm << bitoff
                    if not self._set_efuse_write_enable(enable=True):
                        return (False, '_set_efuse_write_enable fail')
                    elif not self.write_reg(pm_addr, res):
                        msg = f'Write reg fail, address: 0x{pm_addr:x}.'
                        return (False, msg)
                    elif not self._set_efuse_write_enable(enable=False):
                        return (False, '_set_efuse_write_enable fail')
                    elif not self._set_efuse_margin_read(enable=True):
                        return (False, '_set_efuse_margin_read fail')
                    else:
                        rdperm = self.read_reg(pm_addr)
                        if rdperm is None:
                            msg = f'Read reg fail, address: 0x{pm_addr:x}.'
                            return (False, msg)
                        elif rdperm != res:
                            msg = f'Compare write and read fail, address: 0x{pm_addr:x}'
                            return (False, msg)
                        elif not self._set_efuse_margin_read(enable=False):
                            return (False, '_set_efuse_margin_read fail')
                        else:
                            return (True, None)

    def _check_efuse_permission(self, reg_addr, read_write):
        """
        check permission control
        'reg_addr' is the reg address, minimum operation length is 4 bytes
        'read_write' True for read and False for write
        """
        msg = None
        if reg_addr >= self.security_efuse_start_addr and reg_addr <= self.security_efuse_end_addr:
            offset = int((reg_addr - self.security_efuse_start_addr) / 4)
            pm_addr = self.security_permission_ctrl_addr + int(offset / 16) * 4
            bitoff = offset % 16 * 2
        else:
            msg = 'Error, invalid efuse address: 0x{:x}.'.format(reg_addr)
            return (False, msg)
        if not self._set_efuse_margin_read(enable=True):
            return (False, '_set_efuse_margin_read fail')
        res = self.read_reg(pm_addr)
        if res is None:
            msg = f'Read reg fail, address: 0x{pm_addr:x}.'
            return (False, msg)
        else:
            if not self._set_efuse_margin_read(enable=False):
                return (False, '_set_efuse_margin_read fail')
            current_pm = res >> bitoff & 3
            if current_pm == 0 or current_pm == 1 or current_pm == 2 or (current_pm == 3):
                BKLog.d(f'permission address: 0x{pm_addr:x}, value: {current_pm:x}')
            else:
                msg = f'permission error, eFuse permission address @0x{pm_addr:x}, value: {current_pm:x}.'
                return (False, msg)
            if read_write:
                if current_pm == 3 or current_pm == 2:
                    msg = f'check eFuse permission fail, eFuse address: 0x{reg_addr:x} permission is na.'
                    return (False, msg)
            elif current_pm == 3 or current_pm == 1:
                msg = f'check eFuse permission fail, eFuse address: 0x{reg_addr:x} permission is ro/na.'
                return (False, msg)
            return (True, msg)

    def _set_efuse_permission_oplen(self, reg_addr, oplen, permission):
        """
        set permission control
        'reg_addr' is the reg address
        'oplen' is the operation length
        'permission' is the permission value
        """
        BKLog.i(f'set eFuse permission @0x{reg_addr:x}, length: {oplen}')
        msg = None
        for i in range(int(oplen / 4)):
            (ret, msg) = self._set_efuse_permission(reg_addr + i * 4, permission)
            if not ret:
                return (False, msg)
        return (True, None)

    def _check_efuse_permission_oplen(self, reg_addr, oplen, read_write):
        """
        check permission control
        'reg_addr' is the reg address
        'oplen' is the operation length
        'read_write' True for read and False for write
        """
        BKLog.i(f'check eFuse permission @0x{reg_addr:x}, length: {oplen}')
        for i in range(int(oplen / 4)):
            (ret, msg) = self._check_efuse_permission(reg_addr + i * 4, read_write)
            if not ret:
                return (False, msg)
        return (True, None)

    def _write_efuse_base(self, reg_addr, val, reverse=False, big_endian=False):
        """
        write efuse base operate
        'reg_addr' is the reg address
        """
        ss = bytes.fromhex(val)
        if reverse:
            ss = bytes_reverse_per4bytes(ss)
        length = len(ss)
        msg = None
        (ret, msg) = self._check_efuse_permission_oplen(reg_addr, length, read_write=True)
        if not ret:
            return (None, msg)
        (content, msg) = self._read_efuse_base(reg_addr, len(ss))
        if content is None:
            return (False, msg)
        elif content == ss:
            BKLog.w('Write efuse ignore, already written same data.')
            return (True, None)
        for idx in range(length):
            if content[idx] != 0:
                msg = 'Write efuse ignore, already written different data.'
                return (False, msg)
        if not self._set_efuse_write_enable(enable=True):
            return (False, '_set_efuse_write_enable fail')
        elif not self._write_efuse_by_regaddr(reg_addr, ss, big_endian):
            return (False, '_write_efuse_by_regaddr fail')
        elif not self._set_efuse_write_enable(enable=False):
            return (False, '_set_efuse_write_enable fail')
        return (True, None)

    def _read_efuse_base(self, reg_addr, oplen, big_endian=False):
        """
        read efuse base operate
        'reg_addr' is the reg address
        'oplen' is the read length
        """
        (ret, msg) = self._check_efuse_permission_oplen(reg_addr, oplen, read_write=True)
        if not ret:
            return (None, msg)
        (ret, content) = self._read_efuse_by_regaddr(reg_addr, oplen, big_endian)
        if not ret:
            return (None, '_read_efuse_by_regaddr fail')
        return (content, None)

    def _read_efuse(self, efuse_idx, oplen):
        if oplen + efuse_idx > 8:
            oplen = 8 - efuse_idx
        if oplen > 4:
            (ret, content0) = self._read_efuse_by_regaddr(self.security_efuse_security_ctrl0, 4, False)
            if not ret:
                return (None, '_read_efuse_by_regaddr fail')
            else:
                (ret, content1) = self._read_efuse_by_regaddr(self.security_efuse_security_ctrl1, 4, False)
                if not ret:
                    return (None, '_read_efuse_by_regaddr fail')
                else:
                    return ((content0 + content1)[efuse_idx:efuse_idx + oplen], None)
        else:
            if efuse_idx >= 4:
                (ret, content) = self._read_efuse_by_regaddr(self.security_efuse_security_ctrl1, 4, False)
            else:
                (ret, content) = self._read_efuse_by_regaddr(self.security_efuse_security_ctrl0, 4, False)
            if not ret:
                return (None, '_read_efuse_by_regaddr fail')
            elif efuse_idx >= 4:
                return (content[efuse_idx - 4:efuse_idx - 4 + oplen], None)
            else:
                return (content[efuse_idx:efuse_idx + oplen], None)

    def _write_efuse(self, efuse_idx, val):
        """
        efuse_idx: efuse byte address
        val: byte value
        """
        (rv, msg) = self._read_efuse(0, 8)
        if rv is None:
            return (False, '_read_efuse fail')
        readv = rv[efuse_idx]
        readv &= 255
        BKLog.i(f'Read efuse original value: 0x{readv:x}, address: {efuse_idx}.')
        for bit in range(8):
            if val & BIT(bit) == 0 and readv & BIT(bit) == BIT(bit):
                BKLog.i(f'address: {efuse_idx}, bit {bit}.')
                BKLog.e(msg='Write efuse ignore, already written to 1.')
                return (False, msg)
        if readv == val:
            BKLog.i(f'address: {efuse_idx}, bit {bit}.')
            BKLog.w('Write efuse ignore, already written same data.')
            return (True, None)
        rv[efuse_idx] = val
        if not self._set_efuse_write_enable(enable=True):
            return (False, '_set_efuse_write_enable fail')
        if efuse_idx >= 4:
            if not self._write_efuse_by_regaddr(self.security_efuse_security_ctrl1, rv[4:8], False):
                return (False, '_write_efuse_by_regaddr fail')
        elif not self._write_efuse_by_regaddr(self.security_efuse_security_ctrl0, rv[0:4], False):
            return (False, '_write_efuse_by_regaddr fail')
        if not self._set_efuse_write_enable(enable=False):
            return (False, '_set_efuse_write_enable fail')
        return (True, None)

    def _write_efuse_by_bit(self, efuse_idx, bit, val):
        (fullrv, msg) = self._read_efuse(0, 8)
        if fullrv is None:
            return (False, '_read_efuse fail')
        else:
            rv = fullrv[efuse_idx] & BIT(bit)
            BKLog.i(f'Read efuse original value: 0x{rv:x}, address: {efuse_idx}, bit {bit}.')
            if rv == BIT(bit):
                if val == 0:
                    BKLog.i(f'address: {efuse_idx}, bit {bit}.')
                    msg = 'Write efuse ignore, already written to 1.'
                    return (False, msg)
                else:
                    BKLog.i(f'address: {efuse_idx}, bit {bit}.')
                    BKLog.w('Write efuse ignore, already written same data.')
                    return (True, None)
            elif val == 0:
                BKLog.i(f'address: {efuse_idx}, bit {bit}.')
                BKLog.w('Write efuse ignore, dont need write.')
                return (True, None)
            else:
                tmp = fullrv[efuse_idx] | BIT(bit)
                fullrv[efuse_idx] = tmp
                if not self._set_efuse_write_enable(enable=True):
                    return (False, '_set_efuse_write_enable fail')
                else:
                    if efuse_idx >= 4:
                        if not self._write_efuse_by_regaddr(self.security_efuse_security_ctrl1, fullrv[4:8], False):
                            return (False, '_write_efuse_by_regaddr fail')
                    elif not self._write_efuse_by_regaddr(self.security_efuse_security_ctrl0, fullrv[0:4], False):
                        return (False, '_write_efuse_by_regaddr fail')
                    if not self._set_efuse_write_enable(enable=False):
                        return (False, '_set_efuse_write_enable fail')
                    else:
                        return (True, None)

    def _read_efuse_info(self, usr_info: user_operate):
        """
        read efuse by the 'user_operate' information
        """
        address = int(usr_info.start_addr, 16)
        length = int(usr_info.byte_len, 16)
        (content, msg) = self._read_efuse_base(address, length, usr_info.big_endian)
        if content is None:
            return (None, msg)
        ss = content
        if usr_info.reverse:
            ss = bytes_reverse_per4bytes(content)
        sstr = bytes.hex(bytes(ss))
        if usr_info.data_type == 'ascii':
            sstr = encrypt_random(sstr)
        return (sstr, None)

    def _write_efuse_info(self, usr_info: user_operate):
        """
        write otp by the 'user_operate' information
        """
        ss = usr_info.data
        if usr_info.data_type == 'hex':
            ss = usr_info.data
        elif usr_info.data_type == 'ascii':
            try:
                ss = decrypt_random(usr_info.data)
            except Exception:
                name = usr_info.name if usr_info.name else 'unknown'
                msg = "Error, '{0}': ascii decrypt failed; data must be a valid obfuscated string (even length, lowercase a-z only).".format(name)
                return (False, msg)
        else:
            msg = 'Error, data type not support: {0}.'.format(usr_info.data_type)
            return (False, msg)
        msg = None
        address = int(usr_info.start_addr, 16)
        length = int(usr_info.byte_len, 16)
        if length != len(ss) / 2:
            msg = 'Error, data length(0x{:x}) is not 0x{:x}.'.format(len(usr_info.data), length)
            return (False, msg)
        else:
            return self._write_efuse_base(address, ss, usr_info.reverse, usr_info.big_endian)
