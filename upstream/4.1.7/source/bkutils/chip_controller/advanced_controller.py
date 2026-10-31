import time
from bkutils.protocol.app.app_bootloader_ota_success_protocol import AppBootloaderOtaSuccessProtocol
from bkutils.protocol.app.app_bootloader_partition_flag_protocol import AppBootloaderPartitionFlagProtocol
from ..bk_log import BKLog
from .serial_helper import SerialHelper
from ..chip_controller import BaseController
from ..common.common import LINKCHECK, RESET_TYPE
from ..protocol.app import AppEnterOutterFlashModeProtocol, AppEnterOutterFlashModeSuccessProtocol
from ..protocol.bootrom.v2_0 import ChipEnterCbusModeExtProtocol, ChipEnterCbusModeProtocol, ChipExitCbusModeProtocol, ChipStartBL2UpgradeProtocol, ChipStopBL2UpgradeProtocol, ChipHighFreqEnableProtocol, ChipEnterCbusModeDbgProtocol, ChipHighFreqSetProtocol

class AdvancedController(object):

    def __init__(self, serial_instance: SerialHelper) -> None:
        self.serial_instance = serial_instance

    def enter_exit_cbus_mode(self, flash_size, enter_exit, part_addr=None, part_size=None, flash_addr=None, max_try_count=60):
        cnt = max_try_count
        while cnt > 0:
            if enter_exit:
                cbus_protocol = ChipEnterCbusModeProtocol()
                if flash_size >= 268435456:
                    cbus_protocol = ChipEnterCbusModeExtProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(cbus_protocol.cmd([part_addr & 255, part_addr >> 8 & 255, part_addr >> 16 & 255, part_addr >> 24 & 255], [part_size & 255, part_size >> 8 & 255, part_size >> 16 & 255, part_size >> 24 & 255], [flash_addr & 255, flash_addr >> 8 & 255, flash_addr >> 16 & 255, flash_addr >> 24 & 255]), cbus_protocol.expect_length, 5.0)
                if tmp_res and cbus_protocol.response_check(content):
                    return True
            else:
                cbus_protocol = ChipExitCbusModeProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(cbus_protocol.cmd(), cbus_protocol.expect_length, 1.0)
                if tmp_res and cbus_protocol.response_check(content):
                    return True
            time.sleep(0.2)
            cnt -= 1
        return False

    def enter_exit_cbus_mode_dbg(self, enter_exit, flash_addr=None, max_try_count=60):
        cnt = max_try_count
        while cnt > 0:
            if enter_exit:
                cbus_protocol = ChipEnterCbusModeDbgProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(cbus_protocol.cmd([flash_addr & 255, flash_addr >> 8 & 255, flash_addr >> 16 & 255, flash_addr >> 24 & 255]), cbus_protocol.expect_length, 5.0)
                if tmp_res and cbus_protocol.response_check(content):
                    return True
            else:
                cbus_protocol = ChipExitCbusModeProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(cbus_protocol.cmd(), cbus_protocol.expect_length, 1.0)
                if tmp_res and cbus_protocol.response_check(content):
                    return True
            time.sleep(0.2)
            cnt -= 1
        return False

    def start_stop_bl2_upgrade(self, start_stop, max_try_count=5):
        cnt = max_try_count
        while cnt > 0:
            if start_stop:
                bl2_upgrade_protocol = ChipStartBL2UpgradeProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(bl2_upgrade_protocol.cmd(), bl2_upgrade_protocol.expect_length, 10.0)
                if tmp_res and bl2_upgrade_protocol.response_check(content):
                    return bl2_upgrade_protocol.get_boot_flag(content)
            else:
                bl2_upgrade_protocol = ChipStopBL2UpgradeProtocol()
                (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(bl2_upgrade_protocol.cmd(), bl2_upgrade_protocol.expect_length, 10.0)
                if tmp_res and bl2_upgrade_protocol.response_check(content):
                    return True
            cnt -= 1
        return False

    def enter_outter_flash_mode(self, max_retry_count=5):
        of_protocol = AppEnterOutterFlashModeProtocol()
        cnt = max_retry_count
        while cnt > 0:
            (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(of_protocol.cmd(), of_protocol.expect_length, 2.0)
            if tmp_res and of_protocol.response_check(content):
                return True
            cnt -= 1
        return False

    def enter_outter_flash_mode_success(self, max_retry_count=5):
        of_protocol = AppEnterOutterFlashModeSuccessProtocol()
        cnt = max_retry_count
        while cnt > 0:
            (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(of_protocol.cmd(), of_protocol.expect_length, 2.0)
            if tmp_res and of_protocol.response_check(content):
                return True
            cnt -= 1
        return False

    def high_freq_enable(self, mode, cpu_freq, flash_freq, max_retry_count=5):
        hf_protocol = ChipHighFreqEnableProtocol()
        cnt = max_retry_count
        while cnt > 0:
            (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(hf_protocol.cmd(mode, cpu_freq, flash_freq), hf_protocol.expect_length, 2.0)
            if tmp_res and hf_protocol.response_check(content):
                return True
            cnt -= 1
        return False

    def high_freq_set(self, mode, cpu_freq, flash_freq, target, delay=10, max_retry_count=5):
        cnt = max_retry_count
        while cnt > 0:
            self.serial_instance.drain()
            hf_protocol = ChipHighFreqSetProtocol()
            self.serial_instance.write_cmd(hf_protocol.cmd(mode, cpu_freq, flash_freq, target, 20))
            time.sleep(delay / 1000)
            self.serial_instance.switch_baudrate(target)
            ret_content = self.serial_instance.wait_for_cmd_response(hf_protocol.expect_length, 2.0)
            if len(ret_content) == hf_protocol.expect_length and hf_protocol.response_check(ret_content):
                return True
            base_ctrl = BaseController(serial_instance=self.serial_instance)
            if base_ctrl.do_link_check(linkcheck_obj=LINKCHECK.BOOTROM, max_try_count=10):
                return True
            BKLog.w('reconnect bus to retry')
            if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.DTR_RTS, linkcheck_obj=None, max_retry_count=20):
                BKLog.e('reconnect bus fail')
                BKLog.e('baudrate switch fail')
                return False
            cnt -= 1
        return False

    def read_bootloader_partition_flag(self, max_retry_count=5):
        partition_flag_protocol = AppBootloaderPartitionFlagProtocol()
        cnt = max_retry_count
        while cnt > 0:
            (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(partition_flag_protocol.cmd(), partition_flag_protocol.expect_length, 1.0)
            if tmp_res:
                (ret, flag) = partition_flag_protocol.response_check(content)
                if ret:
                    return flag
            cnt -= 1
        return None

    def write_bootloader_ota_success_flag(self, max_retry_count=5):
        ota_success_protocol = AppBootloaderOtaSuccessProtocol()
        cnt = max_retry_count
        while cnt > 0:
            (tmp_res, content) = self.serial_instance.write_cmd_and_wait_response(ota_success_protocol.cmd(), ota_success_protocol.expect_length, 1.0)
            if tmp_res and ota_success_protocol.response_check(content):
                return True
            cnt -= 1
        return False
