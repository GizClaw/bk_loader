from math import fabs
import time
from serial import Timeout
from bkutils.chip_controller import reg_controller
from ...common.bk_out_config import BkSetBaudrateConfig
from .bk7236 import BK7236
from .bk7236N_security import BK7236N_Security
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...bk_log import BKLog
from ...common.common import LINKCHECK, RESET_TYPE, safe_data, PM_CPU_FREQ_LIST, PM_FLASH_FREQ_LIST, PROGRAMING_MODE_LIST, BIT, bytes_reverse_per4bytes, crc32bytes, BinInfo
from ...chip_controller import BaseController, RegController, AdvancedController
import binascii

class BK7236N(BK7236):
    CHIP_ID = 1916161540
    SECOND_ID = [608174128, 616562720, 616562736, 638844960]
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()
        self.sys_reg_base = 1140916224
        self.uart_0_reg_base = 1149370368
        self.uart_config_clk_divid = 8

    def pre_check_img_file_crc(self, bin_list: list):
        if len(bin_list) == 0:
            return
        (ret, val) = self.read_efuse(0, 0)
        if not ret:
            return
        crc_enable = val[3] >> 3 & 1 == 0
        bin_has_crc = False
        for bininfo in bin_list:
            if crc32bytes(bininfo.pfile[0:32]) == bytearray(bininfo.pfile[0:34]):
                bin_has_crc = True
                break
        if not crc_enable == bin_has_crc:
            BKLog.w(f"board {('crc enable' if crc_enable else 'no crc')} but bin {('has crc' if bin_has_crc else 'no crc')}")

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

    def verify_chip_product_id(self, binfile: BinInfo):
        """
        read 16 bytes from bin 0x108(0x118 if with crc)
        compare with the otp product id (ahb offset: 0x58c~0x59c)
        """
        try:
            from bkutils.private.product_id_verifier import verify_chip_product_id_private
        except Exception as e:
            BKLog.w(f'import verify chip product id module fail: {e}')
            return
        sec = BK7236N_Security(serial_instance=self.ser)
        verify_chip_product_id_private(binfile, self.read_chip_otp, sec.security_otp_ahb_start_addr)

    def check_aes_key_enable(self):
        security = BK7236N_Security(serial_instance=self.ser)
        (ret, val) = security._read_efuse(3, 1)
        if not ret:
            BKLog.e('Read efuse fail.')
            return False
        if val[0] & BIT(5) != BIT(5):
            return 0
        return 1

    def check_aes_key_otp_data(self):
        """
        return False for execute fail, 0 for empty data, 1 for data is written
        """
        security = BK7236N_Security(serial_instance=self.ser)
        (ret, msg) = security._read_chip_otp(security.security_aes_key_addr, 32)
        if ret is None:
            BKLog.e('Read otp fail.')
            return False
        for idx in range(32):
            if ret[idx] != 0:
                return 1
        return 0

    def check_aes_key_otp_permission(self):
        """
        return False for execute fail, 0 for all permission is 0, 1 for permission is 0xf
        """
        security = BK7236N_Security(serial_instance=self.ser)
        pm = security._read_ot_permission_value(security.security_aes_key_addr)
        if pm is None:
            BKLog.e('Read otp permission fail.')
            return False
        if pm == 15:
            return 1
        return 0

    def write_chip_otp(self, otp_addr: int, content: str, reverse_content=False, bigendian=False):
        """
        write otp by address information
        """
        security = BK7236N_Security(serial_instance=self.ser)
        return security._write_chip_otp(otp_addr, content, reverse_content, bigendian)

    def set_otp_permission_oplen(self, reg_addr, oplen, permission):
        """
        reg_addr: start OTP address
        oplen: reg count
        permission: wr/ro/na
        """
        security = BK7236N_Security(serial_instance=self.ser)
        return security._set_otp_permission_oplen(reg_addr, oplen, permission)

    def write_efuse_by_bit(self, reg_addr, bit, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7236N_Security(serial_instance=self.ser)
        return security._write_efuse_by_bit(reg_addr, bit, value)

    def write_efuse(self, reg_addr, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7236N_Security(serial_instance=self.ser)
        return security._write_efuse(reg_addr, value)

    def read_chip_otp(self, otp_addr, oplen, reverse_content=False, bigendian=False):
        security = BK7236N_Security(serial_instance=self.ser)
        (ret, msg) = security._read_chip_otp(otp_addr, oplen, bigendian)
        if ret is not None:
            if reverse_content:
                return (bytes_reverse_per4bytes(ret), msg)
            return (ret, msg)
        return (None, msg)

    def read_chip_uid(self):
        """
        read chip UID from OTP, length: 5 bytes
        """
        security = BK7236N_Security(serial_instance=self.ser)
        if not security._set_otp_write_enable():
            BKLog.e('Set OTP write enable fail.')
            return (False, None)
        time.sleep(0.1)
        (ret, val) = security._read_otp_by_regaddr(1258358264, 5)
        if not ret:
            BKLog.e(f'Read OTP fail, address: 0x{security.security_otp_enable_addr:x}.')
            return (False, None)
        return (True, val)

    def read_efuse(self, addr, oplen):
        """
        read chip efuse info
        'addr' is start efuse address
        if 'oplen' set to 0, read all efuse value
        """
        security = BK7236N_Security(serial_instance=self.ser)
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
        security = BK7236N_Security(serial_instance=self.ser)
        if safeinfo.user_operate_enable:
            for usrop in safeinfo.user_operate_list:
                if usrop.status == 'true':
                    if write_biz:
                        if usrop.name.find('otp') != -1:
                            (ret, msg) = security._write_otp_info(usrop)
                            if not ret:
                                return (False, msg)
                        elif usrop.name.find('flash') != -1:
                            pass
                    elif usrop.name.find('otp') != -1:
                        (ret, msg) = security._read_otp_info(usrop)
                        if not ret:
                            return (False, msg)
                        BKLog.w(f'read {usrop.name}: {ret}')
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
                (ret, msg) = security._read_chip_otp(1259340860, 4, True)
                if not ret:
                    return (False, msg)
                BKLog.w(f'read efuse ok: 0x{bytes.hex(bytes(ret))}')
        return (True, None)
