import os
import time
from bkutils.common import ui_bridge
from bkutils.common.ui_bridge_data import TaskInfo
from .action_base import ActionBase
from ..chip_controller import BaseController
from ..chip_controller import get_chip_set_with_chip_id
from ..chip_controller import get_chip_set_with_chip_name
from ..bk_log import BKLog
from ..common.common import EraseInfo, parse_readinfo_otp
from ..common.bk_out_config import BkEraseFlowConfig
from ..common.random_bin_verify import maybe_verify_random_bin_after_get_bus

class Erase(ActionBase):

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, link_check_type=None, reset_type=None, reset_baudrate=115200, getbus_times=100, reboot_after_donwload=True, recnt=5, chipid=None, debug='3', link_key=None, random_bin_path=None) -> None:
        super().__init__(port, baudrate)
        self.link_check_type = link_check_type
        self.reset_type = reset_type
        self.reset_baudrate = reset_baudrate
        self.reboot_after_donwload = reboot_after_donwload
        self.getbus_times = getbus_times
        self.retry = recnt
        self.chip_id = chipid
        self.debug = debug
        self.link_key = link_key
        self.random_bin_path = random_bin_path
        self.task_index = -1
        self.task_list = []

    def task_flag(self, start: bool):
        if start:
            self.task_index += 1
        if self.task_index < len(self.task_list):
            task = self.task_list[self.task_index]
            task.task_start = start
            ui_bridge.task_flag(task)

    def append_task(self, task_name: str):
        task_info = TaskInfo(task_name=task_name, task_id=len(self.task_list))
        self.task_list.append(task_info)

    def combine_task_list(self, eraseinfo: EraseInfo):
        if eraseinfo.bAllFlash:
            self.append_task('erase all')
        elif eraseinfo.vecbinInfo:
            for bininfo in eraseinfo.vecbinInfo:
                self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
        if eraseinfo.flash_otp:
            self.append_task('erase flash OTP')
        ui_bridge.task_list(self.task_list)

    def erase_task(self, eraseinfo: EraseInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_task_list(eraseinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=None, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkEraseFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                maybe_verify_random_bin_after_get_bus(self.ser, linktype, self.random_bin_path)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if not chip_set.set_baudrate_correct():
                    raise Exception('set baudrate correct fail.')
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                BKLog.i('check BKAESRDM words in flash...')
                chip_set.check_bkaesrdm_status(retry_cnt=5)
                BKLog.i('check BKAESRDM words in flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Erasing', int(current_prog))
                BKLog.i('unprotect flash...')
                if not chip_set.un_protect_flash(protect=False):
                    raise Exception('unprotect flash fail.')
                BKLog.i('unprotect flash OK.')
                if BkEraseFlowConfig.develop_set_baudrate_before_align or chip_set.pre_switch_baudrate():
                    BKLog.i('set baudrate to {0}...'.format(eraseinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=eraseinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(eraseinfo.work_baudrate))
                    if eraseinfo.vecbinInfo:
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=eraseinfo.vecbinInfo, for_erase=True, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if eraseinfo.vecbinInfo:
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=eraseinfo.vecbinInfo, for_erase=True, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    BKLog.i('set baudrate to {0}...'.format(eraseinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=eraseinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(eraseinfo.work_baudrate))
                if eraseinfo.bAllFlash or eraseinfo.vecbinInfo:
                    total_prog = 80
                    prog_per_bin = total_prog / len(eraseinfo.vecbinInfo) if len(eraseinfo.vecbinInfo) > 0 else 1
                    if eraseinfo.bAllFlash:
                        self.task_flag(True)
                        BKLog.i('erase whole flash.')
                        if not chip_set.erase_flash(True, None, None, self.retry, cprog=current_prog, sprog=total_prog):
                            raise Exception('erase whole flash fail.')
                        current_prog += total_prog
                        BKLog.i('erase whole flash OK.')
                        self.task_flag(False)
                    elif eraseinfo.vecbinInfo:
                        erase_idx = 0
                        for binfile in eraseinfo.vecbinInfo:
                            self.task_flag(True)
                            BKLog.i(f'[{erase_idx}] erase flash.')
                            BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                            BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                            if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, cprog=current_prog, sprog=prog_per_bin):
                                raise Exception('Erase flash fail.')
                            current_prog += prog_per_bin
                            BKLog.i(f'[{erase_idx}] erase flash OK.')
                            self.task_flag(False)
                            erase_idx += 1
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        raise Exception('protect flash fail.')
                    BKLog.i('protect flash OK.')
                    BKLog.w('Erase flash done.')
                current_prog += 5
                BKLog.progress_log('BK', 'Erasing', int(current_prog))
                if eraseinfo.flash_otp:
                    self.task_flag(True)
                    flashotpinfo = parse_readinfo_otp(eraseinfo.flash_otp)
                    if flashotpinfo is None:
                        raise Exception('Parse flash OTP info fail.')
                    for info in flashotpinfo:
                        BKLog.i('start erase flash OTP @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        ret = chip_set.erase_chip_flash_security(info[0], info[1])
                        if not ret:
                            raise Exception('erase flash OTP fail.')
                        BKLog.w('erase flash OTP done.')
                    self.task_flag(False)
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.i('Erase complete, all pass.')
                BKLog.i('done.')
            else:
                BKLog.e('Erase fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('erase', result)
            return result
