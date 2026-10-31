# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/chip_set/bk7239N.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from math import fabs
import time
from serial import Timeout
from bkutils.chip_controller import reg_controller
from ...common.bk_out_config import BkSetBaudrateConfig
from .bk7236N import BK7236N
from .bk7236N_security import BK7236N_Security
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...bk_log import BKLog
from ...common.common import LINKCHECK, RESET_TYPE, safe_data, PM_CPU_FREQ_LIST, PM_FLASH_FREQ_LIST, PROGRAMING_MODE_LIST, BIT, bytes_reverse_per4bytes, crc32bytes, BinInfo
from ...chip_controller import BaseController, RegController, AdvancedController
import binascii
class BK7239N(BK7236N):
    CHIP_ID = 29238
    SECOND_ID = [628427040, 628426784, 628293664, 628427552]
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL
    def __init__(self):
        super().__init__()
        self.sys_reg_base = 1140916224
        self.uart_0_reg_base = 1149370368
        self.uart_config_clk_divid = 8
    def pre_check_img_file_crc(self, bin_list: list):
        if len(bin_list) == 0:
            return
        else:
            ret, val = self.read_efuse(0, 0)
            if not ret:
                return
            else:
                crc_enable = val[3] >> 3 & 1 == 0
                bin_has_crc = False
                for bininfo in bin_list:
                    if crc32bytes(bininfo.pfile[0:32]) == bytearray(bininfo.pfile[0:34]):
                        bin_has_crc = True
                        break
                if not crc_enable == bin_has_crc:
                    BKLog.w(f"board {('crc enable' if crc_enable else 'no crc')} but bin {('has crc' if bin_has_crc else 'no crc')}")
    def uart_select_clock(self, new_freq: int, old_freq: int, baudrate: int):
        regctrl = RegController(self.ser)
        start_time = time.perf_counter()
        val_r = regctrl.read_reg(self.uart_0_reg_base + 16)
        if val_r is None:
            return False
        else:
            val_r &= (-16776961)
            baud_div = int(new_freq / baudrate) - 1
            val_r |= baud_div << self.uart_config_clk_divid
            regctrl.write_reg(self.uart_0_reg_base + 16, val_r, delay_ms=50, retry=1)
            actual_baud = int(round(int(old_freq / (baud_div + 1)) / 1000) * 1000)
            self.ser.switch_baudrate(actual_baud)
            time.sleep(0.01)
            val_actual_r = regctrl.read_reg(self.uart_0_reg_base + 16)
            if val_actual_r is None or val_actual_r != val_r:
                return False
            else:
                val_r = regctrl.read_reg(self.sys_reg_base + 40)
                if val_r is None:
                    return False
                else:
                    val_r |= 4096
                    regctrl.write_reg(self.sys_reg_base + 40, val_r, delay_ms=50, retry=1)
                    self.ser.switch_baudrate(baudrate)
                    time.sleep(0.01)
                    val_actual_r = regctrl.read_reg(self.sys_reg_base + 40)
                    if val_actual_r is None or val_actual_r != val_r:
                        return False
                    else:
                        return True
    def set_high_baudrate(self, baudrate):
        adctrl = AdvancedController(self.ser)
        if not adctrl.high_freq_enable(PROGRAMING_MODE_LIST.PROGRAMING_DBUS, PM_CPU_FREQ_LIST.PM_CPU_FREQ_120M, PM_FLASH_FREQ_LIST.PM_FLASH_FREQ_40M):
            return False
        else:
            if not self.uart_select_clock(80000000, 40000000, baudrate):
                return False
            else:
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
                    else:
                        cnt -= 1
                        BKLog.e('reconnect bus to retry')
                        if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.MULTI, linkcheck_obj=None, max_retry_count=20):
                            BKLog.e('reconnect bus fail')
                            BKLog.e('baudrate switch fail')
                            return False
                        else:
                            BKLog.e('baudrate switch fail')
                return False
            else:
                return True
        else:
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
                        else:
                            BKLog.w('reconnect bus to retry')
                            if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.DTR_RTS, linkcheck_obj=None, max_retry_count=20):
                                BKLog.e('reconnect bus fail')
                                BKLog.e('baudrate switch fail')
                                return False
                            else:
                                cnt -= 1
                else:
                    BKLog.w('set high baudrate enable')
                    if self.set_high_baudrate(baudrate):
                        BKLog.w(f'set high baudrate:{baudrate} OK')
                        return True
                BKLog.e('baudrate switch fail')
                return False
            else:
                BKLog.i('ignore baudrate switch')
                return True