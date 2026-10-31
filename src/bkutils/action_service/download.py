import time
from typing import List
from ..common import ui_bridge
from ..common.ui_bridge_data import TaskInfo
from .action_base import ActionBase
from ..chip_controller import BaseController
from ..chip_controller import AdvancedController
from ..chip_controller import FlashControllerTsingteng
from ..chip_controller import FlashController
from ..chip_controller.chip_set.base_chip import BaseChip
from ..chip_controller import get_chip_set_with_chip_name
from ..bk_log.log_utils import *
from ..common.common import FLASH_SIZE_DEF, RESET_TYPE, LINKCHECK, BIN_TYPE, BinInfo, DownloadInfo, parse_safe_json_file, parse_writeinfo_otp, parse_writeinfo_efuse, bytes_reverse, parse_device_mac_info, format_expand_data_value_for_log, describe_expand_data_out_of_flash_range
from ..common.version import get_tool_version
from ..common.bk_out_config import BKOTPConfig, BkOutConfig, BkDownloadFlowConfig

class Download(ActionBase):

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
        self.task_list = []
        self.task_index = -1

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

    def combine_base_task_list(self, downloadinfo: DownloadInfo):
        if downloadinfo.bDownloadBin and downloadinfo.pre_erase == 1 and downloadinfo.bAllFlash:
            self.append_task('erase all')
        for expand_data in downloadinfo.expand_data_list:
            self.append_task('write expand data {}'.format(expand_data.name))
        if downloadinfo.bDownloadBin:
            if downloadinfo.pre_erase == 1 and (not downloadinfo.bAllFlash):
                for bininfo in downloadinfo.vecbinInfo:
                    self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
            for bininfo in downloadinfo.vecbinInfo:
                self.append_task('download {}'.format(os.path.basename(bininfo.sFilePath)))
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        ui_bridge.task_list(self.task_list)

    def combine_outter_task_list(self, downloadinfo: DownloadInfo):
        if len(downloadinfo.vecbinInfo) == 0:
            ui_bridge.task_list(self.task_list)
            return
        main_bin = downloadinfo.vecbinInfo[:len(downloadinfo.vecbinInfo) - 1]
        outer_bin = downloadinfo.vecbinInfo[len(downloadinfo.vecbinInfo) - 1]
        if downloadinfo.bDownloadBin and downloadinfo.pre_erase == 1 and downloadinfo.bAllFlash:
            self.append_task('erase all')
        for expand_data in downloadinfo.expand_data_list:
            self.append_task('write expand data {}'.format(expand_data.name))
        if downloadinfo.bDownloadBin:
            if downloadinfo.pre_erase == 1 and (not downloadinfo.bAllFlash):
                for bininfo in main_bin:
                    self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
            for bininfo in main_bin:
                self.append_task('download {}'.format(os.path.basename(bininfo.sFilePath)))
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        if downloadinfo.bDownloadBin:
            self.append_task('erase {}'.format(os.path.basename(outer_bin.sFilePath)))
            self.append_task('download {}'.format(os.path.basename(outer_bin.sFilePath)))
        ui_bridge.task_list(self.task_list)

    def combine_limitedread_task_list(self, downloadinfo: DownloadInfo):
        if downloadinfo.bDownloadBin and downloadinfo.pre_erase == 1 and downloadinfo.bAllFlash:
            self.append_task('erase all')
        if downloadinfo.bDownloadBin:
            if downloadinfo.pre_erase == 1 and (not downloadinfo.bAllFlash):
                for bininfo in downloadinfo.vecbinInfo:
                    self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
            for bininfo in downloadinfo.vecbinInfo:
                self.append_task('download {}'.format(os.path.basename(bininfo.sFilePath)))
        ui_bridge.task_list(self.task_list)

    def combine_bootloader_ota_task_list(self, downloadinfo: DownloadInfo, operate_area: str):
        if downloadinfo.bDownloadBin and downloadinfo.pre_erase == 1 and downloadinfo.bAllFlash:
            self.append_task('erase all')
        for expand_data in downloadinfo.expand_data_list:
            self.append_task('write expand data {}'.format(expand_data.name))
        if downloadinfo.bDownloadBin:
            if downloadinfo.pre_erase == 1 and (not downloadinfo.bAllFlash):
                self.append_task(f'erase manifest {operate_area}')
                self.append_task(f'erase bootloader {operate_area}')
            self.append_task(f'download manifest {operate_area}')
            self.append_task(f'download bootloader {operate_area}')
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        ui_bridge.task_list(self.task_list)

    def combine_secure_task_list(self, downloadinfo: DownloadInfo):
        if downloadinfo.bDownloadBin and downloadinfo.pre_erase == 1 and downloadinfo.bAllFlash:
            self.append_task('erase all')
        for expand_data in downloadinfo.expand_data_list:
            self.append_task('write expand data {}'.format(expand_data.name))
        if downloadinfo.bDownloadBin:
            if downloadinfo.pre_erase == 1 and (not downloadinfo.bAllFlash):
                for bininfo in downloadinfo.vecbinInfo:
                    self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
            for bininfo in downloadinfo.vecbinInfo:
                self.append_task('download {}'.format(os.path.basename(bininfo.sFilePath)))
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        ui_bridge.task_list(self.task_list)

    def combine_reboot_task_list(self, downloadinfo: DownloadInfo):
        """
        Keep UI task list aligned with download_with_reboot_task():
        1) first normal subbin is written directly before reboot (no explicit erase task flag)
        2) remaining bins are processed as erase + download pairs
        3) safe json is written at the end if enabled
        """
        remaining_bins = list(downloadinfo.vecbinInfo)
        if downloadinfo.bDownloadBin and downloadinfo.has_normal_bin and remaining_bins:
            first_bin = remaining_bins[0]
            self.append_task('download {}'.format(os.path.basename(first_bin.sFilePath)))
            remaining_bins = remaining_bins[1:]
        if downloadinfo.bDownloadBin:
            for bininfo in remaining_bins:
                self.append_task('erase {}'.format(os.path.basename(bininfo.sFilePath)))
                self.append_task('download {}'.format(os.path.basename(bininfo.sFilePath)))
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        ui_bridge.task_list(self.task_list)

    def _print_download_info(self, downloadinfo: DownloadInfo):
        self._init_log_level(self.ser.ser.name, self.debug)
        BKLog.w(get_tool_version())
        BKLog.w(f'comport: {self.ser.ser.name}')
        BKLog.w(f'link type: {self.link_check_type}')
        BKLog.w(f'reset type: {self.reset_type}')
        BKLog.w(f'getbus times: {self.getbus_times}')
        BKLog.w(f'reboot: {self.reboot_after_donwload}')
        BKLog.w(f'link key: {self.link_key}')
        BKLog.w(f'work baudrate: {downloadinfo.work_baudrate}')
        BKLog.w(f'erase all: {downloadinfo.bAllFlash}')

    def _check_otp_linkcheck_obj(self, downloadinfo: DownloadInfo):
        if downloadinfo.otp_info or downloadinfo.otp_pm or downloadinfo.efuse_info or downloadinfo.safeinfo.read_safe_config or downloadinfo.safeinfo.write_safe_config or downloadinfo.aes_key:
            if BKOTPConfig.must_use_bl1:
                self.link_check_type = LINKCHECK.BOOTROM
                BkDownloadFlowConfig.allow_change_linkcheck_obj = False

    def _maybe_verify_random_bin(self, linktype):
        from ..common.random_bin_verify import maybe_verify_random_bin_after_get_bus
        maybe_verify_random_bin_after_get_bus(self.ser, linktype, self.random_bin_path)

    def write_expand_data_and_device_info(self, chip_set: BaseChip, downloadinfo: DownloadInfo, current_prog=None, erase_prog=None):
        has_non_bin_data = len(downloadinfo.expand_data_list) > 0 or downloadinfo.bDownloadDeviceName or downloadinfo.bDownloadDeviceID
        all_flash_erased = False
        if has_non_bin_data and downloadinfo.bDownloadBin and (downloadinfo.pre_erase == 1) and downloadinfo.bAllFlash:
            notify_task = len(self.task_list) > 0
            if notify_task:
                self.task_flag(True)
            BKLog.i('erase whole flash.')
            if current_prog is None or erase_prog is None:
                if not chip_set.erase_flash(True, None, None, self.retry):
                    raise Exception('erase whole flash fail.')
            else:
                if not chip_set.erase_flash(True, None, None, self.retry, current_prog, erase_prog):
                    raise Exception('erase whole flash fail.')
                current_prog += erase_prog
            BKLog.i('erase whole flash OK.')
            if notify_task:
                self.task_flag(False)
            all_flash_erased = True
        if len(downloadinfo.expand_data_list) > 0:
            BKLog.i('write expand data.')
            for expand_data in downloadinfo.expand_data_list:
                self.task_flag(True)
                BKLog.i(f'write expand data: {expand_data.name}@0x{expand_data.start_addr:x}@0x{expand_data.length:x} {format_expand_data_value_for_log(expand_data)}.')
                out_of_range = describe_expand_data_out_of_flash_range(expand_data, chip_set._flash_cfg.flash_size)
                if out_of_range:
                    BKLog.e(out_of_range)
                if not chip_set.write_flash_info(expand_data.start_addr, expand_data.value):
                    raise Exception('Write expand data {0} fail.'.format(expand_data.name))
                self.task_flag(False)
            BKLog.w('Write expand data done.')
        if downloadinfo.bDownloadDeviceName:
            BKLog.i(f"write device name: {bytes.decode(downloadinfo.device_name, 'utf-8')}@0x{downloadinfo.device_name_Addr:x}.")
            if not chip_set.write_flash_info(downloadinfo.device_name_Addr, downloadinfo.device_name):
                raise Exception('Write device name to flash fail.')
            BKLog.w('Write device name to flash done.')
        if downloadinfo.bDownloadDeviceID:
            BKLog.i(f'write device ID: {bytes.hex(downloadinfo.device_id)}@0x{downloadinfo.device_id_Addr:x}.')
            devid = downloadinfo.device_id
            if not downloadinfo.bEnableBigEndian:
                devid = bytes_reverse(downloadinfo.device_id)
            if not chip_set.write_flash_info(downloadinfo.device_id_Addr, devid):
                raise Exception('Write device ID to flash fail.')
            BKLog.w('Write device ID to flash done.')
        return (all_flash_erased, current_prog)

    def download_base_task(self, downloadinfo: DownloadInfo):
        self._print_download_info(downloadinfo)
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_base_task_list(downloadinfo)
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                if not chip_set.set_baudrate_correct():
                    raise Exception('set baudrate correct fail.')
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                BKLog.i('check BKAESRDM words in flash...')
                chip_set.check_bkaesrdm_status(retry_cnt=5)
                BKLog.i('check BKAESRDM words in flash OK.')
                th_flash_ctrl = FlashControllerTsingteng(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
                if chip_set._flash_mid == 1274061:
                    if not th_flash_ctrl.tsingteng_flash_fix_mid_incorrect():
                        raise Exception('execute fix flash mid patch fail.')
                    chip_set._flash_mid = 1269965
                if chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_detect_bad_product(downloadinfo.vecbinInfo):
                        raise Exception('execute detect bad flash patch fail.')
                    if not th_flash_ctrl.tsingteng_flash_high_temperature_patch():
                        raise Exception('execute high temperature patch fail.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                (all_flash_erased, current_prog) = self.write_expand_data_and_device_info(chip_set, downloadinfo, current_prog, 40)
                if BkDownloadFlowConfig.develop_set_baudrate_before_align or chip_set.pre_switch_baudrate():
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=downloadinfo.vecbinInfo, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=downloadinfo.vecbinInfo, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    total_prog = 80
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        total_prog = 40
                        prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                        if downloadinfo.bAllFlash:
                            self.task_flag(True)
                            BKLog.i('erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, current_prog, total_prog):
                                raise Exception('erase whole flash fail.')
                            BKLog.i('erase whole flash OK.')
                            current_prog += total_prog
                            self.task_flag(False)
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self.task_flag(True)
                                BKLog.i(f'[{erase_idx}] erase flash.')
                                BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                current_prog += prog_per_bin
                                self.task_flag(False)
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self.task_flag(True)
                        BKLog.i(f'[{write_idx}] write flash.')
                        BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if binfile.bDataPort:
                            if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                                raise Exception('Write flash fail.')
                        elif not chip_set.download_flash_cbus(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                            raise Exception('Write flash by cbus fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                        self.task_flag(False)
                BKLog.w('Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    self.task_flag(True)
                    BKLog.i('write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write safe json fail.')
                    self.task_flag(False)
                    BKLog.w('write safe json done.')
                if downloadinfo.efuse_info:
                    BKLog.i('write chip efuse.')
                    infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
                    if infolist is None:
                        raise Exception('parse efuse info fail.')
                    for info in infolist:
                        if len(info) == 3:
                            (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                        elif len(info) == 2:
                            (ret, msg) = chip_set.write_efuse(info[0], info[1])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                    BKLog.w('Write efuse done.')
                if downloadinfo.otp_info:
                    BKLog.i('write chip OTP.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_info)
                    if infolist is None:
                        raise Exception('parse OTP info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content)
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Write OTP fail.')
                    BKLog.w('Write OTP done.')
                if downloadinfo.otp_pm:
                    BKLog.i('set OTP permission.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
                    if infolist is None:
                        raise Exception('parse OTP permission info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Set OTP permission fail.')
                    BKLog.w('Set OTP permission done.')
                if downloadinfo.flash_otp:
                    BKLog.i('write flash OTP data.')
                    infolist = parse_writeinfo_otp(downloadinfo.flash_otp)
                    if infolist is None:
                        raise Exception('parse flash OTP info fail.')
                    for info in infolist:
                        ret = chip_set.write_chip_flash_security(info[1], bytes.fromhex(info[0]))
                        if not ret:
                            raise Exception('write flash OTP fail.')
                    BKLog.w('write flash OTP done.')
                if (chip_set._flash_mid == 1269965 or chip_set._flash_mid == 1335501 or chip_set._flash_mid == 1401067) and (not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid)):
                    raise Exception('Execute flash scratch solution fail.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                BKLog.progress_log('BK', 'Downloading', 100)
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_base_task', result)
            return result

    def download_common_pre_action(self, downloadinfo: DownloadInfo, base_controller: BaseController, all_bin_info: List[BinInfo], find_sec_id: bool=False, current_prog: float=1):
        """Prepare a reusable shared download session."""
        self._check_otp_linkcheck_obj(downloadinfo)
        (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
        if not tmp_res:
            raise Exception('get bus fail.')
        self._maybe_verify_random_bin(linktype)
        time.sleep(0.1)
        current_prog += 5
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        chip_set = self._get_chip_set(find_sec_id)
        chip_set.update_serial_instance(self.ser)
        if not chip_set.set_baudrate_correct():
            raise Exception('set baudrate correct fail.')
        BKLog.i('parse flash info...')
        if not chip_set.parse_flash_info():
            raise Exception('parse flash info fail.')
        BKLog.i('check BKAESRDM words in flash...')
        chip_set.check_bkaesrdm_status(retry_cnt=5)
        BKLog.i('check BKAESRDM words in flash OK.')
        th_flash_ctrl = FlashControllerTsingteng(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
        if chip_set._flash_mid == 1274061:
            if not th_flash_ctrl.tsingteng_flash_fix_mid_incorrect():
                raise Exception('execute fix flash mid patch fail.')
            chip_set._flash_mid = 1269965
        if chip_set._flash_mid == 1401067:
            if not th_flash_ctrl.tsingteng_flash_detect_bad_product(all_bin_info):
                raise Exception('execute detect bad flash patch fail.')
            if not th_flash_ctrl.tsingteng_flash_high_temperature_patch():
                raise Exception('execute high temperature patch fail.')
        current_prog += 5
        BKLog.progress_log('BK', 'Downloading', int(current_prog))
        if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
            BKLog.i('unprotect flash...')
            if not chip_set.un_protect_flash(protect=False):
                raise Exception('unprotect flash fail.')
            BKLog.i('unprotect flash OK.')
        return (chip_set, th_flash_ctrl, current_prog)

    def download_common_post_action(self, downloadinfo: DownloadInfo, chip_set: BaseChip, th_flash_ctrl: FlashControllerTsingteng, current_prog: float):
        if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
            BKLog.i('protect flash...')
            if not chip_set.un_protect_flash(protect=True):
                BKLog.e('protect flash fail.')
            else:
                BKLog.i('protect flash OK.')
        if downloadinfo.safeinfo.write_safe_config:
            self.task_flag(True)
            BKLog.i('write safe json content.')
            if downloadinfo.aes_key:
                for sedata in downloadinfo.safeinfo.security_data_list:
                    if sedata.name.find('aes_key') != -1:
                        sedata.data = downloadinfo.aes_key
            (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
            if not ret:
                BKLog.e(msg)
                raise Exception('Write safe json fail.')
            self.task_flag(False)
            BKLog.w('write safe json done.')
        if downloadinfo.efuse_info:
            BKLog.i('write chip efuse.')
            infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
            if infolist is None:
                raise Exception('parse efuse info fail.')
            for info in infolist:
                if len(info) == 3:
                    (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write efuse fail.')
                elif len(info) == 2:
                    (ret, msg) = chip_set.write_efuse(info[0], info[1])
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write efuse fail.')
            BKLog.w('Write efuse done.')
        if downloadinfo.otp_info:
            BKLog.i('write chip OTP.')
            infolist = parse_writeinfo_otp(downloadinfo.otp_info)
            if infolist is None:
                raise Exception('parse OTP info fail.')
            for info in infolist:
                (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content)
                if not ret:
                    BKLog.e(msg)
                    raise Exception('Write OTP fail.')
            BKLog.w('Write OTP done.')
        if downloadinfo.otp_pm:
            BKLog.i('set OTP permission.')
            infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
            if infolist is None:
                raise Exception('parse OTP permission info fail.')
            for info in infolist:
                (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                if not ret:
                    BKLog.e(msg)
                    raise Exception('Set OTP permission fail.')
            BKLog.w('Set OTP permission done.')
        if downloadinfo.flash_otp:
            BKLog.i('write flash OTP data.')
            infolist = parse_writeinfo_otp(downloadinfo.flash_otp)
            if infolist is None:
                raise Exception('parse flash OTP info fail.')
            for info in infolist:
                ret = chip_set.write_chip_flash_security(info[1], bytes.fromhex(info[0]))
                if not ret:
                    raise Exception('write flash OTP fail.')
            BKLog.w('write flash OTP done.')
        if chip_set._flash_mid in [1269965, 1335501, 1401067] and (not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid)):
            raise Exception('Execute flash scratch solution fail.')
        current_prog += 5
        BKLog.progress_log('BK', 'Downloading', int(current_prog))
        BKLog.progress_log('BK', 'Downloading', 100)
        return current_prog

    def _combine_bl1_secure_task_list(self, downloadinfo: DownloadInfo, extension_bins: List[BinInfo], fixed_bins: List[BinInfo]):
        self.task_list = []
        self.task_index = -1
        if extension_bins:
            extension_name = os.path.basename(extension_bins[0].sFilePath)
            self.append_task('download {}'.format(extension_name or 'BL1 secure extension'))
        for bininfo in fixed_bins:
            fixed_name = os.path.basename(bininfo.sFilePath)
            display_name = fixed_name or 'BL1 secure fixed'
            self.append_task('erase {}'.format(display_name))
            self.append_task('download {}'.format(display_name))
        if downloadinfo.safeinfo.write_safe_config:
            self.append_task('write safe json')
        ui_bridge.task_list(self.task_list)

    def _ensure_bl1_magic_word(self, chip_set: BaseChip, mg_addr: int, mg_word: bytes, version_info: bytes=None):
        read_bytes = chip_set.read_and_check_sector(0, 10)
        if read_bytes is None:
            raise Exception('Read flash fail, address:0x0, length:0x1000.')
        version_addr = mg_addr + 10
        magic_matches = read_bytes[mg_addr:mg_addr + 5] == mg_word
        version_matches = version_info is None or read_bytes[version_addr:version_addr + 16] == version_info
        if magic_matches and version_matches:
            return
        wr_buffer = bytearray(read_bytes)
        if not magic_matches:
            BKLog.i(f'replace BL1 magic word at 0x{mg_addr:x}.')
            wr_buffer[mg_addr:mg_addr + 5] = mg_word
        if version_info is not None and (not version_matches):
            BKLog.i(f'write BL1 version info at 0x{version_addr:x}: {version_info.hex()}.')
            wr_buffer[version_addr:version_addr + 16] = version_info
        flash_ctrl = FlashController(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
        if not flash_ctrl.erase_sector(0):
            raise Exception('Erase flash fail, address:0x0, length:0x1000.')
        if not chip_set.write_and_check_sector(bytes(wr_buffer), 0):
            raise Exception('Write flash fail, address:0x0, length:0x1000.')

    def _get_bl1_bins_version_and_magic_word(self, fixed_bins: List[BinInfo]):
        """Extract the 16-byte version following BEKEN/BK.SB in fixed bins."""
        magic_words = (b'BEKEN', b'BK.SB', b'BK\x00SB')
        for binfile in fixed_bins:
            for magic_addr in [256, 272]:
                version_addr = magic_addr + 10
                if len(binfile.pfile) < version_addr + 16:
                    continue
                if binfile.pfile[magic_addr:magic_addr + 5] in magic_words:
                    version_info = bytes(binfile.pfile[version_addr:version_addr + 16])
                    BKLog.i(f'find BL1 secure fixed version at 0x{version_addr:x}: {version_info.hex()}.')
                    return (magic_addr, binfile.pfile[magic_addr:magic_addr + 5], version_info)
        raise Exception('Cannot find BEKEN/BK.SB and 16-byte version info in BL1 secure fixed bin.')

    def download_bl1_secure_extension_flash(self, downloadinfo: DownloadInfo, extension_bins: List[BinInfo], base_controller: BaseController, chip_set: BaseChip, current_prog: float, progress_span: float):
        """Write BL1DLV41 and reconnect for the following download stage."""
        if not extension_bins:
            raise Exception('BL1 secure extension bin is empty.')
        extension_bin = extension_bins[0]
        BKLog.i('write BL1 secure extension bin before reboot.')
        BKLog.i(f'start: 0x{extension_bin.iStartAddress:x}.')
        BKLog.i(f'length: 0x{extension_bin.iFileLength:x}.')
        if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
            raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
        self.task_flag(True)
        try:
            if not chip_set.download_flash_cbus(extension_bin.pfile, extension_bin.iStartAddress, extension_bin.iFileLength + 4096, extension_bin.iStartAddress, self.retry, self.reset_type, self.link_check_type, current_prog, progress_span):
                raise Exception('Write BL1 secure extension flash by cbus fail.')
        finally:
            self.task_flag(False)
        (magic_addr, mg_word, version_info) = self._get_bl1_bins_version_and_magic_word(extension_bins)
        self._ensure_bl1_magic_word(chip_set, magic_addr, mg_word)
        BKLog.i('BL1 secure extension write done, reboot and reconnect bus...')
        base_controller.do_reboot()
        time.sleep(0.5)
        if not base_controller.reconnect_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_retry_count=self.getbus_times, link_key=self.link_key):
            raise Exception('reconnect bus after BL1 secure extension fail.')
        chip_set.update_serial_instance(self.ser)
        return current_prog + progress_span

    def download_bl1_secure_fixed_flash(self, downloadinfo: DownloadInfo, fixed_bins: List[BinInfo], chip_set: BaseChip, current_prog: float, progress_span: float):
        """Erase and write all BL1DLV40 sub-images."""
        if not fixed_bins:
            raise Exception('BL1 secure fixed bin is empty.')
        BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
        if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
            raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
        prog_per_action = progress_span / (len(fixed_bins) * 2)
        for (index, binfile) in enumerate(fixed_bins):
            self.task_flag(True)
            try:
                BKLog.i(f'[{index}] erase flash.')
                BKLog.i(f'[{index}] start: 0x{binfile.iStartAddress:x}.')
                BKLog.i(f'[{index}] length: 0x{binfile.iFileLength:x}.')
                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_action):
                    raise Exception('erase flash fail.')
            finally:
                self.task_flag(False)
            current_prog += prog_per_action
            self.task_flag(True)
            try:
                BKLog.i(f'[{index}] write flash.')
                if binfile.bDataPort:
                    write_ok = chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type, current_prog, prog_per_action)
                else:
                    write_ok = chip_set.download_flash_cbus(binfile.pfile, binfile.iPartition_start, binfile.iPartition_size, binfile.iStartAddress, self.retry, self.reset_type, self.link_check_type, current_prog, prog_per_action)
                if not write_ok:
                    raise Exception('Write BL1 secure fixed flash fail.')
            finally:
                self.task_flag(False)
            current_prog += prog_per_action
        (magic_addr, mg_word, version_info) = self._get_bl1_bins_version_and_magic_word(fixed_bins)
        self._ensure_bl1_magic_word(chip_set, magic_addr, mg_word, version_info=version_info)
        BKLog.w('Write BL1 secure fixed flash done.')
        return current_prog

    def _run_bl1_secure_task(self, downloadinfo: DownloadInfo, extension_bins: List[BinInfo], fixed_bins: List[BinInfo], task_name: str):
        self._print_download_info(downloadinfo)
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', current_prog)
        self._combine_bl1_secure_task_list(downloadinfo, extension_bins, fixed_bins)
        try:
            try:
                all_bin_info = list(extension_bins) + list(fixed_bins)
                (chip_set, th_flash_ctrl, current_prog) = self.download_common_pre_action(downloadinfo, base_controller, all_bin_info, False, current_prog)
                middle_progress = 84.0
                extension_weight = extension_bins[0].iFileLength if extension_bins else 0
                fixed_weight = sum((binfile.iFileLength * 2 for binfile in fixed_bins))
                total_weight = extension_weight + fixed_weight
                extension_progress = middle_progress * extension_weight / total_weight if extension_weight else 0
                fixed_progress = middle_progress - extension_progress
                if extension_bins:
                    current_prog = self.download_bl1_secure_extension_flash(downloadinfo, extension_bins, base_controller, chip_set, current_prog, extension_progress)
                if fixed_bins:
                    current_prog = self.download_bl1_secure_fixed_flash(downloadinfo, fixed_bins, chip_set, current_prog, fixed_progress)
                self.download_common_post_action(downloadinfo, chip_set, th_flash_ctrl, current_prog)
                result = True
            except Exception as e:
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            elapsed_time = time.time() - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag(task_name, result)
        return result

    def download_bl1_secure_extension_task(self, downloadinfo: DownloadInfo):
        return self._run_bl1_secure_task(downloadinfo, extension_bins=downloadinfo.vecbinInfo, fixed_bins=[], task_name='download_bl1_secure_extension_task')

    def download_bl1_secure_fixed_task(self, downloadinfo: DownloadInfo):
        return self._run_bl1_secure_task(downloadinfo, extension_bins=[], fixed_bins=downloadinfo.vecbinInfo, task_name='download_bl1_secure_fixed_task')

    def download_mixed_task(self, downloadinfo: DownloadInfo):
        """Select and execute a download flow for mixed bin types."""
        mixed_types = {single_type_bin.binType for single_type_bin in downloadinfo.mixedBinInfo}
        bl1_secure_types = {BIN_TYPE.TYPE_BL1_SECURE_EXTENSION, BIN_TYPE.TYPE_BL1_SECURE_FIXED}
        if mixed_types == bl1_secure_types:
            return self.download_with_reboot_task(downloadinfo)
        type_names = ', '.join(sorted((bin_type.name for bin_type in mixed_types)))
        raise Exception(f'Unsupported mixed bin types: {type_names}')

    def download_with_reboot_task(self, downloadinfo: DownloadInfo):
        extension_bins = []
        fixed_bins = []
        for single_type_bin in downloadinfo.mixedBinInfo:
            if single_type_bin.binType == BIN_TYPE.TYPE_BL1_SECURE_EXTENSION:
                extension_bins.extend(single_type_bin.binList)
            elif single_type_bin.binType == BIN_TYPE.TYPE_BL1_SECURE_FIXED:
                fixed_bins.extend(single_type_bin.binList)
        if not extension_bins or not fixed_bins:
            raise Exception('BL1 secure mixed task requires extension and fixed bins.')
        return self._run_bl1_secure_task(downloadinfo, extension_bins=extension_bins, fixed_bins=fixed_bins, task_name='download_with_reboot_task')

    def download_limited_read_task(self, downloadinfo: DownloadInfo):
        self._print_download_info(downloadinfo)
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_limitedread_task_list(downloadinfo)
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set(find_sec_id=False)
                chip_set.update_serial_instance(self.ser)
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                BKLog.i('check BKAESRDM words in flash...')
                chip_set.check_bkaesrdm_status(retry_cnt=5)
                BKLog.i('check BKAESRDM words in flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    total_prog = 80
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1:
                        total_prog = 40
                        prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                        if downloadinfo.bAllFlash:
                            self.task_flag(True)
                            BKLog.i('erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, current_prog, total_prog):
                                raise Exception('erase whole flash fail.')
                            BKLog.i('erase whole flash OK.')
                            current_prog += total_prog
                            self.task_flag(False)
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self.task_flag(True)
                                BKLog.i(f'[{erase_idx}] erase flash.')
                                BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                current_prog += prog_per_bin
                                self.task_flag(False)
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self.task_flag(True)
                        BKLog.i(f'[{write_idx}] write flash.')
                        BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                        self.task_flag(False)
                BKLog.w('Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                BKLog.progress_log('BK', 'Downloading', 100)
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_limited_read_task', result)
            return result

    def download_with_outter_flash_task(self, downloadinfo: DownloadInfo):
        self._print_download_info(downloadinfo)
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        main_bin = downloadinfo.vecbinInfo[:len(downloadinfo.vecbinInfo) - 1]
        outer_bin = downloadinfo.vecbinInfo[len(downloadinfo.vecbinInfo) - 1]
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_outter_task_list(downloadinfo)
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                BKLog.i('check BKAESRDM words in flash...')
                chip_set.check_bkaesrdm_status(retry_cnt=5)
                BKLog.i('check BKAESRDM words in flash OK.')
                ret = chip_set.read_and_check_sector(8384512)
                if ret is None:
                    raise Exception('read flash @0x7ff000 fail.')
                BKLog.w(f'Device MAC:{bytes.hex(bytes(ret[:6]))}')
                th_flash_ctrl = FlashControllerTsingteng(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
                if chip_set._flash_mid == 1274061:
                    if not th_flash_ctrl.tsingteng_flash_fix_mid_incorrect():
                        raise Exception('execute fix flash mid patch fail.')
                    chip_set._flash_mid = 1269965
                if chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_detect_bad_product(main_bin):
                        raise Exception('execute detect bad flash patch fail.')
                    if not th_flash_ctrl.tsingteng_flash_high_temperature_patch():
                        raise Exception('execute high temperature patch fail.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                erase_prog = 40 / len(downloadinfo.vecbinInfo) * len(main_bin) if downloadinfo.bDownloadBin else None
                (all_flash_erased, current_prog) = self.write_expand_data_and_device_info(chip_set, downloadinfo, current_prog, erase_prog)
                if BkDownloadFlowConfig.develop_set_baudrate_before_align:
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=main_bin, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=main_bin, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    total_prog = 80
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        total_prog = 40
                        prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                        if downloadinfo.bAllFlash:
                            self.task_flag(True)
                            BKLog.i('erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, current_prog, prog_per_bin * len(main_bin)):
                                raise Exception('erase whole flash fail.')
                            BKLog.i('erase whole flash OK.')
                            current_prog += prog_per_bin * len(main_bin)
                            self.task_flag(False)
                        else:
                            erase_idx = 0
                            for binfile in main_bin:
                                self.task_flag(True)
                                BKLog.w(f'[{erase_idx}] erase flash.')
                                BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                current_prog += prog_per_bin
                                self.task_flag(False)
                    time.sleep(0.001)
                    write_idx = 0
                    for binfile in main_bin:
                        self.task_flag(True)
                        if binfile.iStartAddress & 4095:
                            binfile.iStartAddress = int((binfile.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                        BKLog.w(f'[{write_idx}] write flash.')
                        BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, self.reset_type == RESET_TYPE.DTR_RTS, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                        self.task_flag(False)
                BKLog.w('Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    self.task_flag(True)
                    BKLog.i('write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write safe json fail.')
                    self.task_flag(False)
                    BKLog.w('write safe json done.')
                if chip_set._flash_mid == 1269965 or chip_set._flash_mid == 1335501 or chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid):
                        raise Exception('Execute flash scratch solution fail.')
                time.sleep(0.001)
                BKLog.w('OUTTER FLASH OPERATION')
                BKLog.i('enter write outter flash mode...')
                if not chip_set.reboot_and_enter_write_outter_flash_mode(self.reset_type):
                    raise Exception('enter write outter flash mode fail.')
                time.sleep(0.2)
                BKLog.i('parse outter flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse outter flash info fail.')
                if BkDownloadFlowConfig.develop_set_baudrate_before_align:
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=[outer_bin], for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        BKLog.i('align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=[outer_bin], for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    self.task_flag(True)
                    if downloadinfo.bAllFlash:
                        BKLog.i('erase whole outter flash.')
                        if not chip_set.erase_flash(True, None, None, self.retry, current_prog, prog_per_bin):
                            raise Exception('erase whole outter flash fail.')
                        BKLog.i('erase whole outter flash OK.')
                        current_prog += prog_per_bin
                    else:
                        BKLog.w('[outter] erase flash.')
                        BKLog.i(f'[outter] start: 0x{outer_bin.iStartAddress:x}.')
                        BKLog.i(f'[outter] length: 0x{outer_bin.iFileLength:x}.')
                        if not chip_set.erase_flash(False, outer_bin.iStartAddress, outer_bin.iStartAddress + outer_bin.iFileLength, self.retry, current_prog, prog_per_bin):
                            raise Exception('erase outter flash fail.')
                        current_prog += prog_per_bin
                    self.task_flag(False)
                    time.sleep(0.001)
                    self.task_flag(True)
                    BKLog.w('[outter] write flash.')
                    BKLog.i(f'[outter] start: 0x{outer_bin.iStartAddress:x}.')
                    BKLog.i(f'[outter] length: 0x{outer_bin.iFileLength:x}.')
                    if not chip_set.download_flash(outer_bin.pfile, outer_bin.iStartAddress, self.retry, False, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                        raise Exception('Write outter flash fail.')
                    current_prog += prog_per_bin
                    self.task_flag(False)
                BKLog.w('Write outter flash done.')
                time.sleep(0.001)
                if downloadinfo.custom_data:
                    (ret, bydata, addr, oplen) = parse_device_mac_info(downloadinfo.custom_data)
                    if not ret:
                        raise Exception('Input custom data format error.')
                    self.ser.reset(115200)
                    if not base_controller.reconnect_bus(reset_type=self.reset_type, linkcheck_obj=None, reset_baudrate=115200, max_retry_count=60, link_key=self.link_key):
                        raise Exception('reconnect bus fail.')
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                    BKLog.i(f'write custom data: {bytes.hex(bydata)} @0x{addr:x}.')
                    if not chip_set.write_flash_info(addr, bydata):
                        raise Exception('Write custom data to flash fail.')
                    BKLog.w('Write custom data to flash done.')
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            if result and downloadinfo.check_words != '':
                tmp = downloadinfo.check_words.split('@')
                self.ser.reset(int(tmp[1]))
                result = False
                BKLog.w(f'start check key words {tmp[0]}.')
                retry_cnt = 5
                while retry_cnt > 0:
                    start_t = time.time()
                    bcr = b''
                    while time.time() - start_t < 3:
                        rbuf = self.ser.ser.read_all()
                        if rbuf:
                            rlist = rbuf.split(b'\r\n')
                            if len(rlist) == 1:
                                bcr = bcr + rlist[0]
                            else:
                                for idx in range(len(rlist)):
                                    if idx == 0:
                                        sub_rbuf = bcr + rlist[idx]
                                        bcr = b''
                                    elif idx == len(rlist) - 1:
                                        bcr = rlist[idx]
                                    else:
                                        sub_rbuf = rlist[idx]
                                    if sub_rbuf.find(tmp[0].encode('utf-8')) != -1:
                                        result = True
                                        break
                        if result:
                            break
                    if result:
                        break
                    base_controller.do_reset(reset_type=self.reset_type, baudrate=460800)
                    retry_cnt -= 1
                if not result:
                    BKLog.e(f'check key words {tmp[0]} fail.')
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.w(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_with_outter_flash_task', result)
            return result

    def download_secure_task(self, downloadinfo: DownloadInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_secure_task_list(downloadinfo)
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                BKLog.i('check BKAESRDM words in flash...')
                chip_set.check_bkaesrdm_status(retry_cnt=5)
                BKLog.i('check BKAESRDM words in flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                (all_flash_erased, current_prog) = self.write_expand_data_and_device_info(chip_set, downloadinfo, current_prog, 40)
                BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if linktype == LINKCHECK.BOOTROM:
                    BKLog.i('check aes key permission...')
                    ret = chip_set.check_aes_key_otp_permission()
                    if ret is False:
                        raise Exception('check aes key permission fail.')
                    if ret == 0:
                        BKLog.i('aes key permission is not NA.')
                        ret = chip_set.check_aes_key_otp_data()
                        if ret is False:
                            raise Exception('check aes key data fail.')
                        if ret == 0:
                            BKLog.i('aes key data is empty.')
                elif linktype == LINKCHECK.BL2:
                    cnt = 10
                    while cnt > 0:
                        ret = self.bl2_version_upgrade(chip_set, downloadinfo.vecbinInfo, cnt != 10)
                        if ret is False:
                            raise Exception('upgrade bl2 fail.')
                        if ret is None:
                            break
                        cnt -= 1
                    downloadinfo.vecbinInfo[2].bCheck = False
                    downloadinfo.vecbinInfo[3].bCheck = False
                    downloadinfo.vecbinInfo[4].bCheck = False
                    downloadinfo.vecbinInfo[7].bCheck = False
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                if downloadinfo.bDownloadBin:
                    total_prog = 40
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased) and downloadinfo.bAllFlash:
                        self.task_flag(True)
                        BKLog.i('erase whole flash.')
                        if not chip_set.erase_flash(True, None, None, self.retry, current_prog, total_prog):
                            raise Exception('erase whole flash fail.')
                        BKLog.i('erase whole flash OK.')
                        self.task_flag(False)
                    elif downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        erase_idx = 0
                        for binfile in downloadinfo.vecbinInfo:
                            self.task_flag(True)
                            BKLog.i(f'[{erase_idx}] erase flash.')
                            BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                            BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                            if binfile.bCheck and binfile.bDataPort:
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                            erase_idx += 1
                            current_prog += prog_per_bin
                            self.task_flag(False)
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self.task_flag(True)
                        if binfile.bCheck:
                            BKLog.i(f'[{write_idx}] write flash.')
                            BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                            BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                            if binfile.bDataPort:
                                if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, link_type=linktype, cprog=current_prog, sprog=prog_per_bin):
                                    raise Exception('Write flash fail.')
                            elif not chip_set.download_flash_cbus(binfile.pfile, binfile.iPartition_start, binfile.iPartition_size, binfile.iStartAddress, self.retry, self.reset_type, link_type=linktype, cprog=current_prog, sprog=prog_per_bin):
                                raise Exception('Write flash fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                        self.task_flag(False)
                    BKLog.w('Write flash done.')
                if downloadinfo.safeinfo.write_safe_config:
                    self.task_flag(True)
                    BKLog.i('write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write safe json fail.')
                    self.task_flag(False)
                    BKLog.w('write safe json done.')
                if downloadinfo.efuse_info:
                    BKLog.i('write chip efuse.')
                    infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
                    if infolist is None:
                        raise Exception('parse efuse info fail.')
                    for info in infolist:
                        if len(info) == 3:
                            (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                        elif len(info) == 2:
                            (ret, msg) = chip_set.write_efuse(info[0], info[1])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                    BKLog.w('Write efuse done.')
                if downloadinfo.otp_info:
                    BKLog.i('write chip OTP.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_info)
                    if infolist is None:
                        raise Exception('parse OTP info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content, downloadinfo.bEnableBigEndian)
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Write OTP fail.')
                    BKLog.w('Write OTP done.')
                if downloadinfo.otp_pm:
                    BKLog.i('set OTP permission.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
                    if infolist is None:
                        raise Exception('parse OTP permission info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Set OTP permission fail.')
                    BKLog.w('Set OTP permission done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName:
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_secure_task', result)
            return result

    def download_bootloader_ota(self, downloadinfo: DownloadInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        try:
            try:
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                th_flash_ctrl = FlashControllerTsingteng(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
                if chip_set._flash_mid == 1274061:
                    if not th_flash_ctrl.tsingteng_flash_fix_mid_incorrect():
                        raise Exception('execute fix flash mid patch fail.')
                    chip_set._flash_mid = 1269965
                if chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_detect_bad_product(downloadinfo.vecbinInfo):
                        raise Exception('execute detect bad flash patch fail.')
                    if not th_flash_ctrl.tsingteng_flash_high_temperature_patch():
                        raise Exception('execute high temperature patch fail.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if BaseController.link_check_obj is not None and BaseController.link_check_obj == LINKCHECK.BL2:
                    advctrl = AdvancedController(serial_instance=self.ser)
                    partition_flag = advctrl.read_bootloader_partition_flag()
                    if partition_flag is None:
                        raise Exception('read bootloader partition flag fail.')
                    operate_area = 'A' if partition_flag == 2 else 'B'
                    running_area = 'B' if operate_area == 'A' else 'A'
                    BKLog.i(f'bootloader is running in {running_area},load {operate_area}.')
                else:
                    operate_area = 'A'
                indices = [0, 2] if operate_area == 'A' else [1, 3]
                selected_bins = [downloadinfo.vecbinInfo[i] for i in indices]
                downloadinfo.vecbinInfo = selected_bins
                self.combine_bootloader_ota_task_list(downloadinfo, operate_area=operate_area)
                (all_flash_erased, _) = self.write_expand_data_and_device_info(chip_set, downloadinfo)
                if downloadinfo.bDownloadBin:
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        if downloadinfo.bAllFlash:
                            self.task_flag(True)
                            BKLog.i('erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry):
                                raise Exception('erase whole flash fail.')
                            BKLog.i('erase whole flash OK.')
                            self.task_flag(False)
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self.task_flag(True)
                                BKLog.i(f'[{erase_idx}] erase flash.')
                                BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                self.task_flag(False)
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self.task_flag(True)
                        if binfile.iStartAddress & 4095:
                            binfile.iStartAddress = int((binfile.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                        BKLog.i(f'[{write_idx}] write flash.')
                        BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, self.reset_type == RESET_TYPE.DTR_RTS, self.reset_type, self.link_check_type):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                        self.task_flag(False)
                BKLog.w('Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        BKLog.e('protect flash fail.')
                    else:
                        BKLog.i('protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    self.task_flag(True)
                    BKLog.i('write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Write safe json fail.')
                    self.task_flag(False)
                    BKLog.w('write safe json done.')
                if downloadinfo.efuse_info:
                    BKLog.i('write chip efuse.')
                    infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
                    if infolist is None:
                        raise Exception('parse efuse info fail.')
                    for info in infolist:
                        if len(info) == 3:
                            (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                        elif len(info) == 2:
                            (ret, msg) = chip_set.write_efuse(info[0], info[1])
                            if not ret:
                                BKLog.e(msg)
                                raise Exception('Write efuse fail.')
                    BKLog.w('Write efuse done.')
                if downloadinfo.otp_info:
                    BKLog.i('write chip OTP.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_info)
                    if infolist is None:
                        raise Exception('parse OTP info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content)
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Write OTP fail.')
                    BKLog.w('Write OTP done.')
                if downloadinfo.otp_pm:
                    BKLog.i('set OTP permission.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
                    if infolist is None:
                        raise Exception('parse OTP permission info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                        if not ret:
                            BKLog.e(msg)
                            raise Exception('Set OTP permission fail.')
                    BKLog.w('Set OTP permission done.')
                if chip_set._flash_mid == 1269965 or chip_set._flash_mid == 1335501 or chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid):
                        raise Exception('Execute flash scratch solution fail.')
                if BaseController.link_check_obj is not None and BaseController.link_check_obj == LINKCHECK.BL2:
                    advctrl = AdvancedController(serial_instance=self.ser)
                    if not advctrl.write_bootloader_ota_success_flag():
                        raise Exception('Write bootloader ota success flag fail.')
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_base_task', result)
            return result

    def bl2_version_upgrade(self, chip_set: BaseChip, binlist: List[BinInfo], ifreconnect=False):
        new_ver = binlist[2].pfile[4] + (binlist[2].pfile[5] << 8) + (binlist[2].pfile[6] << 16) + (binlist[2].pfile[7] << 24)
        BKLog.i(f'new version is: 0x{new_ver:x}')
        bl2a_start = binlist[4].iStartAddress
        bl2a_len = binlist[4].iFileLength
        bl2b_len = binlist[7].iFileLength
        manifesta_start = binlist[2].iStartAddress
        manifestb_start = binlist[3].iStartAddress
        bl2b_start = binlist[7].iStartAddress
        BKLog.i(f'bl2a_start is: 0x{bl2a_start:x}')
        BKLog.i(f'bl2a_len is: 0x{bl2a_len:x}')
        BKLog.i(f'bl2b_start is: 0x{bl2b_start:x}')
        BKLog.i(f'bl2b_len is: 0x{bl2b_len:x}')
        BKLog.i(f'bl2b_buf_len is: 0x{len(binlist[7].pfile):x}')
        BKLog.i(f'manifesta_start is: 0x{manifesta_start:x}')
        BKLog.i(f'manifesta_len is: 0x{binlist[2].iFileLength:x}')
        BKLog.i(f'manifestb_start is: 0x{manifestb_start:x}')
        BKLog.i(f'manifestb_len is: 0x{binlist[3].iFileLength:x}')
        baudrate_backup = self.ser.baudrate
        basectrl = BaseController(serial_instance=self.ser)
        if ifreconnect:
            if not basectrl.reconnect_bus(reset_type=RESET_TYPE.MULTI, linkcheck_obj=None, max_retry_count=20, link_key=self.link_key):
                BKLog.e('reconnect bus fail.')
                return False
            time.sleep(0.1)
            if not chip_set.set_baudrate(baudrate=baudrate_backup, delay_ms=20):
                BKLog.e('set baudrate {0} fail.'.format(baudrate_backup))
                return False
        cur_ver = chip_set.read_bl2_version()
        if not cur_ver:
            BKLog.e('read bl2 current version fail.')
            return False
        BKLog.i(f'current version is: 0x{cur_ver:x}')
        if cur_ver != 4294967295 and new_ver <= cur_ver:
            return
        advctrl = AdvancedController(serial_instance=self.ser)
        bootflag = advctrl.start_stop_bl2_upgrade(True)
        if bootflag is False:
            BKLog.e('start bl2 upgrade fail.')
            return False
        BKLog.i(f'bootflag is: {bootflag}')
        if not chip_set.un_protect_flash(protect=False):
            BKLog.e('unprotect flash fail.')
            return False
        if bootflag == 2:
            BKLog.i('start write flash for manifest_a.')
            if not chip_set.erase_flash(full_erase=False, start_addr=manifesta_start, end_addr=manifesta_start + 4096, align_addr=True):
                BKLog.e('erase flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.download_flash(wbuf=binlist[2].pfile, start_addr=manifesta_start):
                BKLog.e('write flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.erase_flash(full_erase=False, start_addr=bl2a_start, end_addr=bl2a_start + bl2a_len, align_addr=True):
                BKLog.e('erase flash fail.')
                return False
            time.sleep(0.1)
            BKLog.i('start write flash for bl2_a.')
            if not chip_set.download_flash(wbuf=binlist[4].pfile, start_addr=bl2a_start, reset_type=RESET_TYPE.DTR_RTS, link_type=self.link_check_type):
                BKLog.i('write flash for bl2_a fail.')
                return False
        elif bootflag == 1:
            BKLog.i('start write flash for manifest_b.')
            if not chip_set.erase_flash(full_erase=False, start_addr=manifestb_start, end_addr=manifestb_start + 4096, align_addr=True):
                BKLog.e('erase flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.download_flash(wbuf=binlist[3].pfile, start_addr=manifestb_start):
                BKLog.e('write flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.erase_flash(full_erase=False, start_addr=bl2b_start, end_addr=bl2b_start + bl2b_len, align_addr=True):
                BKLog.e('erase flash fail.')
                return False
            time.sleep(0.1)
            BKLog.i('start write flash for bl2_b.')
            if not chip_set.download_flash(wbuf=binlist[7].pfile, start_addr=bl2b_start, reset_type=RESET_TYPE.DTR_RTS, link_type=self.link_check_type):
                BKLog.i('write flash for bl2_b fail.')
                return False
        else:
            return False
        if not advctrl.start_stop_bl2_upgrade(start_stop=False):
            BKLog.e('stop bl2 upgrade fail.')
            return False
        time.sleep(0.01)
        basectrl.do_reboot()
        return True

    def download_flash_cbus_task(self, downloadinfo: DownloadInfo):
        self._print_download_info(downloadinfo)
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_base_task_list(downloadinfo)
                self._check_otp_linkcheck_obj(downloadinfo)
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
                chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.verify_product_id and downloadinfo.bDownloadBin:
                    BKLog.i('verifying chip product id...')
                    chip_set.verify_chip_product_id(downloadinfo.vecbinInfo[0])
                    BKLog.i('verifying chip product id OK.')
                BKLog.i('parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    BKLog.i('unprotect flash OK.')
                BKLog.i('set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    total_prog = 80
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1:
                        total_prog = 40
                        prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                        if downloadinfo.bAllFlash:
                            self.task_flag(True)
                            BKLog.i('erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, current_prog, total_prog):
                                raise Exception('erase whole flash fail.')
                            BKLog.i('erase whole flash OK.')
                            current_prog += total_prog
                            self.task_flag(False)
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self.task_flag(True)
                                if binfile.iFileLength & 4095:
                                    binfile.iFileLength = int((binfile.iFileLength + 4095) / 4096) * 4096
                                BKLog.i(f'[{erase_idx}] erase flash.')
                                BKLog.i(f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                BKLog.i(f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                current_prog += prog_per_bin
                                self.task_flag(False)
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self.task_flag(True)
                        BKLog.i(f'[{write_idx}] write flash cbus.')
                        BKLog.i(f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        BKLog.i(f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash_cbus_dbg(binfile.pfile, binfile.iStartAddress, self.retry, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                            raise Exception('Write flash cbus fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                        self.task_flag(False)
                BKLog.w('Write flash by cbus done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    BKLog.i('protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        raise Exception('protect flash fail.')
                    BKLog.i('protect flash OK.')
                current_prog += 5
                BKLog.progress_log('BK', 'Downloading', int(current_prog))
                BKLog.progress_log('BK', 'Downloading', 100)
                result = True
            except Exception as e:
                result = False
                BKLog.e(str(e))
        finally:
            if self.reboot_after_donwload:
                BKLog.i('do reboot from bootrom.')
                base_controller.do_reboot()
            self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                BKLog.w('Download complete, all pass.')
                BKLog.w('done.')
            else:
                BKLog.e('Download fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            ui_bridge.end_flag('download_flash_cbus_task', result)
            return result

    def download_flash(self, work_br, binlist: List[BinInfo], all_flash_erase, chip_set: BaseChip):
        msg = None
        BKLog.i('parse flash info...')
        if not chip_set.parse_flash_info():
            msg = 'parse flash info fail.'
            return (False, msg)
        BKLog.i('unprotect flash...')
        if not chip_set.un_protect_flash(protect=False):
            msg = 'unprotect flash fail.'
            return (False, msg)
        BKLog.i('unprotect flash OK.')
        if BkDownloadFlowConfig.develop_set_baudrate_before_align:
            BKLog.i('set baudrate to {0}...'.format(work_br))
            if not chip_set.set_baudrate(baudrate=work_br, delay_ms=20):
                msg = 'set baudrate {0} fail.'.format(work_br)
                return (False, msg)
            if not all_flash_erase:
                BKLog.i('align start/end address...')
                if not chip_set.align_all_bin_buf(binlist=binlist, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                    raise Exception('align bin start/end address fail.')
        else:
            if not all_flash_erase:
                BKLog.i('align start/end address...')
                if not chip_set.align_all_bin_buf(binlist=binlist, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                    raise Exception('align bin start/end address fail.')
            BKLog.i('set baudrate to {0}...'.format(work_br))
            if not chip_set.set_baudrate(baudrate=work_br, delay_ms=20):
                msg = 'set baudrate {0} fail.'.format(work_br)
                return (False, msg)
        if all_flash_erase:
            if not chip_set.erase_flash(True, None, None, self.retry):
                msg = 'erase whole flash fail.'
                return (False, msg)
            BKLog.i('erase whole flash OK.')
        else:
            for binfile in binlist:
                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry):
                    msg = 'erase flash fail.'
                    return (False, msg)
        for binfile in binlist:
            if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type):
                msg = 'Write flash fail.'
                return (False, msg)
        BKLog.w('Write flash done.')
        BKLog.i('protect flash...')
        if not chip_set.un_protect_flash(protect=True):
            BKLog.e('protect flash fail.')
        else:
            BKLog.i('protect flash OK.')
        return (True, None)

    def download_safe_json(self, work_br, safe_json, aes_key, chip_set: BaseChip):
        msg = None
        BKLog.i('set baudrate to {0}...'.format(work_br))
        if not chip_set.set_baudrate(baudrate=work_br, delay_ms=20):
            msg = 'set baudrate {0} fail.'.format(work_br)
            return (False, msg)
        BKLog.i('write safe json content.')
        safeinfo = parse_safe_json_file(safe_json)
        if aes_key:
            for sedata in safeinfo.security_data_list:
                if sedata.name.find('aes_key') != -1:
                    sedata.data = aes_key
        (ret, msg) = chip_set.write_safe_json(safeinfo)
        if not ret:
            return (False, msg)
        BKLog.w('write safe json done.')
        return (True, None)
