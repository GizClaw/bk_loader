import time
from typing import List
from .action_base import ActionBase
from ..chip_controller import BaseController, AdvancedController
from ..chip_controller import FlashControllerTsingteng
from ..chip_controller import FlashController
from ..chip_controller import get_chip_set_with_chip_name
from ..chip_controller.chip_set.base_chip import BaseChip
from ..bk_log.log_utils import *
from ..common import ui_bridge
from ..common.common import RESET_TYPE, LINKCHECK, DownloadInfo, BIN_TYPE, FLASH_SIZE_DEF, BinInfo, bytes_reverse, parse_writeinfo_efuse, parse_writeinfo_otp, parse_device_mac_info, format_expand_data_value_for_log, describe_expand_data_out_of_flash_range
from ..common.version import get_tool_version
from ..common.bk_out_config import BKOTPConfig, BkDownloadFlowConfig

class SinglePortDownload(ActionBase):
    """单端口烧录类，继承自 ActionBase，负责单个串口的完整烧录流程"""

    def __init__(self, port='/dev/ttyUSB0', baudrate=115200, link_check_type=None, reset_type=None, reset_baudrate=115200, getbus_times=100, reboot_after_download=True, retry=5, chipname=None, debug='3', link_key=None, random_bin_path=None, port_prefix='', channel_number=None) -> None:
        super().__init__(port, baudrate)
        self.link_check_type = link_check_type
        self.reset_type = reset_type
        self.reset_baudrate = reset_baudrate
        self.reboot_after_download = reboot_after_download
        self.getbus_times = getbus_times
        self.retry = retry
        self.chip_name = chipname
        self.chip_id = None
        self.debug = debug
        self.link_key = link_key
        self.random_bin_path = random_bin_path
        self.port_prefix = port_prefix
        self.channel_number = channel_number
        self._port_name = port

    def _get_chip_set(self, find_sec_id=True):
        """工厂模式优先使用显式 chipname，否则从设备识别。"""
        if self.chip_name:
            chip_set = get_chip_set_with_chip_name(self.chip_name)
            if chip_set is None:
                raise Exception('get chip set fail. Unsupported chip name: {}'.format(self.chip_name))
            return chip_set
        return super()._get_chip_set(find_sec_id)

    def download_common_pre_action(self, downloadinfo: DownloadInfo, base_controller: BaseController, all_bin_info: List[BinInfo], find_sec_id: bool=False, current_prog: float=1):
        """工厂模式 mixed task 的公共前置流程。"""
        self._check_otp_linkcheck_obj(downloadinfo)
        (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
        if not tmp_res:
            raise Exception('get bus fail.')
        self._maybe_verify_random_bin(linktype)
        time.sleep(0.1)
        current_prog += 5
        chip_set = self._get_chip_set(find_sec_id)
        chip_set.update_serial_instance(self.ser)
        if not chip_set.set_baudrate_correct():
            raise Exception('set baudrate correct fail.')
        self._log('i', 'parse flash info...')
        if not chip_set.parse_flash_info():
            raise Exception('parse flash info fail.')
        self._log('i', 'check BKAESRDM words in flash...')
        chip_set.check_bkaesrdm_status(retry_cnt=5)
        self._log('i', 'check BKAESRDM words in flash OK.')
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
        if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
            self._log('i', 'unprotect flash...')
            if not chip_set.un_protect_flash(protect=False):
                raise Exception('unprotect flash fail.')
            self._log('i', 'unprotect flash OK.')
        return (chip_set, th_flash_ctrl, current_prog)

    def download_common_post_action(self, downloadinfo: DownloadInfo, chip_set: BaseChip, th_flash_ctrl: FlashControllerTsingteng, current_prog: float):
        """工厂模式 mixed task 的公共后置流程。"""
        if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
            self._log('i', 'protect flash...')
            if not chip_set.un_protect_flash(protect=True):
                self._log('e', 'protect flash fail.')
            else:
                self._log('i', 'protect flash OK.')
        if downloadinfo.safeinfo.write_safe_config:
            self._log('i', 'write safe json content.')
            if downloadinfo.aes_key:
                for sedata in downloadinfo.safeinfo.security_data_list:
                    if 'aes_key' in sedata.name:
                        sedata.data = downloadinfo.aes_key
            (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
            if not ret:
                self._log('e', msg)
                raise Exception('Write safe json fail.')
            self._log('w', 'write safe json done.')
        if downloadinfo.efuse_info:
            infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
            if infolist is None:
                raise Exception('parse efuse info fail.')
            for info in infolist:
                if len(info) == 3:
                    (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                elif len(info) == 2:
                    (ret, msg) = chip_set.write_efuse(info[0], info[1])
                else:
                    raise Exception('Invalid efuse write info.')
                if not ret:
                    self._log('e', msg)
                    raise Exception('Write efuse fail.')
        if downloadinfo.otp_info:
            infolist = parse_writeinfo_otp(downloadinfo.otp_info)
            if infolist is None:
                raise Exception('parse OTP info fail.')
            for info in infolist:
                (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content)
                if not ret:
                    self._log('e', msg)
                    raise Exception('Write OTP fail.')
        if downloadinfo.otp_pm:
            infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
            if infolist is None:
                raise Exception('parse OTP permission info fail.')
            for info in infolist:
                (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                if not ret:
                    self._log('e', msg)
                    raise Exception('Set OTP permission fail.')
        if downloadinfo.flash_otp:
            infolist = parse_writeinfo_otp(downloadinfo.flash_otp)
            if infolist is None:
                raise Exception('parse flash OTP info fail.')
            for info in infolist:
                if not chip_set.write_chip_flash_security(info[1], bytes.fromhex(info[0])):
                    raise Exception('write flash OTP fail.')
        if chip_set._flash_mid in [1269965, 1335501, 1401067] and (not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid)):
            raise Exception('Execute flash scratch solution fail.')
        return current_prog + 5

    def _ensure_bl1_magic_word(self, chip_set: BaseChip, magic_addr: int, magic_word: bytes, version_info: bytes=None):
        read_bytes = chip_set.read_and_check_sector(0, 10)
        if read_bytes is None:
            raise Exception('Read flash fail, address:0x0, length:0x1000.')
        version_addr = magic_addr + 10
        magic_matches = read_bytes[magic_addr:magic_addr + 5] == magic_word
        version_matches = version_info is None or read_bytes[version_addr:version_addr + 16] == version_info
        if magic_matches and version_matches:
            return
        write_buffer = bytearray(read_bytes)
        write_buffer[magic_addr:magic_addr + 5] = magic_word
        if version_info is not None:
            write_buffer[version_addr:version_addr + 16] = version_info
        flash_ctrl = FlashController(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
        if not flash_ctrl.erase_sector(0):
            raise Exception('Erase flash fail, address:0x0, length:0x1000.')
        if not chip_set.write_and_check_sector(bytes(write_buffer), 0):
            raise Exception('Write flash fail, address:0x0, length:0x1000.')

    def _get_bl1_bins_version_and_magic_word(self, bin_list: List[BinInfo]):
        magic_words = (b'BEKEN', b'BK.SB')
        for binfile in bin_list:
            for magic_addr in [256, 272]:
                version_addr = magic_addr + 10
                if len(binfile.pfile) < version_addr + 16:
                    continue
                magic_word = binfile.pfile[magic_addr:magic_addr + 5]
                if magic_word in magic_words:
                    version_info = bytes(binfile.pfile[version_addr:version_addr + 16])
                    return (magic_addr, magic_word, version_info)
        raise Exception('Cannot find BEKEN/BK.SB and 16-byte version info in BL1 bin.')

    def download_bl1_secure_extension_flash(self, downloadinfo: DownloadInfo, extension_bins: List[BinInfo], base_controller: BaseController, chip_set: BaseChip, current_prog: float, progress_span: float):
        if not extension_bins:
            raise Exception('BL1 secure extension bin is empty.')
        extension_bin = extension_bins[0]
        self._log('i', 'write BL1 secure extension bin before reboot.')
        if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
            raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
        if not chip_set.download_flash_cbus(extension_bin.pfile, extension_bin.iStartAddress, extension_bin.iFileLength + 4096, extension_bin.iStartAddress, self.retry, self.reset_type, self.link_check_type, current_prog, progress_span):
            raise Exception('Write BL1 secure extension flash by cbus fail.')
        (magic_addr, magic_word, _) = self._get_bl1_bins_version_and_magic_word(extension_bins)
        self._ensure_bl1_magic_word(chip_set, magic_addr, magic_word)
        self._log('i', 'BL1 secure extension write done, reboot and reconnect bus...')
        base_controller.do_reboot()
        time.sleep(0.5)
        if not base_controller.reconnect_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_retry_count=self.getbus_times, link_key=self.link_key):
            raise Exception('reconnect bus after BL1 secure extension fail.')
        chip_set.update_serial_instance(self.ser)
        return current_prog + progress_span

    def download_bl1_secure_fixed_flash(self, downloadinfo: DownloadInfo, fixed_bins: List[BinInfo], chip_set: BaseChip, current_prog: float, progress_span: float):
        if not fixed_bins:
            raise Exception('BL1 secure fixed bin is empty.')
        self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
        if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
            raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
        prog_per_action = progress_span / (len(fixed_bins) * 2)
        for (index, binfile) in enumerate(fixed_bins):
            self._log('i', f'[{index}] erase flash.')
            if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_action):
                raise Exception('erase flash fail.')
            current_prog += prog_per_action
            self._log('i', f'[{index}] write flash.')
            if binfile.bDataPort:
                write_ok = chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type, current_prog, prog_per_action)
            else:
                write_ok = chip_set.download_flash_cbus(binfile.pfile, binfile.iPartition_start, binfile.iPartition_size, binfile.iStartAddress, self.retry, self.reset_type, self.link_check_type, current_prog, prog_per_action)
            if not write_ok:
                raise Exception('Write BL1 secure fixed flash fail.')
            current_prog += prog_per_action
        (magic_addr, magic_word, version_info) = self._get_bl1_bins_version_and_magic_word(fixed_bins)
        self._ensure_bl1_magic_word(chip_set, magic_addr, magic_word, version_info=version_info)
        self._log('w', 'Write BL1 secure fixed flash done.')
        return current_prog

    def _run_bl1_secure_task(self, downloadinfo: DownloadInfo, extension_bins: List[BinInfo], fixed_bins: List[BinInfo], task_name: str):
        """Factory wrapper around the shared BL1 secure mixed actions."""
        start_time = time.time()

        def _elapsed():
            return int(time.time() - start_time)
        if self.channel_number is not None:
            if ui_bridge.should_stop_factory(self.channel_number):
                self._push_factory_status('standby', 0, 0)
                return (False, 'stopped')
            self._push_factory_status('running', 0, 0)
        self._print_download_info(downloadinfo)
        result = False
        error_msg = None
        base_controller = BaseController(serial_instance=self.ser)
        current_prog = 1
        try:
            try:
                self._push_factory_status('running', 15, _elapsed(), phase='get_bus')
                all_bin_info = list(extension_bins) + list(fixed_bins)
                (chip_set, th_flash_ctrl, current_prog) = self.download_common_pre_action(downloadinfo, base_controller, all_bin_info, False, current_prog)
                middle_progress = 84.0
                extension_weight = extension_bins[0].iFileLength if extension_bins else 0
                fixed_weight = sum((binfile.iFileLength * 2 for binfile in fixed_bins))
                total_weight = extension_weight + fixed_weight
                extension_progress = middle_progress * extension_weight / total_weight if extension_weight else 0
                fixed_progress = middle_progress - extension_progress
                if extension_bins:
                    self._push_factory_status('running', 25, _elapsed(), phase='write')
                    current_prog = self.download_bl1_secure_extension_flash(downloadinfo, extension_bins, base_controller, chip_set, current_prog, extension_progress)
                if fixed_bins:
                    self._push_factory_status('running', max(25, int(current_prog)), _elapsed(), phase='erase')
                    current_prog = self.download_bl1_secure_fixed_flash(downloadinfo, fixed_bins, chip_set, current_prog, fixed_progress)
                self._push_factory_status('running', 95, _elapsed(), phase='write_safe_json')
                self.download_common_post_action(downloadinfo, chip_set, th_flash_ctrl, current_prog)
                result = True
            except Exception as e:
                error_msg = str(e)
                self._log('e', error_msg)
        finally:
            if self.channel_number is not None:
                if result:
                    self._push_factory_status('success', 100, _elapsed())
                else:
                    self._push_factory_status('failure', 100, _elapsed(), error_msg)
            if self.reboot_after_download:
                self._log('i', 'do reboot from bootrom.')
                base_controller.do_reboot()
            if self.ser:
                self.ser.disconnect()
            if result:
                self._log('w', 'Download complete, all pass.')
                self._log('w', 'done.')
            else:
                self._log('e', 'Download fail.')
            self._log('i', f'Elapse time: {time.time() - start_time:.6f} seconds.')
        return (result, error_msg)

    def download_bl1_secure_extension_task(self, downloadinfo: DownloadInfo):
        return self._run_bl1_secure_task(downloadinfo, extension_bins=downloadinfo.vecbinInfo, fixed_bins=[], task_name='download_bl1_secure_extension_task')

    def download_bl1_secure_fixed_task(self, downloadinfo: DownloadInfo):
        return self._run_bl1_secure_task(downloadinfo, extension_bins=[], fixed_bins=downloadinfo.vecbinInfo, task_name='download_bl1_secure_fixed_task')

    def download_mixed_task(self, downloadinfo: DownloadInfo):
        mixed_types = {single_type_bin.binType for single_type_bin in downloadinfo.mixedBinInfo}
        supported_types = {BIN_TYPE.TYPE_BL1_SECURE_EXTENSION, BIN_TYPE.TYPE_BL1_SECURE_FIXED}
        if mixed_types == supported_types:
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

    def switch_baudrate_for_expand_data_write(self, chip_set: BaseChip, end_flag: bool, original_baudrate: int=None):
        """
        拓展数据烧录前/后切换波特率：传入 chip_set、end_flag、original_baudrate；方法内由 factory_switch_baudrate_for_expand_data 判断是否执行；end_flag=False 切到 115200，end_flag=True 恢复为 original_baudrate。
        """
        if not BkDownloadFlowConfig.factory_switch_baudrate_for_expand_data:
            return
        if end_flag:
            if original_baudrate is not None and (not chip_set.set_baudrate(original_baudrate)):
                raise Exception('restore baudrate after write expand data fail.')
        elif not chip_set.set_baudrate(115200):
            raise Exception('set baudrate to 115200 for write expand data fail.')

    def write_expand_data_and_device_info(self, chip_set: BaseChip, downloadinfo: DownloadInfo, current_prog=None, erase_prog=None, elapsed_seconds: int=0):
        has_non_bin_data = len(downloadinfo.expand_data_list) > 0 or downloadinfo.bDownloadDeviceName or downloadinfo.bDownloadDeviceID
        all_flash_erased = False
        if has_non_bin_data and downloadinfo.bDownloadBin and (downloadinfo.pre_erase == 1) and downloadinfo.bAllFlash:
            if self.channel_number is not None:
                self._push_factory_status('running', 25, elapsed_seconds, phase='erase')
            self._log('i', 'erase whole flash.')
            if current_prog is None or erase_prog is None:
                if not chip_set.erase_flash(True, None, None, self.retry):
                    raise Exception('erase whole flash fail.')
            else:
                if not chip_set.erase_flash(True, None, None, self.retry, current_prog, erase_prog):
                    raise Exception('erase whole flash fail.')
                current_prog += erase_prog
            self._log('i', 'erase whole flash OK.')
            all_flash_erased = True
        if has_non_bin_data and self.channel_number is not None:
            self._push_factory_status('running', 80, elapsed_seconds, phase='write_expand_data')
        if len(downloadinfo.expand_data_list) > 0:
            self._log('i', 'write expand data.')
            for expand_data in downloadinfo.expand_data_list:
                self._log('i', f'write expand data: {expand_data.name}@0x{expand_data.start_addr:x}@0x{expand_data.length:x} {format_expand_data_value_for_log(expand_data)}.')
                out_of_range = describe_expand_data_out_of_flash_range(expand_data, chip_set._flash_cfg.flash_size)
                if out_of_range:
                    self._log('e', out_of_range)
                if not chip_set.write_flash_info(expand_data.start_addr, expand_data.value):
                    raise Exception('Write expand data {0} fail.'.format(expand_data.name))
            self._log('w', 'Write expand data done.')
        if downloadinfo.bDownloadDeviceName:
            self._log('i', f'write device name: {downloadinfo.device_name} @0x{downloadinfo.device_name_Addr:x}.')
            if not chip_set.write_flash_info(downloadinfo.device_name_Addr, downloadinfo.device_name):
                raise Exception('Write device name to flash fail.')
            self._log('w', 'Write device name to flash done.')
        if downloadinfo.bDownloadDeviceID:
            self._log('i', f'write device ID: {bytes.hex(downloadinfo.device_id)} @0x{downloadinfo.device_id_Addr:x}.')
            devid = bytes_reverse(downloadinfo.device_id) if not downloadinfo.bEnableBigEndian else downloadinfo.device_id
            if not chip_set.write_flash_info(downloadinfo.device_id_Addr, devid):
                raise Exception('Write device ID to flash fail.')
            self._log('w', 'Write device ID to flash done.')
        return (all_flash_erased, current_prog)

    def _log(self, level: str, msg: str):
        """带端口前缀的日志输出"""
        full_msg = self.port_prefix + msg if self.port_prefix else msg
        if level == 'i':
            BKLog.i(full_msg)
        elif level == 'w':
            BKLog.w(full_msg)
        elif level == 'e':
            BKLog.e(full_msg)
        elif level == 'd':
            BKLog.d(full_msg)
        else:
            BKLog.w(full_msg)

    def _push_factory_status(self, status: str, progress: int, elapsed_seconds: int, error_message=None, phase: str=None):
        """工厂模式下推送通道状态到 UI。phase 为当前阶段：get_bus/erase/write/write_expand_data/write_safe_json。"""
        if self.channel_number is not None:
            ui_bridge.factory_channel_status(self.channel_number, self._port_name, status, progress, elapsed_seconds, error_message, phase=phase)

    def _print_download_info(self, downloadinfo: DownloadInfo):
        """打印下载信息"""
        self._init_log_level(self.ser.ser.name, self.debug)
        self._log('w', get_tool_version())
        self._log('w', f'comport: {self.ser.ser.name}')
        self._log('w', f'link type: {self.link_check_type}')
        self._log('w', f'reset type: {self.reset_type}')
        self._log('w', f'getbus times: {self.getbus_times}')
        self._log('w', f'reboot: {self.reboot_after_download}')
        self._log('w', f'link key: {self.link_key}')
        self._log('w', f'work baudrate: {downloadinfo.work_baudrate}')
        self._log('w', f'pre_erase: {downloadinfo.pre_erase} (0=no erase, 1=erase before write)')
        self._log('w', f'erase all: {downloadinfo.bAllFlash}')

    def _check_otp_linkcheck_obj(self, downloadinfo: DownloadInfo):
        """检查safe_json linkcheck对象"""
        if (downloadinfo.safeinfo.read_safe_config or downloadinfo.safeinfo.write_safe_config or downloadinfo.aes_key) and BKOTPConfig.must_use_bl1:
            self.link_check_type = LINKCHECK.BOOTROM
            BkDownloadFlowConfig.allow_change_linkcheck_obj = False

    def _maybe_verify_random_bin(self, linktype):
        from ..common.random_bin_verify import maybe_verify_random_bin_after_get_bus
        maybe_verify_random_bin_after_get_bus(self.ser, linktype, self.random_bin_path)

    def _bl2_version_upgrade(self, chip_set: BaseChip, binlist: List[BinInfo], ifreconnect=False):
        """BL2 版本升级逻辑，与 Download.bl2_version_upgrade 一致。"""
        new_ver = binlist[2].pfile[4] + (binlist[2].pfile[5] << 8) + (binlist[2].pfile[6] << 16) + (binlist[2].pfile[7] << 24)
        self._log('i', f'new version is: 0x{new_ver:x}')
        bl2a_start = binlist[4].iStartAddress
        bl2a_len = binlist[4].iFileLength
        bl2b_len = binlist[7].iFileLength
        manifesta_start = binlist[2].iStartAddress
        manifestb_start = binlist[3].iStartAddress
        bl2b_start = binlist[7].iStartAddress
        self._log('i', f'bl2a_start is: 0x{bl2a_start:x}')
        self._log('i', f'bl2a_len is: 0x{bl2a_len:x}')
        self._log('i', f'bl2b_start is: 0x{bl2b_start:x}')
        self._log('i', f'bl2b_len is: 0x{bl2b_len:x}')
        self._log('i', f'bl2b_buf_len is: 0x{len(binlist[7].pfile):x}')
        self._log('i', f'manifesta_start is: 0x{manifesta_start:x}')
        self._log('i', f'manifesta_len is: 0x{binlist[2].iFileLength:x}')
        self._log('i', f'manifestb_start is: 0x{manifestb_start:x}')
        self._log('i', f'manifestb_len is: 0x{binlist[3].iFileLength:x}')
        baudrate_backup = self.ser.baudrate
        basectrl = BaseController(serial_instance=self.ser)
        if ifreconnect:
            if not basectrl.reconnect_bus(reset_type=RESET_TYPE.MULTI, linkcheck_obj=None, max_retry_count=20, link_key=self.link_key):
                self._log('e', 'reconnect bus fail.')
                return False
            time.sleep(0.1)
            if not chip_set.set_baudrate(baudrate=baudrate_backup, delay_ms=20):
                self._log('e', 'set baudrate {0} fail.'.format(baudrate_backup))
                return False
        cur_ver = chip_set.read_bl2_version()
        if not cur_ver:
            self._log('e', 'read bl2 current version fail.')
            return False
        self._log('i', f'current version is: 0x{cur_ver:x}')
        if cur_ver != 4294967295 and new_ver <= cur_ver:
            return
        advctrl = AdvancedController(serial_instance=self.ser)
        bootflag = advctrl.start_stop_bl2_upgrade(True)
        if bootflag is False:
            self._log('e', 'start bl2 upgrade fail.')
            return False
        self._log('i', f'bootflag is: {bootflag}')
        if not chip_set.un_protect_flash(protect=False):
            self._log('e', 'unprotect flash fail.')
            return False
        if bootflag == 2:
            self._log('i', 'start write flash for manifest_a.')
            if not chip_set.erase_flash(False, manifesta_start, manifesta_start + 4096, self.retry):
                self._log('e', 'erase flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.download_flash(wbuf=binlist[2].pfile, start_addr=manifesta_start):
                self._log('e', 'write flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.erase_flash(False, bl2a_start, bl2a_start + bl2a_len, self.retry):
                self._log('e', 'erase flash fail.')
                return False
            time.sleep(0.1)
            self._log('i', 'start write flash for bl2_a.')
            if not chip_set.download_flash(wbuf=binlist[4].pfile, start_addr=bl2a_start, reset_type=RESET_TYPE.DTR_RTS, link_type=self.link_check_type):
                self._log('i', 'write flash for bl2_a fail.')
                return False
        elif bootflag == 1:
            self._log('i', 'start write flash for manifest_b.')
            if not chip_set.erase_flash(False, manifestb_start, manifestb_start + 4096, self.retry):
                self._log('e', 'erase flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.download_flash(wbuf=binlist[3].pfile, start_addr=manifestb_start):
                self._log('e', 'write flash fail.')
                return False
            time.sleep(0.1)
            if not chip_set.erase_flash(False, bl2b_start, bl2b_start + bl2b_len, self.retry):
                self._log('e', 'erase flash fail.')
                return False
            time.sleep(0.1)
            self._log('i', 'start write flash for bl2_b.')
            if not chip_set.download_flash(wbuf=binlist[7].pfile, start_addr=bl2b_start, reset_type=RESET_TYPE.DTR_RTS, link_type=self.link_check_type):
                self._log('i', 'write flash for bl2_b fail.')
                return False
        else:
            return False
        if not advctrl.start_stop_bl2_upgrade(start_stop=False):
            self._log('e', 'stop bl2 upgrade fail.')
            return False
        time.sleep(0.01)
        basectrl.do_reboot()
        return True

    def download_secure_task(self, downloadinfo: DownloadInfo) -> tuple:
        """Secure Fix 任务，与 Download.download_secure_task 逻辑一致。返回 (success, error_msg)。"""
        result = False
        error_msg = None
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        if self.channel_number is not None:
            if ui_bridge.should_stop_factory(self.channel_number):
                self._push_factory_status('standby', 0, 0)
                return (False, 'stopped')
            self._push_factory_status('running', 0, 0)
        self._print_download_info(downloadinfo)
        current_prog = 1

        def _elapsed():
            return int(time.time() - start_time)
        try:
            try:
                self._check_otp_linkcheck_obj(downloadinfo)
                self._log('i', 'Getting bus...')
                if self.channel_number is not None:
                    self._push_factory_status('running', 15, _elapsed(), phase='get_bus')
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                if self.chip_name:
                    chip_set = get_chip_set_with_chip_name(self.chip_name)
                    if chip_set is None:
                        raise Exception('get chip set fail. Unsupported chip name: {}'.format(self.chip_name))
                else:
                    chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                self._log('i', 'parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                current_prog += 5
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                if linktype == LINKCHECK.BOOTROM:
                    self._log('i', 'check aes key permission...')
                    ret = chip_set.check_aes_key_otp_permission()
                    if ret is False:
                        raise Exception('check aes key permission fail.')
                    if ret == 0:
                        self._log('i', 'aes key permission is not NA.')
                        ret = chip_set.check_aes_key_otp_data()
                        if ret is False:
                            raise Exception('check aes key data fail.')
                        if ret == 0:
                            self._log('i', 'aes key data is empty.')
                elif linktype == LINKCHECK.BL2:
                    cnt = 10
                    while cnt > 0:
                        ret = self._bl2_version_upgrade(chip_set, downloadinfo.vecbinInfo, cnt != 10)
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
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                (all_flash_erased, current_prog) = self.write_expand_data_and_device_info(chip_set, downloadinfo, current_prog, 40, elapsed_seconds=_elapsed())
                if downloadinfo.bDownloadBin:
                    total_prog = 40
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if self.channel_number is not None and (not all_flash_erased):
                        self._push_factory_status('running', 35, _elapsed(), phase='erase')
                    if not all_flash_erased and downloadinfo.bAllFlash:
                        self._log('i', 'erase whole flash.')
                        if not chip_set.erase_flash(True, None, None, self.retry, current_prog, total_prog):
                            raise Exception('erase whole flash fail.')
                        self._log('i', 'erase whole flash OK.')
                    elif not all_flash_erased:
                        erase_idx = 0
                        for binfile in downloadinfo.vecbinInfo:
                            self._log('i', f'[{erase_idx}] erase flash.')
                            self._log('i', f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                            self._log('i', f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                            if binfile.bCheck and binfile.bDataPort:
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                            erase_idx += 1
                            current_prog += prog_per_bin
                    if self.channel_number is not None:
                        self._push_factory_status('running', 50, _elapsed(), phase='write')
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        if binfile.bCheck:
                            self._log('i', f'[{write_idx}] write flash.')
                            self._log('i', f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                            self._log('i', f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                            if binfile.bDataPort:
                                if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, link_type=linktype, cprog=current_prog, sprog=prog_per_bin):
                                    raise Exception('Write flash fail.')
                            elif not chip_set.download_flash_cbus(binfile.pfile, binfile.iPartition_start, binfile.iPartition_size, binfile.iStartAddress, self.retry, self.reset_type, link_type=linktype, cprog=current_prog, sprog=prog_per_bin):
                                raise Exception('Write flash fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                    self._log('w', 'Write flash done.')
                if downloadinfo.safeinfo.write_safe_config:
                    if self.channel_number is not None:
                        self._push_factory_status('running', 80, _elapsed(), phase='write_safe_json')
                    self._log('i', 'write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        self._log('e', msg)
                        raise Exception('Write safe json fail.')
                    self._log('w', 'write safe json done.')
                if downloadinfo.efuse_info:
                    self._log('i', 'write chip efuse.')
                    infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
                    if infolist is None:
                        raise Exception('parse efuse info fail.')
                    for info in infolist:
                        if len(info) == 3:
                            (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                        else:
                            (ret, msg) = chip_set.write_efuse(info[0], info[1])
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Write efuse fail.')
                    self._log('w', 'Write efuse done.')
                if downloadinfo.otp_info:
                    self._log('i', 'write chip OTP.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_info)
                    if infolist is None:
                        raise Exception('parse OTP info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content, downloadinfo.bEnableBigEndian)
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Write OTP fail.')
                    self._log('w', 'Write OTP done.')
                if downloadinfo.otp_pm:
                    self._log('i', 'set OTP permission.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
                    if infolist is None:
                        raise Exception('parse OTP permission info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Set OTP permission fail.')
                    self._log('w', 'Set OTP permission done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName:
                    self._log('i', 'protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        self._log('e', 'protect flash fail.')
                    else:
                        self._log('i', 'protect flash OK.')
                result = True
            except Exception as e:
                result = False
                error_msg = str(e)
                self._log('e', error_msg)
        finally:
            if self.reboot_after_download:
                self._log('i', 'do reboot from bootrom.')
                base_controller.do_reboot()
            if self.channel_number is not None:
                elapsed = _elapsed()
                if result:
                    self._push_factory_status('success', 100, elapsed)
                else:
                    self._push_factory_status('failure', 100, elapsed, error_msg)
            if self.ser:
                self.ser.disconnect()
            elapsed_time = time.time() - start_time
            if result:
                self._log('w', 'Download complete, all pass.')
                self._log('w', 'done.')
            else:
                self._log('e', 'Download fail.')
            self._log('i', f'Elapse time: {elapsed_time:.6f} seconds.')
        return (result, error_msg)

    def download_with_outter_flash_task(self, downloadinfo: DownloadInfo) -> tuple:
        """外置 Flash 任务，与 Download.download_with_outter_flash_task 逻辑一致。返回 (success, error_msg)。"""
        result = False
        error_msg = None
        start_time = time.time()
        if self.channel_number is not None:
            if ui_bridge.should_stop_factory(self.channel_number):
                self._push_factory_status('standby', 0, 0)
                return (False, 'stopped')
            self._push_factory_status('running', 0, 0)
        self._print_download_info(downloadinfo)
        base_controller = BaseController(serial_instance=self.ser)
        main_bin = downloadinfo.vecbinInfo[:len(downloadinfo.vecbinInfo) - 1]
        outer_bin = downloadinfo.vecbinInfo[len(downloadinfo.vecbinInfo) - 1]
        current_prog = 1

        def _elapsed():
            return int(time.time() - start_time)
        try:
            try:
                self._check_otp_linkcheck_obj(downloadinfo)
                self._log('i', 'Getting bus...')
                if self.channel_number is not None:
                    self._push_factory_status('running', 15, _elapsed(), phase='get_bus')
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                current_prog += 5
                if self.chip_name:
                    chip_set = get_chip_set_with_chip_name(self.chip_name)
                    if chip_set is None:
                        raise Exception('get chip set fail. Unsupported chip name: {}'.format(self.chip_name))
                else:
                    chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                self._log('i', 'parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                ret = chip_set.read_and_check_sector(8384512)
                if ret is None:
                    raise Exception('read flash @0x7ff000 fail.')
                self._log('w', f'Device MAC:{bytes.hex(bytes(ret[:6]))}')
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
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                total_prog = 40
                prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                (all_flash_erased, current_prog) = self.write_expand_data_and_device_info(chip_set, downloadinfo, current_prog, prog_per_bin * len(main_bin), elapsed_seconds=_elapsed())
                if BkDownloadFlowConfig.factory_set_baudrate_before_align:
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=main_bin, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=main_bin, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    total_prog = 80
                    prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        if self.channel_number is not None:
                            self._push_factory_status('running', 30, _elapsed(), phase='erase')
                        total_prog = 40
                        prog_per_bin = total_prog / len(downloadinfo.vecbinInfo)
                        if downloadinfo.bAllFlash:
                            self._log('i', 'erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, current_prog, prog_per_bin * len(main_bin)):
                                raise Exception('erase whole flash fail.')
                            self._log('i', 'erase whole flash OK.')
                            current_prog += prog_per_bin * len(main_bin)
                        else:
                            erase_idx = 0
                            for binfile in main_bin:
                                self._log('i', f'[{erase_idx}] erase flash.')
                                self._log('i', f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                self._log('i', f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry, current_prog, prog_per_bin):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                                current_prog += prog_per_bin
                    time.sleep(0.001)
                    if self.channel_number is not None:
                        self._push_factory_status('running', 45, _elapsed(), phase='write')
                    write_idx = 0
                    for binfile in main_bin:
                        if binfile.iStartAddress & 4095:
                            binfile.iStartAddress = int((binfile.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                        self._log('i', f'[{write_idx}] write flash.')
                        self._log('i', f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        self._log('i', f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, self.reset_type == RESET_TYPE.DTR_RTS, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                        current_prog += prog_per_bin
                self._log('w', 'Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    self._log('i', 'protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        self._log('e', 'protect flash fail.')
                    else:
                        self._log('i', 'protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    if self.channel_number is not None:
                        self._push_factory_status('running', 55, _elapsed(), phase='write_safe_json')
                    self._log('i', 'write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        self._log('e', msg)
                        raise Exception('Write safe json fail.')
                    self._log('w', 'write safe json done.')
                if chip_set._flash_mid == 1269965 or chip_set._flash_mid == 1335501 or chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid):
                        raise Exception('Execute flash scratch solution fail.')
                time.sleep(0.001)
                self._log('w', 'OUTTER FLASH OPERATION')
                self._log('i', 'enter write outter flash mode...')
                if not chip_set.reboot_and_enter_write_outter_flash_mode(self.reset_type):
                    raise Exception('enter write outter flash mode fail.')
                time.sleep(0.2)
                self._log('i', 'parse outter flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse outter flash info fail.')
                if BkDownloadFlowConfig.factory_set_baudrate_before_align:
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=[outer_bin], for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=[outer_bin], for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    if self.channel_number is not None:
                        self._push_factory_status('running', 70, _elapsed(), phase='erase')
                    if downloadinfo.bAllFlash:
                        self._log('i', 'erase whole outter flash.')
                        if not chip_set.erase_flash(True, None, None, self.retry, current_prog, prog_per_bin):
                            raise Exception('erase whole outter flash fail.')
                        self._log('i', 'erase whole outter flash OK.')
                        current_prog += prog_per_bin
                    else:
                        self._log('w', '[outter] erase flash.')
                        self._log('i', f'[outter] start: 0x{outer_bin.iStartAddress:x}.')
                        self._log('i', f'[outter] length: 0x{outer_bin.iFileLength:x}.')
                        if not chip_set.erase_flash(False, outer_bin.iStartAddress, outer_bin.iStartAddress + outer_bin.iFileLength, self.retry, current_prog, prog_per_bin):
                            raise Exception('erase outter flash fail.')
                        current_prog += prog_per_bin
                    time.sleep(0.001)
                    if self.channel_number is not None:
                        self._push_factory_status('running', 85, _elapsed(), phase='write')
                    self._log('w', '[outter] write flash.')
                    self._log('i', f'[outter] start: 0x{outer_bin.iStartAddress:x}.')
                    self._log('i', f'[outter] length: 0x{outer_bin.iFileLength:x}.')
                    if not chip_set.download_flash(outer_bin.pfile, outer_bin.iStartAddress, self.retry, False, self.reset_type, self.link_check_type, current_prog, prog_per_bin):
                        raise Exception('Write outter flash fail.')
                    current_prog += prog_per_bin
                self._log('w', 'Write outter flash done.')
                time.sleep(0.001)
                if downloadinfo.custom_data:
                    (ret, bydata, addr, oplen) = parse_device_mac_info(downloadinfo.custom_data)
                    if not ret:
                        raise Exception('Input custom data format error.')
                    self.ser.reset(115200)
                    if not base_controller.reconnect_bus(reset_type=self.reset_type, linkcheck_obj=None, reset_baudrate=115200, max_retry_count=60, link_key=self.link_key):
                        raise Exception('reconnect bus fail.')
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                    self._log('i', f'write custom data: {bytes.hex(bydata)} @0x{addr:x}.')
                    if not chip_set.write_flash_info(addr, bydata):
                        raise Exception('Write custom data to flash fail.')
                    self._log('w', 'Write custom data to flash done.')
                    self._log('i', 'protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        self._log('e', 'protect flash fail.')
                    else:
                        self._log('i', 'protect flash OK.')
                current_prog += 5
                result = True
            except Exception as e:
                result = False
                error_msg = str(e)
                self._log('e', error_msg)
        finally:
            if self.reboot_after_download:
                self._log('i', 'do reboot from bootrom.')
                base_controller.do_reboot()
            if result and downloadinfo.check_words != '':
                tmp = downloadinfo.check_words.split('@')
                self.ser.reset(int(tmp[1]))
                result = False
                self._log('w', f'start check key words {tmp[0]}.')
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
                    self._log('e', f'check key words {tmp[0]} fail.')
            if self.channel_number is not None:
                elapsed = _elapsed()
                if result:
                    self._push_factory_status('success', 100, elapsed)
                else:
                    self._push_factory_status('failure', 100, elapsed, error_msg)
            if self.ser:
                self.ser.disconnect()
            elapsed_time = time.time() - start_time
            if result:
                self._log('w', 'Download complete, all pass.')
                self._log('w', 'done.')
            else:
                self._log('e', 'Download fail.')
            self._log('i', f'Elapse time: {elapsed_time:.6f} seconds.')
        return (result, error_msg)

    def download_bootloader_ota(self, downloadinfo: DownloadInfo) -> tuple:
        """BL2 OTA 任务，与 Download.download_bootloader_ota 逻辑一致。返回 (success, error_msg)。"""
        result = False
        error_msg = None
        start_time = time.time()
        if self.channel_number is not None:
            if ui_bridge.should_stop_factory(self.channel_number):
                self._push_factory_status('standby', 0, 0)
                return (False, 'stopped')
            self._push_factory_status('running', 0, 0)
        self._print_download_info(downloadinfo)
        base_controller = BaseController(serial_instance=self.ser)

        def _elapsed():
            return int(time.time() - start_time)
        try:
            try:
                self._check_otp_linkcheck_obj(downloadinfo)
                self._log('i', 'Getting bus...')
                if self.channel_number is not None:
                    self._push_factory_status('running', 15, _elapsed(), phase='get_bus')
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                if self.chip_name:
                    chip_set = get_chip_set_with_chip_name(self.chip_name)
                    if chip_set is None:
                        raise Exception('get chip set fail. Unsupported chip name: {}'.format(self.chip_name))
                else:
                    chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                self._log('i', 'parse flash info...')
                if not chip_set.parse_flash_info():
                    raise Exception('parse flash info fail.')
                self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                th_flash_ctrl = FlashControllerTsingteng(serial_instance=self.ser, flash_cfg=chip_set._flash_cfg)
                if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
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
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                if BaseController.link_check_obj is not None and BaseController.link_check_obj == LINKCHECK.BL2:
                    advctrl = AdvancedController(serial_instance=self.ser)
                    partition_flag = advctrl.read_bootloader_partition_flag()
                    if partition_flag is None:
                        raise Exception('read bootloader partition flag fail.')
                    operate_area = 'A' if partition_flag == 2 else 'B'
                    self._log('i', f"bootloader is running in {('B' if operate_area == 'A' else 'A')}, load {operate_area}.")
                else:
                    operate_area = 'A'
                indices = [0, 2] if operate_area == 'A' else [1, 3]
                selected_bins = [downloadinfo.vecbinInfo[i] for i in indices]
                downloadinfo.vecbinInfo = selected_bins
                (all_flash_erased, _) = self.write_expand_data_and_device_info(chip_set, downloadinfo, elapsed_seconds=_elapsed())
                if downloadinfo.bDownloadBin:
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        if self.channel_number is not None:
                            self._push_factory_status('running', 35, _elapsed(), phase='erase')
                        if downloadinfo.bAllFlash:
                            self._log('i', 'erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry):
                                raise Exception('erase whole flash fail.')
                            self._log('i', 'erase whole flash OK.')
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self._log('i', f'[{erase_idx}] erase flash.')
                                self._log('i', f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                self._log('i', f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                    if self.channel_number is not None:
                        self._push_factory_status('running', 50, _elapsed(), phase='write')
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        if binfile.iStartAddress & 4095:
                            binfile.iStartAddress = int((binfile.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                        self._log('i', f'[{write_idx}] write flash.')
                        self._log('i', f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        self._log('i', f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, self.reset_type == RESET_TYPE.DTR_RTS, self.reset_type, self.link_check_type):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                    self._log('w', 'Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    self._log('i', 'protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        self._log('e', 'protect flash fail.')
                    else:
                        self._log('i', 'protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    if self.channel_number is not None:
                        self._push_factory_status('running', 80, _elapsed(), phase='write_safe_json')
                    self._log('i', 'write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        self._log('e', msg)
                        raise Exception('Write safe json fail.')
                    self._log('w', 'write safe json done.')
                if downloadinfo.efuse_info:
                    self._log('i', 'write chip efuse.')
                    infolist = parse_writeinfo_efuse(downloadinfo.efuse_info)
                    if infolist is None:
                        raise Exception('parse efuse info fail.')
                    for info in infolist:
                        if len(info) == 3:
                            (ret, msg) = chip_set.write_efuse_by_bit(info[1], info[2], info[0])
                        else:
                            (ret, msg) = chip_set.write_efuse(info[0], info[1])
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Write efuse fail.')
                    self._log('w', 'Write efuse done.')
                if downloadinfo.otp_info:
                    self._log('i', 'write chip OTP.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_info)
                    if infolist is None:
                        raise Exception('parse OTP info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.write_chip_otp(info[1], info[0], downloadinfo.reverse_content)
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Write OTP fail.')
                    self._log('w', 'Write OTP done.')
                if downloadinfo.otp_pm:
                    self._log('i', 'set OTP permission.')
                    infolist = parse_writeinfo_otp(downloadinfo.otp_pm)
                    if infolist is None:
                        raise Exception('parse OTP permission info fail.')
                    for info in infolist:
                        (ret, msg) = chip_set.set_otp_permission_oplen(info[1], info[2], info[0])
                        if not ret:
                            self._log('e', msg)
                            raise Exception('Set OTP permission fail.')
                    self._log('w', 'Set OTP permission done.')
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
                error_msg = str(e)
                self._log('e', error_msg)
        finally:
            if self.reboot_after_download:
                self._log('i', 'do reboot from bootrom.')
                base_controller.do_reboot()
            if self.channel_number is not None:
                elapsed = _elapsed()
                if result:
                    self._push_factory_status('success', 100, elapsed)
                else:
                    self._push_factory_status('failure', 100, elapsed, error_msg)
            if self.ser:
                self.ser.disconnect()
            elapsed_time = time.time() - start_time
            if result:
                self._log('w', 'Download complete, all pass.')
                self._log('w', 'done.')
            else:
                self._log('e', 'Download fail.')
            self._log('i', f'Elapse time: {elapsed_time:.6f} seconds.')
        return (result, error_msg)

    def download_base_task(self, downloadinfo: DownloadInfo) -> tuple:
        start_time = time.time()
        if self.channel_number is not None:
            if ui_bridge.should_stop_factory(self.channel_number):
                self._push_factory_status('standby', 0, 0)
                return (False, 'stopped')
            self._push_factory_status('running', 0, 0)
        self._print_download_info(downloadinfo)
        result = False
        error_msg = None
        base_controller = BaseController(serial_instance=self.ser)

        def _elapsed():
            return int(time.time() - start_time)
        try:
            try:
                self._check_otp_linkcheck_obj(downloadinfo)
                self._log('i', 'Getting bus...')
                if self.channel_number is not None:
                    self._push_factory_status('running', 15, _elapsed(), phase='get_bus')
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=self.link_check_type, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=BkDownloadFlowConfig.allow_change_linkcheck_obj)
                if not tmp_res:
                    raise Exception('get bus fail.')
                self._maybe_verify_random_bin(linktype)
                time.sleep(0.1)
                if self.chip_name:
                    chip_set = get_chip_set_with_chip_name(self.chip_name)
                    if chip_set is None:
                        raise Exception('get chip set fail. Unsupported chip name: {}'.format(self.chip_name))
                else:
                    chip_set = self._get_chip_set()
                chip_set.update_serial_instance(self.ser)
                if BkDownloadFlowConfig.check_bin_board_crc_sync:
                    chip_set.pre_check_img_file_crc(downloadinfo.vecbinInfo)
                if not chip_set.set_baudrate_correct():
                    raise Exception('set baudrate correct fail.')
                if BkDownloadFlowConfig.verify_product_id and downloadinfo.bDownloadBin:
                    self._log('i', 'verifying chip product id...')
                    chip_set.verify_chip_product_id(downloadinfo.vecbinInfo[0])
                    self._log('i', 'verifying chip product id OK.')
                self._log('i', 'parse flash info...')
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
                    self._log('i', 'unprotect flash...')
                    if not chip_set.un_protect_flash(protect=False):
                        raise Exception('unprotect flash fail.')
                    self._log('i', 'unprotect flash OK.')
                (all_flash_erased, _) = self.write_expand_data_and_device_info(chip_set, downloadinfo, 1, 40, elapsed_seconds=_elapsed())
                if BkDownloadFlowConfig.factory_set_baudrate_before_align:
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=downloadinfo.vecbinInfo, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                else:
                    if downloadinfo.bDownloadBin and (not downloadinfo.bAllFlash):
                        self._log('i', 'align start/end address...')
                        if not chip_set.align_all_bin_buf(binlist=downloadinfo.vecbinInfo, for_erase=False, reconnect_retry=True, reset_type=self.reset_type, link_type=self.link_check_type, retry_cnt=self.retry):
                            raise Exception('align bin start/end address fail.')
                    self._log('i', 'set baudrate to {0}...'.format(downloadinfo.work_baudrate))
                    if not chip_set.set_baudrate(baudrate=downloadinfo.work_baudrate, delay_ms=20):
                        raise Exception('set baudrate {0} fail.'.format(downloadinfo.work_baudrate))
                if downloadinfo.bDownloadBin:
                    if downloadinfo.pre_erase == 1 and (not all_flash_erased):
                        if self.channel_number is not None:
                            self._push_factory_status('running', 35, _elapsed(), phase='erase')
                        if downloadinfo.bAllFlash:
                            self._log('i', 'erase whole flash.')
                            if not chip_set.erase_flash(True, None, None, self.retry, 1, 40):
                                raise Exception('erase whole flash fail.')
                            self._log('i', 'erase whole flash OK.')
                        else:
                            erase_idx = 0
                            for binfile in downloadinfo.vecbinInfo:
                                self._log('i', f'[{erase_idx}] erase flash.')
                                self._log('i', f'[{erase_idx}] start: 0x{binfile.iStartAddress:x}.')
                                self._log('i', f'[{erase_idx}] length: 0x{binfile.iFileLength:x}.')
                                if not chip_set.erase_flash(False, binfile.iStartAddress, binfile.iStartAddress + binfile.iFileLength, self.retry):
                                    raise Exception('erase flash fail.')
                                erase_idx += 1
                    if self.channel_number is not None:
                        self._push_factory_status('running', 45, _elapsed(), phase='write')
                    write_idx = 0
                    for binfile in downloadinfo.vecbinInfo:
                        self._log('i', f'[{write_idx}] write flash.')
                        self._log('i', f'[{write_idx}] start: 0x{binfile.iStartAddress:x}.')
                        self._log('i', f'[{write_idx}] length: 0x{binfile.iFileLength:x}.')
                        if not chip_set.download_flash(binfile.pfile, binfile.iStartAddress, self.retry, True, self.reset_type, self.link_check_type):
                            raise Exception('Write flash fail.')
                        write_idx += 1
                self._log('w', 'Write flash done.')
                if downloadinfo.bDownloadBin or downloadinfo.bDownloadDeviceID or downloadinfo.bDownloadDeviceName or (len(downloadinfo.expand_data_list) > 0):
                    self._log('i', 'protect flash...')
                    if not chip_set.un_protect_flash(protect=True):
                        self._log('e', 'protect flash fail.')
                    else:
                        self._log('i', 'protect flash OK.')
                if downloadinfo.safeinfo.write_safe_config:
                    self._log('i', 'write safe json content.')
                    if downloadinfo.aes_key:
                        for sedata in downloadinfo.safeinfo.security_data_list:
                            if sedata.name.find('aes_key') != -1:
                                sedata.data = downloadinfo.aes_key
                    (ret, msg) = chip_set.write_safe_json(downloadinfo.safeinfo)
                    if not ret:
                        self._log('e', msg)
                        raise Exception('Write safe json fail.')
                    self._log('w', 'write safe json done.')
                if self.channel_number is not None:
                    self._push_factory_status('running', 95, _elapsed(), phase='write_safe_json')
                if chip_set._flash_mid == 1269965 or chip_set._flash_mid == 1335501 or chip_set._flash_mid == 1401067:
                    if not th_flash_ctrl.tsingteng_flash_scratch_solution(chip_set._flash_mid):
                        raise Exception('Execute flash scratch solution fail.')
                result = True
            except Exception as e:
                result = False
                error_msg = str(e)
                self._log('e', error_msg)
        finally:
            if self.channel_number is not None:
                elapsed = _elapsed()
                if result:
                    self._push_factory_status('success', 100, elapsed)
                else:
                    self._push_factory_status('failure', 100, elapsed, error_msg)
            if self.reboot_after_download:
                self._log('i', 'do reboot from bootrom.')
                base_controller.do_reboot()
            if self.ser:
                self.ser.disconnect()
            end_time = time.time()
            elapsed_time = end_time - start_time
            if result:
                self._log('w', 'Download complete, all pass.')
                self._log('w', 'done.')
            else:
                self._log('e', 'Download fail.')
            self._log('i', f'Elapse time: {elapsed_time:.6f} seconds.')
        return (result, error_msg)
