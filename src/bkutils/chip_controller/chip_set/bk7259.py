import time
from serial import Timeout
from .bk7236 import BK7236
from .bk7259_security import BK7259_Security
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...bk_log import BKLog
from ...common.bk_out_config import BkSetBaudrateConfig
from ...common.common import FLASH_SIZE_DEF, LINKCHECK, RESET_TYPE, FLASH_ERASE_CMD_EXT, FLASH_ERASE_CMD, safe_data, BinInfo, is_buf_all_0xff, BIT, BFD, crc32_ver2, crc32bytes, bytes_reverse, bytes_reverse_per4bytes, PM_CPU_FREQ_LIST, PM_FLASH_FREQ_LIST, PROGRAMING_MODE_LIST
from ...chip_controller import BaseController, FlashController, RegController, AdvancedController

class BK7259(BK7236):
    CHIP_ID = 29273
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()

    def set_high_baudrate(self, baudrate):
        adctrl = AdvancedController(self.ser)
        if not adctrl.high_freq_set(PROGRAMING_MODE_LIST.PROGRAMING_DBUS, PM_CPU_FREQ_LIST.PM_CPU_FREQ_480M, PM_FLASH_FREQ_LIST.PM_FLASH_FREQ_80M, target=baudrate, delay=10):
            return False
        return True

    def set_baudrate(self, baudrate, delay_ms=20, max_retry_cnt=5):
        cmd_delay_ms = BkSetBaudrateConfig.cmd_delay_ms
        switch_delay_ms = BkSetBaudrateConfig.switch_delay_ms
        wait_response_timeout_ms = BkSetBaudrateConfig.wait_response_timeout_ms
        if BaseController.link_check_obj is not None and BaseController.link_check_obj == LINKCHECK.BL2:
            if baudrate != self.ser.baudrate:
                cnt = max_retry_cnt
                while cnt > 0:
                    self.ser.drain()
                    sbp = self.BOOTROM_PROTOCOL.SetBaudrateProtocol()
                    self.ser.write_cmd(sbp.cmd(baudrate, cmd_delay_ms))
                    time.sleep(switch_delay_ms / 1000)
                    self.ser.switch_baudrate(baudrate)
                    ret_content = self.ser.wait_for_cmd_response(sbp.expect_length, wait_response_timeout_ms / 1000)
                    if len(ret_content) == sbp.expect_length and sbp.response_check(ret_content, baudrate):
                        return True
                    base_ctrl = BaseController(serial_instance=self.ser)
                    if base_ctrl.do_link_check(linkcheck_obj=LINKCHECK.BL2):
                        return True
                    cnt -= 1
                    BKLog.e('reconnect bus to retry')
                    if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.MULTI, linkcheck_obj=None, max_retry_count=20):
                        BKLog.e('reconnect bus fail')
                        BKLog.e('baudrate switch fail')
                        return False
                    BKLog.e('baudrate switch fail')
                return False
            return True
        if baudrate == 3000000:
            baudrate = 2600000
        if baudrate != self.ser.baudrate:
            if baudrate <= 2600000:
                cnt = max_retry_cnt
                while cnt > 0:
                    self.ser.drain()
                    sbp = self.BOOTROM_PROTOCOL.SetBaudrateProtocol()
                    self.ser.write_cmd(sbp.cmd(baudrate, cmd_delay_ms))
                    time.sleep(switch_delay_ms / 1000)
                    self.ser.switch_baudrate(baudrate)
                    ret_content = self.ser.wait_for_cmd_response(sbp.expect_length, wait_response_timeout_ms / 1000)
                    if len(ret_content) == sbp.expect_length and sbp.response_check(ret_content, baudrate):
                        return True
                    base_ctrl = BaseController(serial_instance=self.ser)
                    if base_ctrl.do_link_check(linkcheck_obj=LINKCHECK.BOOTROM, max_try_count=10):
                        return True
                    BKLog.w('reconnect bus to retry')
                    if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.DTR_RTS, linkcheck_obj=None, max_retry_count=20):
                        BKLog.e('reconnect bus fail')
                        BKLog.e('baudrate switch fail')
                        return False
                    cnt -= 1
            else:
                BKLog.w('set high baudrate enable')
                if self.set_high_baudrate(baudrate):
                    BKLog.w(f'set high baudrate:{baudrate} OK')
                    return True
            BKLog.e('baudrate switch fail')
            return False
        BKLog.i('ignore baudrate switch')
        return True

    def pre_check_image_file(self, bin_list: list):
        """
        check if image data add crc(2bytes) per 32 bytes, then remove it
        """
        for bininfo in bin_list:
            if crc32bytes(bininfo.pfile[0:32]) == bytearray(bininfo.pfile[0:34]):
                total_len = bininfo.iFileLength
                src_data = bininfo.pfile
                if total_len % 34:
                    total_len += 34 - total_len % 34
                    src_data += b'0xff' * (34 - total_len % 34)
                idx = 0
                nocrc_buf = bytearray()
                while idx < total_len - 34:
                    nocrc_buf += bytearray(src_data[idx:idx + 32])
                    idx += 34
                bininfo.pfile = nocrc_buf
                bininfo.iFileLength = len(nocrc_buf)

    def pre_set_efuse_nocrc(self):
        security = BK7259_Security(serial_instance=self.ser)
        return security._write_efuse_by_bit(3, 3, 1)

    def write_chip_otp(self, otp_addr: int, content: str, reverse_content=False, bigendian=False):
        """
        write otp by address information
        """
        security = BK7259_Security(serial_instance=self.ser)
        return security._write_chip_otp(otp_addr, content, reverse_content, bigendian)

    def set_otp_permission_oplen(self, reg_addr, oplen, permission):
        """
        reg_addr: start OTP address
        oplen: reg count
        permission: wr/ro/na
        """
        security = BK7259_Security(serial_instance=self.ser)
        return security._set_otp_permission_oplen(reg_addr, oplen, permission)

    def write_efuse_by_bit(self, reg_addr, bit, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7259_Security(serial_instance=self.ser)
        return security._write_efuse_by_bit(reg_addr, bit, value)

    def write_efuse(self, reg_addr, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7259_Security(serial_instance=self.ser)
        return security._write_efuse(reg_addr, value)

    def read_chip_otp(self, otp_addr, oplen, reverse_content=False, bigendian=False):
        security = BK7259_Security(serial_instance=self.ser)
        (ret, msg) = security._read_chip_otp(otp_addr, oplen, bigendian)
        if ret is not None:
            if reverse_content:
                return (bytes_reverse_per4bytes(ret), msg)
            return (ret, msg)
        return (None, msg)

    def read_otp_efuse_auto(self, addr, oplen, reverse_content=False, bigendian=False):
        security = BK7259_Security(serial_instance=self.ser)
        if security.is_otp_addr(addr):
            return self.read_chip_otp(addr, oplen, reverse_content, bigendian)
        if security.is_efuse_addr(addr):
            (ret, efuse) = self.read_efuse(addr, oplen)
            if not ret:
                return (None, f'read efuse fail, address: 0x{addr:x}')
            return (efuse, None)
        return (None, f'Error, invalid OTP/Efuse address: 0x{addr:x}.')

    def read_chip_uid(self):
        """
        read chip UID from OTP, length: 5 bytes
        """
        security = BK7259_Security(serial_instance=self.ser)
        if not security._set_otp_write_enable():
            BKLog.e(f'Set OTP write enable fail.')
            return (False, None)
        time.sleep(0.1)
        (ret, val) = security._read_otp_by_regaddr(1259341760, 5, True)
        if not ret:
            BKLog.e(f'Read OTP fail, address: 0x{security.security_otp_enable_addr:x}.')
            return (False, None)
        return (True, val)

    def read_efuse(self, addr, oplen):
        """
        read chip efuse info
        """
        security = BK7259_Security(serial_instance=self.ser)
        if oplen == 0:
            byteslen = int(security.security_efuse_length / 8)
        else:
            byteslen = oplen
        (ret, val) = security._read_efuse(addr, byteslen)
        if not ret:
            BKLog.e('Read efuse fail.')
            return (False, None)
        return (True, val)

    def write_safe_json(self, safeinfo: safe_data):
        return self._work_as_safe_json(safeinfo, True)

    def read_as_safe_json(self, safeinfo: safe_data):
        return self._work_as_safe_json(safeinfo, False)

    def _work_as_safe_json(self, safeinfo: safe_data, write_biz: bool=True):
        security = BK7259_Security(serial_instance=self.ser)
        if safeinfo.user_operate_enable:
            for usrop in safeinfo.user_operate_list:
                if usrop.status == 'true':
                    if write_biz:
                        if usrop.name.find('otp') != -1:
                            (ret, msg) = security._write_otp_info(usrop, usrop.reverse, usrop.big_endian)
                            if not ret:
                                return (False, msg)
                        elif usrop.name.find('flash') != -1:
                            pass
            BKLog.i(f"{('write' if write_biz else 'read')} user operate ok.")
            if write_biz:
                for usrop in safeinfo.user_operate_list:
                    if usrop.status == 'true' and usrop.mode == 'write' and (usrop.name.find('otp') != -1):
                        (ret, msg) = security._write_otp_permission(usrop.start_addr, usrop.byte_len, usrop.permission)
                        if not ret:
                            return (False, msg)
        if safeinfo.security_data_enable:
            for secdata in safeinfo.security_data_list:
                if secdata.status == 'true':
                    if secdata.name.find('aes_key') != -1:
                        if not secdata.is_reverse_specified():
                            secdata.reverse = True
                        if not secdata.is_big_endian_specified():
                            secdata.big_endian = True
                    elif secdata.name.find('ota_key') != -1 or secdata.name.find('ota_iv') != -1 or secdata.name.find('media_data_key') != -1:
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
                        (ret, msg) = security._write_otp_info(secdata)
                        if not ret:
                            return (False, msg)
                        (ret, msg) = security._write_otp_permission(secdata.start_addr, secdata.byte_len, secdata.permission)
                        if not ret:
                            return (False, msg)
                    else:
                        addr = int(secdata.start_addr, 16)
                        if security.is_efuse_addr(addr):
                            length = int(secdata.byte_len, 16)
                            (ret, efuse_value) = security._read_efuse(addr, length)
                            if not ret:
                                return (False, None)
                            BKLog.w(f'read {secdata.name}: {bytes.hex(bytes(efuse_value))}')
                        else:
                            (ret, msg) = security._read_otp_info(secdata)
                            if not ret:
                                return (False, msg)
                            BKLog.w(f'read {secdata.name}: {ret}')
            BKLog.i(f"{('write' if write_biz else 'read')} security data ok.")
        if safeinfo.efuse_enable:
            for efu in safeinfo.efuse_info_list:
                if efu.status == 'true':
                    if write_biz:
                        addr = int(efu.byte_addr, 16)
                        value = int(efu.data, 16)
                        (ret, msg) = security._write_efuse(addr, value)
                        if not ret:
                            return (False, msg)
                    else:
                        addr = int(efu.byte_addr, 16)
                        length = int(efu.length, 16)
                        (ret, efuse_value) = security._read_efuse(addr, length)
                        if not ret:
                            return (False, None)
                        BKLog.w(f'read {efu.name}: {bytes.hex(bytes(efuse_value))}')
            BKLog.i(f"{('write' if write_biz else 'read')} efuse ok.")
        if safeinfo.security_ctrl_enable:
            if write_biz:
                for sectrl in safeinfo.security_ctrl:
                    slst = sectrl.split(',')
                    if len(slst) == 3 and slst[2] == '1':
                        byte_idx = int(slst[0])
                        bit_idx = int(slst[1])
                        (ret, msg) = security._write_efuse_by_bit(byte_idx, bit_idx, 1)
                        if not ret:
                            return (False, msg)
                BKLog.i("'write security ctrl ok.")
            else:
                (ret, msg) = security._read_efuse(0, int(security.security_efuse_length / 8))
                if not ret:
                    return (False, msg)
                BKLog.w(f'read efuse ok: 0x{bytes.hex(bytes(ret))}')
        return (True, None)
