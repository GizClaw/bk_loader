import time
from datetime import datetime
import os
from bkutils.common import ui_bridge
from bkutils.common.bk_out_config import BKOTPConfig
from bkutils.common.ui_bridge_data import TaskInfo
from bkutils.chip_controller.advanced_controller import AdvancedController
from .action_base import ActionBase
from ..chip_controller import BaseController
from ..chip_controller import get_chip_set_with_chip_id
from ..chip_controller import get_chip_set_with_chip_name
from ..bk_log import BKLog
from ..common.common import LINKCHECK, ReadInfo, parse_readinfo_otp, parse_writeinfo_otp
from ..common.random_bin_verify import maybe_verify_random_bin_after_get_bus

class Dump(ActionBase):

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

    def combine_base_task_list(self, readinfo: ReadInfo):
        if readinfo.bAllFlash:
            self.append_task('dump all')
        else:
            for bininfo in readinfo.vecbinInfo:
                task_name = 'dump 0x{:x}-0x{:x}'.format(bininfo.iStartAddress, bininfo.iStartAddress + bininfo.iFileLength)
                self.append_task(task_name)
        if readinfo.read_efuse:
            self.append_task('read efuse')
        if readinfo.read_otp:
            self.append_task('read otp')
        if readinfo.read_otp_efuse_auto:
            self.append_task('read otp/efuse auto')
        if readinfo.safeinfo.read_safe_config:
            self.append_task('read safe json')
        ui_bridge.task_list(self.task_list)

    def read_task(self, readinfo: ReadInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_base_task_list(readinfo)
                allow_change_linkcheck_obj = True
                linkcheck_obj_for_bus = None
                if (readinfo.read_otp or readinfo.read_otp_efuse_uid or readinfo.read_otp_efuse_auto or readinfo.read_efuse or readinfo.read_uid or readinfo.safeinfo.read_safe_config) and BKOTPConfig.must_use_bl1:
                    self.link_check_type = LINKCHECK.BOOTROM
                    allow_change_linkcheck_obj = False
                    linkcheck_obj_for_bus = self.link_check_type
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=linkcheck_obj_for_bus, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=allow_change_linkcheck_obj)
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
                BKLog.i('set baudrate to {0}...'.format(readinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=readinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(readinfo.work_baudrate))
                current_prog += 5
                BKLog.progress_log('BK', 'Dumping', int(current_prog))
                if len(readinfo.vecbinInfo) > 0:
                    if readinfo.read_path is not None:
                        readinfo.read_path = os.path.join(readinfo.read_path, datetime.strftime(datetime.now(), '%y_%m_%d_%H_%M_%S'))
                    total_prog = 80
                    prog_per_bin = total_prog / len(readinfo.vecbinInfo)
                    current_time = datetime.now()
                    fmt_time = current_time.strftime('%Y%m%d%H%M%S')
                    if readinfo.bAllFlash:
                        readinfo.vecbinInfo[0].iFileLength = int(chip_set._flash_cfg.flash_size / 8)
                    for rinfo in readinfo.vecbinInfo:
                        (root, ext) = os.path.splitext(rinfo.sFilePath)
                        if not ext:
                            ext = '.bin'
                        rinfo.sFilePath = f'{root}_0x{rinfo.iStartAddress:x}-0x{rinfo.iFileLength:x}_{fmt_time}{ext}'
                        if readinfo.read_path is not None:
                            if not os.path.exists(readinfo.read_path):
                                os.makedirs(readinfo.read_path)
                            rinfo.sFilePath = os.path.join(readinfo.read_path, rinfo.sFilePath)
                    BKLog.i('start read flash ...')
                    if readinfo.bAllFlash:
                        self.task_flag(True)
                        flash_size = int(chip_set._flash_cfg.flash_size / 8)
                        BKLog.i(f'read all flash path: {readinfo.vecbinInfo[0].sFilePath}')
                        BKLog.i(f'start: 0x{readinfo.vecbinInfo[0].iStartAddress:x}')
                        BKLog.i(f'length: 0x{flash_size:x}')
                        if not chip_set.dump_flash(readinfo.vecbinInfo[0].iStartAddress, flash_size, readinfo.vecbinInfo[0].sFilePath, self.retry, readinfo.bConsole):
                            raise Exception('Read flash fail.')
                        self.task_flag(False)
                    else:
                        read_idx = 0
                        for binfile in readinfo.vecbinInfo:
                            self.task_flag(True)
                            BKLog.i(f'[{read_idx}] read flash path:{binfile.sFilePath}')
                            BKLog.i(f'[{read_idx}] start: 0x{binfile.iStartAddress:x}')
                            BKLog.i(f'[{read_idx}] length: 0x{binfile.iFileLength:x}')
                            if not chip_set.dump_flash(binfile.iStartAddress, binfile.iFileLength, binfile.sFilePath, self.retry, readinfo.bConsole):
                                raise Exception('Read flash fail.')
                            read_idx += 1
                            self.task_flag(False)
                    BKLog.i('Read flash done.')
                if readinfo.flash_otp:
                    self.task_flag(True)
                    flashotpinfo = parse_readinfo_otp(readinfo.flash_otp)
                    if flashotpinfo is None:
                        raise Exception('Parse flash OTP info fail.')
                    for info in flashotpinfo:
                        BKLog.i('start read flash OTP @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        ret = chip_set.read_chip_flash_security(info[0], info[1], '', True)
                        if not ret:
                            raise Exception('Read flash OTP fail.')
                        BKLog.w('Read flash OTP done.')
                    self.task_flag(False)
                if readinfo.read_uid:
                    BKLog.i('start read chip UID ...')
                    (ret, uid) = chip_set.read_chip_uid()
                    if not ret:
                        raise Exception('Read UID fail.')
                    bytesuid = bytes(uid[:5])
                    BKLog.w('Read UID done.')
                    BKLog.w('UID is: ' + bytes.hex(bytesuid))
                if readinfo.read_efuse:
                    self.task_flag(True)
                    efuseinfo = parse_readinfo_otp(readinfo.read_efuse)
                    if efuseinfo is None:
                        raise Exception('Parse efuse read info fail.')
                    for info in efuseinfo:
                        if info[1] == 0:
                            BKLog.i('start read efuse all ...')
                        else:
                            BKLog.i('start read efuse @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        (ret, efuse) = chip_set.read_efuse(info[0], info[1])
                        if not ret or efuse is None:
                            BKLog.e('Read efuse fail.')
                            raise Exception('Read efuse fail.')
                        BKLog.w('Read efuse done.')
                        cnt = len(efuse)
                        for i in range(cnt):
                            BKLog.w(f'address: 0x{i + info[0]:x}, read = 0x{efuse[i]:x}')
                    self.task_flag(False)
                if readinfo.read_otp:
                    self.task_flag(True)
                    otpinfo = parse_readinfo_otp(readinfo.read_otp)
                    if otpinfo is None:
                        raise Exception('Parse OTP read info fail.')
                    for info in otpinfo:
                        BKLog.i('start read OTP @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        (otp, msg) = chip_set.read_chip_otp(info[0], info[1], readinfo.reverse_content)
                        if otp is None:
                            BKLog.e(msg)
                            raise Exception('Read OTP fail.')
                        BKLog.w('Read OTP done.')
                        bytesotp = bytes(otp)
                        BKLog.w('OTP stream: ' + bytes.hex(bytesotp))
                    self.task_flag(False)
                if readinfo.read_otp_efuse_auto:
                    self.task_flag(True)
                    auto_info = parse_readinfo_otp(readinfo.read_otp_efuse_auto)
                    if auto_info is None:
                        raise Exception('Parse OTP/Efuse auto read info fail.')
                    for info in auto_info:
                        BKLog.i('start read OTP/Efuse auto @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        (data, msg) = chip_set.read_otp_efuse_auto(info[0], info[1], readinfo.reverse_content)
                        if data is None:
                            BKLog.e(msg)
                            raise Exception('Read OTP/Efuse auto fail.')
                        BKLog.w('Read OTP/Efuse auto done.')
                        bytesdata = bytes(data)
                        BKLog.w('OTP/Efuse auto stream: ' + bytes.hex(bytesdata))
                    self.task_flag(False)
                if readinfo.safeinfo.read_safe_config:
                    self.task_flag(True)
                    (ret, msg) = chip_set.read_as_safe_json(readinfo.safeinfo)
                    if not ret:
                        BKLog.e(msg)
                        raise Exception('Read safe json fail.')
                    self.task_flag(False)
                    BKLog.i('Read safe json done.')
                if readinfo.read_otp_efuse_uid:
                    BKLog.i('start read efuse all ...')
                    (ret, efuse) = chip_set.read_efuse(0, 0)
                    if not ret:
                        raise Exception('Read efuse fail.')
                    BKLog.w('Read efuse done.')
                    cnt = len(efuse)
                    for i in range(cnt):
                        BKLog.w(f'address: 0x{i:x}, read = 0x{efuse[i]:x}')
                    BKLog.i('start read chip UID ...')
                    (ret, uid) = chip_set.read_chip_uid()
                    if not ret:
                        raise Exception('Read UID fail.')
                    bytesuid = bytes(uid[:5])
                    BKLog.w('Read UID done.')
                    BKLog.w('UID is: ' + bytes.hex(bytesuid))
                    otpinfo = parse_readinfo_otp(readinfo.read_otp_efuse_uid)
                    if otpinfo is None:
                        raise Exception('Parse OTP write info fail.')
                    for info in otpinfo:
                        BKLog.i('start read OTP @0x{:x}, '.format(info[0]) + 'length: {0}'.format(info[1]))
                        (otp, msg) = chip_set.read_chip_otp(info[0], info[1], readinfo.reverse_content)
                        if otp is None:
                            BKLog.e(msg)
                            raise Exception('Read OTP fail.')
                        BKLog.w('Read OTP done.')
                        bytesotp = bytes(otp)
                        BKLog.w('OTP stream: ' + bytes.hex(bytesotp))
                current_prog += 5
                BKLog.progress_log('BK', 'Dumping', int(current_prog))
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
                BKLog.i('Read complete, all pass.')
                BKLog.i('done.')
            else:
                BKLog.i('Read fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            if result:
                self.print_dump_file_info(readinfo)
            ui_bridge.end_flag('dump', result)
            return result

    def read_cbus_task(self, readinfo: ReadInfo):
        result = False
        start_time = time.time()
        base_controller = BaseController(serial_instance=self.ser)
        self._init_log_level(self.ser.ser.name, self.debug)
        current_prog = 1
        BKLog.progress_log('BK', 'Getting Bus', int(current_prog))
        try:
            try:
                self.combine_base_task_list(readinfo)
                allow_change_linkcheck_obj = True
                linkcheck_obj_for_bus = None
                if (readinfo.read_otp or readinfo.read_otp_efuse_uid or readinfo.read_efuse or readinfo.read_uid or readinfo.safeinfo.read_safe_config) and BKOTPConfig.must_use_bl1:
                    self.link_check_type = LINKCHECK.BOOTROM
                    allow_change_linkcheck_obj = False
                    linkcheck_obj_for_bus = self.link_check_type
                (tmp_res, linktype) = base_controller.get_bus(reset_type=self.reset_type, linkcheck_obj=linkcheck_obj_for_bus, reset_baudrate=self.reset_baudrate, max_try_count=self.getbus_times, link_key=self.link_key, allow_change_linkcheck_obj=allow_change_linkcheck_obj)
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
                BKLog.i('set baudrate to {0}...'.format(readinfo.work_baudrate))
                if not chip_set.set_baudrate(baudrate=readinfo.work_baudrate, delay_ms=20):
                    raise Exception('set baudrate {0} fail.'.format(readinfo.work_baudrate))
                current_prog += 5
                BKLog.progress_log('BK', 'Dumping', int(current_prog))
                if len(readinfo.vecbinInfo) > 0:
                    if readinfo.read_path is not None:
                        readinfo.read_path = os.path.join(readinfo.read_path, datetime.strftime(datetime.now(), '%y_%m_%d_%H_%M_%S'))
                    total_prog = 80
                    prog_per_bin = total_prog / len(readinfo.vecbinInfo)
                    current_time = datetime.now()
                    fmt_time = current_time.strftime('%Y%m%d%H%M%S')
                    if readinfo.bAllFlash:
                        readinfo.vecbinInfo[0].iFileLength = int(chip_set._flash_cfg.flash_size / 8)
                    for rinfo in readinfo.vecbinInfo:
                        (root, ext) = os.path.splitext(rinfo.sFilePath)
                        if not ext:
                            ext = '.bin'
                        rinfo.sFilePath = f'{root}_0x{rinfo.iStartAddress:x}-0x{rinfo.iFileLength:x}_{fmt_time}{ext}'
                        if readinfo.read_path is not None:
                            if not os.path.exists(readinfo.read_path):
                                os.makedirs(readinfo.read_path)
                            rinfo.sFilePath = os.path.join(readinfo.read_path, rinfo.sFilePath)
                    advctrl = AdvancedController(serial_instance=chip_set.ser)
                    BKLog.i('start read flash ...')
                    if readinfo.bAllFlash:
                        self.task_flag(True)
                        flash_size = int(chip_set._flash_cfg.flash_size / 8)
                        BKLog.i(f'read all flash path: {readinfo.vecbinInfo[0].sFilePath}')
                        BKLog.i(f'start: 0x{readinfo.vecbinInfo[0].iStartAddress:x}')
                        BKLog.i(f'length: 0x{flash_size:x}')
                        if not advctrl.enter_exit_cbus_mode_dbg(enter_exit=True, flash_addr=0, max_try_count=self.retry):
                            raise Exception('enter cbus mode for debug fail.')
                        if not chip_set.dump_flash(readinfo.vecbinInfo[0].iStartAddress, flash_size, readinfo.vecbinInfo[0].sFilePath, self.retry, readinfo.bConsole, cprog=current_prog, sprog=total_prog):
                            raise Exception('Read flash fail.')
                        if not advctrl.enter_exit_cbus_mode_dbg(enter_exit=False, flash_addr=0, max_try_count=self.retry):
                            raise Exception('exit cbus mode for debug fail.')
                        current_prog += total_prog
                        self.task_flag(False)
                    else:
                        read_idx = 0
                        for binfile in readinfo.vecbinInfo:
                            self.task_flag(True)
                            BKLog.i(f'[{read_idx}] read flash path:{binfile.sFilePath}')
                            BKLog.i(f'[{read_idx}] start: 0x{binfile.iStartAddress:x}')
                            BKLog.i(f'[{read_idx}] length: 0x{binfile.iFileLength:x}')
                            if not advctrl.enter_exit_cbus_mode_dbg(enter_exit=True, flash_addr=binfile.iStartAddress, max_try_count=self.retry):
                                raise Exception('enter cbus mode for debug fail.')
                            if not chip_set.dump_flash(binfile.iStartAddress, binfile.iFileLength, binfile.sFilePath, self.retry, readinfo.bConsole, cprog=current_prog, sprog=prog_per_bin):
                                raise Exception('Read flash fail.')
                            if not advctrl.enter_exit_cbus_mode_dbg(enter_exit=False, flash_addr=binfile.iStartAddress, max_try_count=self.retry):
                                raise Exception('exit cbus mode for debug fail.')
                            read_idx += 1
                            current_prog += prog_per_bin
                            self.task_flag(False)
                    BKLog.i('Read flash done.')
                current_prog += 5
                BKLog.progress_log('BK', 'Dumping', int(current_prog))
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
                BKLog.i('Read complete, all pass.')
                BKLog.i('done.')
            else:
                BKLog.i('Read fail.')
            BKLog.i(f'Elapse time: {elapsed_time:.6f} seconds.\n')
            if result:
                self.print_dump_file_info(readinfo)
            ui_bridge.end_flag('dump', result)
            return result

    def print_dump_file_info(self, readinfo: ReadInfo):
        if readinfo.read_path is None:
            return
        ui_bridge.dump_folder_info(readinfo.read_path)
        path_list = [binfile.sFilePath for binfile in readinfo.vecbinInfo]
        for path in path_list:
            if not os.path.exists(path):
                continue
            ui_bridge.dump_bin_info(path)
