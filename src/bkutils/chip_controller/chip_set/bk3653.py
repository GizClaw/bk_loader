# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/chip_set/bk3653.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import time
from .bk7236N import BK7236N
from .bk3653_security import BK3653_Security
from ...bk_log import BKLog
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...chip_controller import BaseController, RegController, AdvancedController
from ...common.bk_out_config import BkSetBaudrateConfig
from ...common.common import LINKCHECK, RESET_TYPE, safe_data, FLASH_CLOCK_LIST, CPU_CLOCK_LIST, PROGRAMING_MODE_LIST, BIT, bytes_reverse_per4bytes, crc32bytes, BinInfo
class BK3653(BK7236N):
    CHIP_ID = 13907
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL
    def __init__(self):
        super().__init__()
    def set_high_baudrate(self, baudrate):
        adctrl = AdvancedController(self.ser)
        if not adctrl.high_freq_set(PROGRAMING_MODE_LIST.PROGRAMING_DBUS, CPU_CLOCK_LIST.CLOCK_PLL_CPU_96M, FLASH_CLOCK_LIST.CLOCK_PLL_FLASH_40M, target=baudrate, delay=10):
            return False
        else:
            return True
    def write_chip_otp(self, otp_addr: int, content: str, reverse_content=False, bigendian=False):
        """\n        write otp by address information\n        """
        security = BK3653_Security(serial_instance=self.ser)
        return security._write_efuse_base(otp_addr, content, reverse_content, bigendian)
    def set_otp_permission_oplen(self, reg_addr, oplen, permission):
        """\n        reg_addr: start OTP address\n        oplen: reg count\n        permission: wr/ro/na\n        """
        security = BK3653_Security(serial_instance=self.ser)
        return security._set_efuse_permission_oplen(reg_addr, oplen, permission)
    def write_efuse_by_bit(self, reg_addr, bit, value):
        """\n        write one byte value, 8 bits\n        \'addr\' is the pos of efuse\n        """
        security = BK3653_Security(serial_instance=self.ser)
        return security._write_efuse_by_bit(reg_addr, bit, value)
    def write_efuse(self, efuse_addr, value):
        """\n        write several bytes value\n        \'addr\' is the efuse index\n        """
        security = BK3653_Security(serial_instance=self.ser)
        return security._write_efuse(efuse_addr, value)
    def read_chip_otp(self, otp_addr, oplen, reverse_content=False, bigendian=False):
        security = BK3653_Security(serial_instance=self.ser)
        content, msg = security._read_efuse_base(otp_addr, oplen, bigendian)
        if content is not None:
            if reverse_content:
                return (bytes_reverse_per4bytes(content), msg)
            else:
                return (content, msg)
        else:
            return (None, msg)
    def read_chip_uid(self):
        """\n        read chip UID from OTP, length: 5 bytes\n        """
        raise Exception('not support operation.')
    def read_efuse(self, addr, oplen):
        """\n        read chip efuse info\n        \'addr\' is start efuse address\n        if \'oplen\' set to 0, read all efuse value\n        """
        security = BK3653_Security(serial_instance=self.ser)
        if oplen == 0:
            byteslen = int(security.security_efuse_length / 8)
        else:
            byteslen = oplen
        val, msg = security._read_efuse(addr, byteslen)
        if val is None:
            BKLog.e(msg)
            return (False, None)
        else:
            return (True, val)
    def write_safe_json(self, safeinfo: safe_data):
        return self._work_as_safe_json(safeinfo, True)
    def read_as_safe_json(self, safeinfo: safe_data):
        return self._work_as_safe_json(safeinfo, False)
    def _work_as_safe_json(self, safeinfo: safe_data, write_biz: bool=True):
        security = BK3653_Security(serial_instance=self.ser)
        if safeinfo.user_operate_enable:
            for usrop in safeinfo.user_operate_list:
                if usrop.status == 'true':
                    raise Exception('Not support operation!')
            BKLog.i(f"{('write' if write_biz else 'read')} user operate ok.")
        if safeinfo.security_data_enable:
            for secdata in safeinfo.security_data_list:
                if secdata.status == 'true':
                    if secdata.name.find('aes_key') != (-1):
                        if not secdata.is_reverse_specified():
                            secdata.reverse = True
                        if not secdata.is_big_endian_specified():
                            secdata.big_endian = True
                    else:
                        if secdata.name.find('ota_key') != (-1) or secdata.name.find('ota_iv') != (-1) or secdata.name.find('media_data_key') != (-1):
                            if not secdata.is_reverse_specified():
                                secdata.reverse = False
                            if not secdata.is_big_endian_specified():
                                secdata.big_endian = False
                        else:
                            if not secdata.is_reverse_specified():
                                secdata.reverse = False
                            if not secdata.is_big_endian_specified():
                                secdata.big_endian = True
                    if write_biz:
                        ret, msg = security._write_efuse_info(secdata)
                        if not ret:
                            return (False, msg)
                    else:
                        ret, msg = security._read_efuse_info(secdata)
                        if not ret:
                            return (False, msg)
                        else:
                            BKLog.w(f'read {secdata.name}: {ret}')
            BKLog.i(f"{('write' if write_biz else 'read')} security data ok.")
        if safeinfo.efuse_enable:
            for efu in safeinfo.efuse_info_list:
                if efu.status == 'true':
                    if write_biz:
                        addr = int(efu.byte_addr, 16)
                        value = int(efu.data, 16)
                        ret, msg = security._write_efuse(addr, value)
                        if not ret:
                            return (False, msg)
                    else:
                        addr = int(efu.byte_addr, 16)
                        length = int(efu.length, 16)
                        efuse_value, msg = security._read_efuse(addr, length)
                        if efuse_value is None:
                            return (False, msg)
                        else:
                            BKLog.w(f'read {efu.name}: {bytes.hex(bytes(efuse_value))}')
            BKLog.i(f"{('write' if write_biz else 'read')} efuse ok.")
        if safeinfo.security_ctrl_enable and write_biz:
            if write_biz:
                for sectrl in safeinfo.security_ctrl:
                    slst = sectrl.split(',')
                    if len(slst) == 3 and slst[2] == '1':
                        byte_idx = int(slst[0])
                        bit_idx = int(slst[1])
                        ret, msg = security._write_efuse_by_bit(byte_idx, bit_idx, 1)
                        if not ret:
                            return (False, msg)
                BKLog.i('\'write security ctrl ok.')
            else:
                ret, msg = security._read_efuse(0, 8)
                if not ret:
                    return (False, msg)
                else:
                    BKLog.w(f'read security ctrl info ok: 0x{bytes.hex(bytes(ret))}')
        return (True, None)