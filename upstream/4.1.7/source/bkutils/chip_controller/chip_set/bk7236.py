import time
from typing import List, Tuple
from ...common.bk_out_config import BkDownloadFlowConfig, BkReadFlashMidConfig, BkSetBaudrateConfig
from .base_chip import BaseChip
from .bk7236_security import BK7236_Security
from .bk7236_high_baudrate import BK7236_HighBaudrate
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...bk_log import BKLog
from ...common.common import FLASH_SIZE_DEF, LINKCHECK, RESET_TYPE, FLASH_ERASE_CMD_EXT, FLASH_ERASE_CMD, safe_data, BinInfo, is_buf_all_0xff, BIT, BFD, crc32_ver2, bytes_reverse, bytes_reverse_per4bytes
from ...chip_controller import BaseController, FlashController, AdvancedController
from ...common.encrypt_helper import generate_random_8bytes, aes128_ecb_encrypt
import hashlib

class BK7236(BaseChip):
    CHIP_ID = 29238
    SECOND_ID = [540281616]
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init__(self):
        super().__init__()

    def set_high_baudrate(self, baudrate):
        """
        use apll and change uart to high baudrate
        """
        high_br = BK7236_HighBaudrate(serial_instance=self.ser)
        if not high_br.use_apll_set_baudrate(baudrate=baudrate):
            raise Exception(f'use apll set high baudrate {baudrate} fail.')
        base_ctrl = BaseController(serial_instance=self.ser)
        if base_ctrl.do_link_check(linkcheck_obj=LINKCHECK.BOOTROM, max_try_count=10):
            return True
        return False

    def align_sector_address_for_erase(self, addr: int, start_or_end: bool, reconnect_retry=False, reset_type=None, link_type=None, read_baudrate=1000000):
        flash_control = FlashController(self.ser, self._flash_cfg)
        erase_addr = int(addr / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
        baudrate_backup = self.ser.baudrate
        if not self.set_baudrate(read_baudrate):
            BKLog.w(f'Set baudrate: {read_baudrate} fail.')
            return False
        time.sleep(0.1)
        cnt = 5
        while cnt > 0:
            ret = flash_control.read_sector(erase_addr)
            if ret is not None:
                break
            cnt -= 1
        if ret is None:
            BKLog.e(f'read_sector fail @0x{erase_addr:x}.')
            return False
        cnt = 5
        while cnt > 0:
            res = self._erase_custom_size(erase_addr, FLASH_SIZE_DEF.SIZE_4K)
            if res:
                break
            cnt -= 1
        if not res:
            BKLog.e(f'erase_custom_size fail @0x{erase_addr:x}.')
            return False
        if not self.set_baudrate(baudrate_backup):
            BKLog.e(f'Set baudrate: {baudrate_backup} fail.')
            return False
        if start_or_end:
            ret = ret[:addr & 4095] + b'\xff' * (FLASH_SIZE_DEF.SIZE_4K - addr & 4095)
        else:
            ret = b'\xff' * (addr & 4095) + ret[addr & 4095:]
        if not self.write_and_check_sector(ret, erase_addr):
            BKLog.i('write sector @0x{:x} fail, retry'.format(erase_addr))
            if not self.retry_write_sector(erase_addr, ret, reconnect_bus=reconnect_retry, reset_type=reset_type, link_type=link_type):
                BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_addr))
                return False
        return True

    def align_sector_address_for_write(self, addr: int, start_or_end: bool, content: bytes, reconnect_retry=False, reset_type=None, link_type=None, read_baudrate=1000000):
        flash_control = FlashController(self.ser, self._flash_cfg)
        erase_addr = int(addr / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
        baudrate_backup = self.ser.baudrate
        if not self.set_baudrate(read_baudrate):
            BKLog.e(f'Set baudrate: {read_baudrate} fail.')
            return False
        time.sleep(0.1)
        cnt = 5
        while cnt > 0:
            ret = flash_control.read_sector(erase_addr)
            if ret is not None:
                break
            cnt -= 1
        if ret is None:
            BKLog.e(f'read_sector fail @0x{erase_addr:x}.')
            return False
        cnt = 5
        while cnt > 0:
            res = self._erase_custom_size(erase_addr, FLASH_SIZE_DEF.SIZE_4K)
            if res:
                break
            cnt -= 1
        if not res:
            BKLog.e(f'erase_custom_size fail @0x{erase_addr:x}.')
            return False
        if not self.set_baudrate(baudrate_backup):
            BKLog.e(f'Set baudrate: {baudrate_backup} fail.')
            return False
        if start_or_end:
            ret = ret[:addr & 4095] + content[:FLASH_SIZE_DEF.SIZE_4K - addr & 4095]
        else:
            ret = content[-(addr & 4095):] + ret[addr & 4095:]
        time.sleep(0.1)
        if not self.write_and_check_sector(ret, erase_addr):
            BKLog.i('write sector @0x{:x} fail, retry'.format(erase_addr))
            if not self.retry_write_sector(erase_addr, ret, reconnect_bus=reconnect_retry, reset_type=reset_type, link_type=link_type):
                BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_addr))
                return False
        return True

    def retry_write_sector(self, flash_addr: int, buf: bytes, recnt=3, reconnect_bus=False, reset_type=None, link_type=None, link_key=None):
        flash_control = FlashController(self.ser, self._flash_cfg)
        base_controller = BaseController(serial_instance=self.ser)
        cmd = FLASH_ERASE_CMD.SIZE_4K
        if self._flash_cfg.flash_size >= 268435456:
            cmd = FLASH_ERASE_CMD_EXT.SIZE_4K
        baudrate_backup = self.ser.baudrate
        if self._erase_custom_size(flash_addr, FLASH_SIZE_DEF.SIZE_4K) and self.write_and_check_sector(buf, flash_addr):
            return True
        if reconnect_bus:
            cnt = recnt
            while cnt > 0:
                ret = base_controller.reconnect_bus(reset_type=reset_type, linkcheck_obj=link_type, reset_baudrate=115200, max_retry_count=30, link_key=link_key)
                if ret:
                    time.sleep(0.01)
                    if self.set_baudrate(baudrate_backup):
                        erase_ret = self._erase_custom_size(flash_addr, FLASH_SIZE_DEF.SIZE_4K)
                        if erase_ret and self.write_and_check_sector(buf, flash_addr):
                            return True
                cnt -= 1
        else:
            cnt = recnt
            while cnt > 0:
                cnt -= 1
                ret = base_controller.reconnect_bus(reset_type=reset_type, linkcheck_obj=link_type, reset_baudrate=115200, max_retry_count=30, link_key=link_key)
                if ret:
                    time.sleep(0.1)
                    erase_ret = self._erase_custom_size(8359936, FLASH_SIZE_DEF.SIZE_4K)
                    if erase_ret:
                        BKLog.i('enter write outter flash mode...')
                        if self.reboot_and_enter_write_outter_flash_mode(reset_type):
                            time.sleep(0.2)
                            BKLog.i('parse outter flash info...')
                            if not self.parse_flash_info():
                                continue
                            if self.set_baudrate(baudrate_backup):
                                erase_ret = self._erase_custom_size(flash_addr, FLASH_SIZE_DEF.SIZE_4K)
                                if erase_ret and self.write_and_check_sector(buf, flash_addr):
                                    return True
        return False

    def retry_write_sector_cbus(self, flash_addr: int, buf: bytes, recnt=5, reset_type=None, link_type=None, partition_start=None, partition_size=None):
        base_controller = BaseController(serial_instance=self.ser)
        adctrl = AdvancedController(serial_instance=self.ser)
        baudrate_backup = self.ser.baudrate
        cnt = recnt
        while cnt > 0:
            self.ser.reset(baudrate=115200)
            (ret, linktype) = base_controller.get_bus(reset_type=reset_type, linkcheck_obj=None, max_try_count=30)
            if ret:
                time.sleep(0.01)
                if self.set_baudrate(baudrate_backup) and adctrl.enter_exit_cbus_mode(self._flash_cfg.flash_size, True, partition_start, partition_size, flash_addr, 60) and self.write_and_check_sector(buf, flash_addr):
                    return True
            cnt -= 1
        return False

    def retry_write_sector_cbus_dbg(self, flash_addr: int, buf: bytes, recnt=5, reset_type=None, link_type=None):
        base_controller = BaseController(serial_instance=self.ser)
        adctrl = AdvancedController(serial_instance=self.ser)
        baudrate_backup = self.ser.baudrate
        cnt = recnt
        while cnt > 0:
            self.ser.reset(baudrate=115200)
            (ret, linktype) = base_controller.get_bus(reset_type=reset_type, linkcheck_obj=None, max_try_count=30)
            if ret:
                time.sleep(0.01)
                if self.set_baudrate(baudrate_backup) and adctrl.enter_exit_cbus_mode_dbg(True, flash_addr, 60) and self.write_and_check_sector(buf, flash_addr):
                    return True
            cnt -= 1
        return False

    def read_chip_flash_security(self, addr: int, oplen: int, file, console: bool=False):
        flash_control = FlashController(self.ser, self._flash_cfg)
        file_buf = b''
        BKLog.i('Start read flash security area.')
        rxbuf = flash_control.read_flash_security(addr, oplen)
        if rxbuf is None:
            return False
        file_buf += rxbuf
        BKLog.i('End read flash security.')
        if console:
            BKLog.w('out stream: ' + bytes.hex(file_buf))
        else:
            with open(file, 'wb') as f:
                f.write(file_buf[:oplen])
                f.close()
        return True

    def write_chip_flash_security(self, addr: int, buf):
        flash_control = FlashController(self.ser, self._flash_cfg)
        oplen = len(buf)
        if (addr & 4095) + oplen > 512:
            BKLog.e('start address+data length must not be over 0x200')
            return False
        readaddr = addr & 16773120
        rd_buf = flash_control.read_flash_security(readaddr, 512)
        wr_buf = rd_buf[:addr & 4095] + buf + rd_buf[(addr & 4095) + oplen:]
        time.sleep(0.05)
        BKLog.i('Start write flash security area.')
        flash_control._write_flash_reg_enable()
        if not flash_control.erase_flash_security(addr):
            return False
        time.sleep(0.05)
        flash_control._write_flash_reg_enable()
        if not flash_control.write_flash_security(readaddr, wr_buf[:80]):
            return False
        flash_control._write_flash_reg_enable()
        if not flash_control.write_flash_security(readaddr + 80, wr_buf[80:256]):
            return False
        flash_control._write_flash_reg_enable()
        if not flash_control.write_flash_security(readaddr + 256, wr_buf[256:336]):
            return False
        flash_control._write_flash_reg_enable()
        if not flash_control.write_flash_security(readaddr + 336, wr_buf[336:]):
            return False
        BKLog.i('End write flash security.')
        time.sleep(0.05)
        return True

    def erase_chip_flash_security(self, addr: int, oplen):
        """
        0x152085 flash otp area: 0x001000~0x0011ff, 0x002000~0x0021ff, 0x003000~0x0031ff
        erase command will ignore last 5bit, 
        so if the erase address is 0x001100, the operation will erase whole 0x001000~0x0011ff address
        """
        flash_control = FlashController(self.ser, self._flash_cfg)
        BKLog.i('Start erase flash security area.')
        flash_control._write_flash_reg_enable()
        if not flash_control.erase_flash_security(addr):
            return False
        BKLog.i('End erase flash security.')
        return True

    def _erase_flash_security_with_reconnect_bus(self, addr: int, reconnect_bus: bool=True) -> Tuple[bool, bool]:
        flash_control = FlashController(self.ser, self._flash_cfg)
        (ret, permission_denied) = flash_control.erase_flash_security_new(addr)
        if ret:
            return (True, False)
        if not permission_denied:
            return (False, False)
        if not reconnect_bus:
            return (False, True)
        if BaseController.link_check_obj == LINKCHECK.BOOTROM:
            return (False, True)
        if not self._reboot_and_reconnect_bus(LINKCHECK.BOOTROM):
            return (False, True)
        return flash_control.erase_flash_security_new(addr)

    def _erase_flash_security(self, addr: int) -> bool:
        (ret, permission_denied) = self._erase_flash_security_with_reconnect_bus(addr, reconnect_bus=True)
        if not ret:
            BKLog.e(f'erase flash security fail @0x{addr:x}.')
            return False
        return True

    def set_baudrate_correct(self):
        return True

    def parse_flash_info(self):
        fmp = self.BOOTROM_PROTOCOL.GetFlashMidProtocol()
        max_try = max(1, BkReadFlashMidConfig.retry_count)
        delay_s = max(0.0, BkReadFlashMidConfig.delay_after_fail_ms / 1000.0)
        timeout = BkReadFlashMidConfig.wait_response_timeout_sec
        for attempt in range(max_try):
            (res, content) = self.ser.write_cmd_and_wait_response(fmp.cmd(159), fmp.expect_length, timeout)
            if res and fmp.response_check(content):
                tmp_mid = fmp.get_mid(content)
                BKLog.i(f'flash mid is 0x{tmp_mid:x}')
                self._flash_mid = tmp_mid
                self._flash_cfg.parse_flash_info(self._flash_mid)
                if attempt > 0:
                    BKLog.i(f'parse flash info OK after {attempt + 1} attempt(s).')
                return True
            BKLog.w(f'read flash mid fail (attempt {attempt + 1}/{max_try}).')
            if attempt < max_try - 1:
                time.sleep(delay_s)
        BKLog.e(f'read flash mid fail after {max_try} attempt(s).')
        return False

    def write_tool_version(self, ver: str):
        """
        write version info to flash OTP (addr: 0x000100)
        """
        flash_ctrl = FlashController(self.ser, self._flash_cfg)
        by_ver = ver.encode('utf-8')
        addr = 4096
        BKLog.i(f'version info: {by_ver}')
        flash_ctrl._write_flash_reg_enable()
        time.sleep(0.05)
        if not flash_ctrl.erase_flash_security(addr):
            BKLog.e(f'erase flash OTP @0x{addr:x} fail.')
            return False
        time.sleep(0.05)
        flash_ctrl._write_flash_reg_enable()
        time.sleep(0.05)
        if not flash_ctrl.write_flash_security(addr, by_ver):
            BKLog.e(f'write flash OTP @0x{addr:x} fail.')
            return False
        time.sleep(0.1)
        read_ver = flash_ctrl.read_flash_security(addr, len(by_ver))
        if read_ver is None:
            BKLog.e(f'read flash OTP @0x{addr:x} fail.')
            return False
        if read_ver != by_ver:
            BKLog.e(f'data compare fail, read: {read_ver}, write: {by_ver}')
            return False
        return True

    def pre_check_image_file(self, bin_list: list):
        return True

    def pre_check_img_file_crc(self, bin_list: list):
        return

    def pre_set_efuse_nocrc(self):
        return True

    def set_baudrate(self, baudrate, delay_ms=20, max_retry_cnt=5):
        cmd_delay_ms = BkSetBaudrateConfig.cmd_delay_ms
        switch_delay_ms = BkSetBaudrateConfig.switch_delay_ms
        wait_response_timeout_ms = BkSetBaudrateConfig.wait_response_timeout_ms
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
                    if base_ctrl.do_link_check(linkcheck_obj=BaseController.link_check_obj, max_try_count=10):
                        return True
                    BKLog.w('reconnect bus to retry')
                    if not base_ctrl.reconnect_bus(reset_type=RESET_TYPE.DTR_RTS, linkcheck_obj=None, max_retry_count=20):
                        BKLog.e('reconnect bus fail')
                        BKLog.e('baudrate switch fail')
                        return False
                    cnt -= 1
                    continue
            elif baudrate == 3000000:
                BKLog.w('use apll to set high baudrate.')
                if self.set_high_baudrate(baudrate):
                    return True
                BKLog.w(f'use apll to set high baudrate:{baudrate} OK.')
            else:
                BKLog.e(f'not support baudrate: {baudrate}')
            BKLog.e('baudrate switch fail')
            return False
        BKLog.i('ignore baudrate switch')
        return True

    def un_protect_flash(self, protect: bool):
        flash_control = FlashController(self.ser, self._flash_cfg)
        if protect:
            return flash_control.protect_flash()
        return flash_control.unprotect_flash()

    def read_and_check_sector(self, addr: int, recnt=5):
        flash_control = FlashController(self.ser, self._flash_cfg)
        ret = None
        cnt = recnt
        while cnt > 0:
            ret = flash_control.read_sector(addr)
            if ret and flash_control.check_crc_ver2(ret, addr, FLASH_SIZE_DEF.SIZE_4K, recnt=recnt):
                return ret
            cnt -= 1
        BKLog.e('Read and check sector @0x{:x} fail.'.format(addr))
        return None

    def write_and_check_sector(self, buf_sec: bytes, addr: int):
        flash_control = FlashController(self.ser, self._flash_cfg)
        length = len(buf_sec)
        if not flash_control.write_sector(addr, buf_sec):
            BKLog.e(f'Write sector @0x{addr:x} fail, buf length: 0x{length:x}')
            return False
        if not flash_control.check_crc_ver2(buf_sec, addr, length):
            BKLog.e('Check CRC32 @0x{:x}, '.format(addr) + 'len: 0x{:x} fail.'.format(length))
            return False
        return True

    def _write_sector_only(self, buf_sec: bytes, addr: int) -> bool:
        flash_control = FlashController(self.ser, self._flash_cfg)
        length = len(buf_sec)
        if not flash_control.write_sector(addr, buf_sec):
            BKLog.e(f'Write sector @0x{addr:x} fail, buf length: 0x{length:x}')
            return False
        return True

    def _verify_crc_range(self, wbuf: bytes, c0: int, length: int, start_addr: int) -> bool:
        if length <= 0:
            return True
        flash_control = FlashController(self.ser, self._flash_cfg)
        chunk = wbuf[c0:c0 + length]
        timeout = max(1.8, 1.8 * (length / FLASH_SIZE_DEF.SIZE_4K))
        if not flash_control.check_crc_ver2(chunk, start_addr + c0, length, timeout=timeout):
            BKLog.e('Check CRC32 @0x{:x}, len: 0x{:x} fail.'.format(start_addr + c0, length))
            return False
        return True

    def _verify_crc_chunk_with_recover(self, wbuf: bytes, c0: int, length: int, start_addr: int, retry=5, reconnect_retry=False, reset_type=None, link_type=None):
        if self._verify_crc_range(wbuf, c0, length, start_addr):
            return True
        BKLog.i('chunk crc verify fail @0x{:x}-0x{:x}, recover per 4K'.format(start_addr + c0, start_addr + c0 + length))
        i = c0
        end = c0 + length
        while i < end:
            sec = wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]
            if not is_buf_all_0xff(sec):
                if not self.retry_write_sector(start_addr + i, sec, retry, reconnect_retry, reset_type, link_type):
                    return False
            i += FLASH_SIZE_DEF.SIZE_4K
        return True

    def _crc_chunk_verify_bounds(self, file_offset: int, file_len: int, crc_chunk: int):
        at_boundary = file_offset > 0 and file_offset % crc_chunk == 0
        at_eof = file_offset == file_len
        if not at_boundary and (not at_eof):
            return
        remainder = file_offset % crc_chunk
        c0 = file_offset - (remainder if remainder else crc_chunk)
        if c0 < 0:
            c0 = 0
        if file_offset <= c0:
            return
        return (c0, file_offset)

    def erase_flash(self, full_erase: bool, start_addr=None, end_addr=None, retry=5, cprog=0, sprog=100):
        flash_control = FlashController(self.ser, self._flash_cfg)
        if full_erase:
            BKLog.i('erase all chip.')
            BKLog.progress_log('BK', 'Erasing Flash', int(cprog))
            erase_res = False
            for _ in range(retry):
                erase_res = self._erase_all()
                if erase_res:
                    break
                BKLog.i('chip erase fail, retry')
            if not erase_res:
                raise Exception('chip erase fail.')
            BKLog.progress_log('BK', 'Erasing Flash', int(cprog + sprog))
        else:
            BKLog.i('erase start address @0x{:x}, '.format(start_addr) + 'end address @0x{:x}.'.format(end_addr))
            if start_addr is None or end_addr is None:
                BKLog.e('Error, address parameters is None.')
                return False
            if start_addr > end_addr:
                BKLog.e('Error, start address is over end.')
                return False
            erase_size = end_addr - start_addr
            if erase_size == 0:
                BKLog.w('erase size is 0, skip erase.')
                return True
            i = 0
            while i < erase_size:
                task_progress = 100 * i / erase_size
                BKLog.progress_log('BK', 'Erasing Flash', int(task_progress), task_progress=True)
                if i % (FLASH_SIZE_DEF.SIZE_4K * 40) == 0:
                    current_progress = cprog + sprog * i / erase_size
                    BKLog.progress_log('BK', 'Erasing Flash', int(current_progress))
                if erase_size - i > int(FLASH_SIZE_DEF.SIZE_64K):
                    if start_addr + i & 65535:
                        cnt = retry
                        ret = False
                        while cnt > 0 and (not ret):
                            BKLog.d('Erase sector @0x{:x} .'.format(start_addr + i))
                            ret = self._erase_custom_size(start_addr + i, FLASH_SIZE_DEF.SIZE_4K)
                            cnt -= 1
                        if not ret:
                            BKLog.e('Erase sector @0x{:x} fail.'.format(start_addr + i))
                            return False
                        i += FLASH_SIZE_DEF.SIZE_4K
                    else:
                        cnt = retry
                        ret = False
                        while cnt > 0 and (not ret):
                            BKLog.d('Erase block(64K) @0x{:x} .'.format(start_addr + i))
                            ret = self._erase_custom_size(start_addr + i, FLASH_SIZE_DEF.SIZE_64K)
                            cnt -= 1
                        if not ret:
                            BKLog.e('Erase block(64K) @0x{:x} fail.'.format(start_addr + i))
                            return False
                        i += FLASH_SIZE_DEF.SIZE_64K
                else:
                    cnt = retry
                    ret = False
                    while cnt > 0 and (not ret):
                        BKLog.d('Erase sector @0x{:x} .'.format(start_addr + i))
                        ret = self._erase_custom_size(start_addr + i, FLASH_SIZE_DEF.SIZE_4K)
                        cnt -= 1
                    if not ret:
                        BKLog.e('Erase sector @0x{:x} fail.'.format(start_addr + i))
                        return False
                    i += FLASH_SIZE_DEF.SIZE_4K
            BKLog.i('end erase.')
        return True

    def _reboot_and_reconnect_bus(self, linkcheck_obj: LINKCHECK) -> bool:
        if not BaseController.allow_change_linkcheck_obj:
            return False
        BKLog.i(f'reboot and reconnect bus to {linkcheck_obj}')
        backup_baudrate = self.ser.baudrate
        base_controller = BaseController(serial_instance=self.ser)
        base_controller.do_reboot()
        if not base_controller.reconnect_bus(reset_type=RESET_TYPE.MULTI, linkcheck_obj=linkcheck_obj, max_retry_count=20):
            BKLog.e('reconnect bus fail')
            return False
        if not self.set_baudrate(backup_baudrate):
            BKLog.e('set baudrate fail')
            return False
        return True

    def _erase_all_with_reconnect_bus(self, reconnect_bus: bool=True) -> Tuple[bool, bool]:
        flash_control = FlashController(self.ser, self._flash_cfg)
        (ret, permission_denied) = flash_control.erase_all()
        if ret:
            return (True, False)
        if not permission_denied:
            return (False, False)
        if not reconnect_bus:
            return (False, True)
        if BaseController.link_check_obj == LINKCHECK.BOOTROM:
            return (False, True)
        if not self._reboot_and_reconnect_bus(LINKCHECK.BOOTROM):
            return (False, True)
        return flash_control.erase_all()

    def _erase_all(self) -> bool:
        (ret, permission_denied) = self._erase_all_with_reconnect_bus(reconnect_bus=True)
        if not ret:
            BKLog.e('erase all fail')
            return False
        return True

    def _erase_custom_size_with_reconnect(self, flash_addr: int, erase_size: int, reconnect_bus: bool=True) -> Tuple[bool, bool]:
        flash_control = FlashController(self.ser, self._flash_cfg)
        (ret, permission_denied) = flash_control.erase_custom_size_new(flash_addr, erase_size)
        if ret:
            return (True, False)
        if not permission_denied:
            return (False, False)
        if not reconnect_bus:
            return (False, True)
        if BaseController.link_check_obj == LINKCHECK.BOOTROM:
            return (False, True)
        if not self._reboot_and_reconnect_bus(LINKCHECK.BOOTROM):
            return (False, True)
        return flash_control.erase_custom_size_new(flash_addr, erase_size)

    def _erase_custom_size(self, flash_addr: int, erase_size: int) -> bool:
        (ret, permission_denied) = self._erase_custom_size_with_reconnect(flash_addr, erase_size, reconnect_bus=True)
        if not ret:
            BKLog.e(f'erase custom size fail @0x{flash_addr:x}, size: {erase_size}')
            return False
        return True

    def download_flash(self, wbuf: bytes, start_addr: int, retry=5, reconnect_retry=False, reset_type=None, link_type=None, cprog=0, sprog=100):
        file_len = len(wbuf)
        if file_len % 4096:
            wbuf += b'\xff' * (4096 - file_len % 4096)
            file_len = len(wbuf)
        crc_chunk = BkDownloadFlowConfig.crc_verify_chunk_bytes
        BKLog.i('write flash start @0x{:x}, '.format(start_addr) + 'length: 0x{:x}'.format(file_len))
        i = 0
        while i < file_len:
            task_progress = 100 * i / file_len
            BKLog.progress_log('BK', 'Writing Flash', int(task_progress), task_progress=True)
            if i % (FLASH_SIZE_DEF.SIZE_4K * 40) == 0:
                current_progress = cprog + sprog * i / file_len
                BKLog.progress_log('BK', 'Writing Flash', int(current_progress))
            sec = wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]
            if not is_buf_all_0xff(sec):
                BKLog.d('write sector @0x{:x} .'.format(i + start_addr))
                flash_addr = i + start_addr
                write_ok = self._write_sector_only(sec, flash_addr)
                if not write_ok:
                    BKLog.i('write sector @0x{:x} fail, retry'.format(flash_addr))
                    if not self.retry_write_sector(flash_addr, sec, retry, reconnect_retry, reset_type, link_type):
                        BKLog.e('write sector @0x{:x} by retry fail.'.format(flash_addr))
                        return False
            i += FLASH_SIZE_DEF.SIZE_4K
            bounds = self._crc_chunk_verify_bounds(i, file_len, crc_chunk)
            if bounds is not None:
                (c0, c1) = bounds
                if not self._verify_crc_chunk_with_recover(wbuf, c0, c1 - c0, start_addr, retry, reconnect_retry, reset_type, link_type):
                    BKLog.e('chunk crc verify fail @0x{:x}, len: 0x{:x}'.format(start_addr + c0, c1 - c0))
                    return False
        return True

    def download_flash_checkCRC_at_end(self, wbuf: bytes, start_addr: int, retry=5, reconnect_retry=False, reset_type=None, link_type=None, read_baudrate=115200):
        file_len = len(wbuf)
        if file_len % 256:
            wbuf += b'\xff' * (256 - file_len % 256)
            file_len = len(wbuf)
        end_addr = start_addr + file_len
        BKLog.i('write flash start @0x{:x}, '.format(start_addr) + 'length: 0x{:x}'.format(file_len))
        buf_backup = wbuf
        start_backup = start_addr
        len_backup = file_len
        flash_ctrl = FlashController(serial_instance=self.ser, flash_cfg=self._flash_cfg)
        if start_addr & 4095:
            if not self.align_sector_address_for_write(start_addr, True, wbuf, reconnect_retry, reset_type=reset_type, link_type=link_type, read_baudrate=read_baudrate):
                BKLog.e('Align start address @0x{:x} fail.'.format(start_addr))
                return False
            wbuf = wbuf[FLASH_SIZE_DEF.SIZE_4K - start_addr & 4095:]
            start_addr = int((start_addr + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
            file_len = len(wbuf)
        if end_addr & 4095:
            if not self.align_sector_address_for_write(end_addr, False, wbuf, reconnect_retry, reset_type=reset_type, link_type=link_type, read_baudrate=read_baudrate):
                BKLog.e('Align end address @0x{:x} fail.'.format(end_addr))
                return False
            wbuf = wbuf[:len(wbuf) - (end_addr & 4095)]
            end_addr = int(end_addr / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
            file_len = len(wbuf)
        i = 0
        while i < file_len:
            task_progress = 100 * i / file_len
            BKLog.progress_log('BK', 'Writing Flash', int(task_progress), task_progress=True)
            current_progress = 100 * i / file_len
            BKLog.progress_log('BK', 'Writing Flash', int(current_progress))
            if not is_buf_all_0xff(wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]):
                BKLog.d('write sector @0x{:x} .'.format(i + start_addr))
                if not flash_ctrl.write_sector(i + start_addr, wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]):
                    return False
            i += FLASH_SIZE_DEF.SIZE_4K
        if not flash_ctrl.check_crc_ver2(buf_backup, start_backup, len_backup):
            BKLog.w('Check CRC for address @0x{:x} fail.'.format(end_addr))
            return False
        return True

    def dump_flash(self, start, oplen, file, recnt=5, console=False, cprog=0, sprog=100):
        file_buf = b''
        cnt = recnt
        i = 0
        flash_control = FlashController(self.ser, self._flash_cfg)
        while i < oplen:
            task_progress = 100 * i / oplen
            BKLog.progress_log('BK', 'Reading Flash', int(task_progress), task_progress=True)
            current_progress = cprog + sprog * i / oplen
            BKLog.progress_log('BK', 'Reading Flash', int(current_progress))
            ret = self.read_and_check_sector(start + i, cnt)
            if ret == None:
                BKLog.e('Read flash fail.')
                return False
            file_buf += ret
            i += FLASH_SIZE_DEF.SIZE_4K
        if console:
            BKLog.w('out stream: ' + bytes.hex(file_buf[:oplen]))
        else:
            with open(file, 'wb') as f:
                f.write(file_buf[:oplen])
                f.close()
        return True

    def write_flash_info(self, flash_addr, buf):
        """
        write device name or mac to flash by flash address
        """
        bin = BinInfo(iStartAddress=flash_addr, iFileLength=len(buf), pfile=buf)
        if not self.align_all_bin_buf([bin], for_erase=False):
            BKLog.e(f'Align all buf fail @0x{flash_addr:x}')
            return False
        if not self.download_flash(bin.pfile, bin.iStartAddress, reconnect_retry=True):
            BKLog.e(f'Download flash fail @0x{bin.iStartAddress:x}')
            return False
        return True

    def download_flash_cbus(self, wbuf: bytes, partition_start: int, partition_size: int, start_addr: int, retry=5, reset_type=None, link_type=None, cprog=0, sprog=100):
        file_len = len(wbuf)
        BKLog.i(f'original buf len: 0x{file_len:x}')
        page_write = False
        if file_len % 4096:
            wbuf += b'\xff' * (4096 - file_len % 4096)
            file_len = len(wbuf)
        BKLog.i('write flash start @0x{:x}, '.format(start_addr) + 'length: 0x{:x}'.format(file_len))
        adctrl = AdvancedController(serial_instance=self.ser)
        BKLog.i('enter cbus mode...')
        if not adctrl.enter_exit_cbus_mode(self._flash_cfg.flash_size, True, partition_start, partition_size, start_addr, 50):
            BKLog.e('enter cbus mode fail.')
            return False
        BKLog.i('enter cbus mode done.')
        i = 0
        write_ok = True
        while i < file_len:
            current_progress = cprog + sprog * i / file_len
            BKLog.progress_log('BK', 'Writing Flash', int(current_progress))
            if not is_buf_all_0xff(wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]) and (not self.write_and_check_sector(wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K], i + start_addr)) and (not self.retry_write_sector_cbus(i + start_addr, wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K], retry, reset_type, link_type, partition_start, partition_size)):
                write_ok = False
                break
            i += FLASH_SIZE_DEF.SIZE_4K
        BKLog.i('exit cbus mode...')
        if not adctrl.enter_exit_cbus_mode(self._flash_cfg.flash_size, False, partition_start, partition_size, start_addr):
            BKLog.e('exit cbus mode fail.')
            return False
        return True

    def download_flash_cbus_dbg(self, wbuf: bytes, start_addr: int, retry=5, reset_type=None, link_type=None, cprog=0, sprog=100):
        file_len = len(wbuf)
        BKLog.i(f'original buf len: 0x{file_len:x}')
        page_write = False
        if file_len % 4096:
            wbuf += b'\xff' * (4096 - file_len % 4096)
            file_len = len(wbuf)
        BKLog.i('write flash start @0x{:x}, '.format(start_addr) + 'length: 0x{:x}'.format(file_len))
        adctrl = AdvancedController(serial_instance=self.ser)
        BKLog.i('enter cbus mode debug...')
        if not adctrl.enter_exit_cbus_mode_dbg(True, start_addr, 50):
            BKLog.e('enter cbus mode debug fail.')
            return False
        BKLog.i('enter cbus mode debug done.')
        i = 0
        while i < file_len:
            current_progress = cprog + sprog * i / file_len
            BKLog.progress_log('BK', 'Writing Flash', int(current_progress))
            if not is_buf_all_0xff(wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K]) and (not self.write_and_check_sector(wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K], i + start_addr)) and (not self.retry_write_sector_cbus_dbg(i + start_addr, wbuf[i:i + FLASH_SIZE_DEF.SIZE_4K], retry, reset_type, link_type)):
                return False
            i += FLASH_SIZE_DEF.SIZE_4K
        BKLog.i('exit cbus mode debug...')
        if not adctrl.enter_exit_cbus_mode_dbg(False, start_addr):
            BKLog.e('exit cbus mode debug fail.')
            return False
        return True

    def align_all_bin_buf(self, binlist: List[BinInfo], for_erase=False, reconnect_retry=False, reset_type=None, link_type=None, retry_cnt=5):
        """
        align start or end address for each bin
        """
        flash_control = FlashController(self.ser, self._flash_cfg)
        mask_4k = -4096
        for bin in binlist:
            BKLog.d(f'start address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x}')
            original_start_addr = bin.iStartAddress
            original_file_length = bin.iFileLength
            if not bin.bDataPort:
                BKLog.i('bin is not data port, skip align.')
                continue
            if bin.iStartAddress & 4095:
                BKLog.d(f'align start address: 0x{bin.iStartAddress:x}')
                erase_start_addr = int(bin.iStartAddress) & mask_4k
                read_retry_cnt = retry_cnt
                while read_retry_cnt > 0:
                    original_4k_sector_data = flash_control.read_sector(erase_start_addr)
                    if original_4k_sector_data is not None:
                        break
                    read_retry_cnt -= 1
                if original_4k_sector_data is None:
                    BKLog.e(f'read_sector fail @0x{erase_start_addr:x}.')
                    return False
                erase_retry_cnt = retry_cnt
                while erase_retry_cnt > 0:
                    erase_ret = self._erase_custom_size(erase_start_addr, FLASH_SIZE_DEF.SIZE_4K)
                    if erase_ret:
                        break
                    erase_retry_cnt -= 1
                if not erase_ret:
                    BKLog.e(f'erase_custom_size fail @0x{erase_start_addr:x}.')
                    return False
                is_start_end_in_same_4k_sector = False
                if erase_start_addr == bin.iStartAddress + bin.iFileLength & mask_4k:
                    is_start_end_in_same_4k_sector = True
                pending_start_point = bin.iStartAddress & 4095
                if is_start_end_in_same_4k_sector:
                    pending_end_point = bin.iStartAddress + bin.iFileLength & 4095
                else:
                    pending_end_point = FLASH_SIZE_DEF.SIZE_4K
                pending_file_length = pending_end_point - pending_start_point
                if for_erase:
                    end_sector_data = original_4k_sector_data[:pending_start_point] + b'\xff' * pending_file_length + original_4k_sector_data[pending_end_point:]
                else:
                    end_sector_data = original_4k_sector_data[:pending_start_point] + bin.pfile[:pending_file_length] + original_4k_sector_data[pending_end_point:]
                bin.iStartAddress = erase_start_addr + FLASH_SIZE_DEF.SIZE_4K
                bin.iFileLength = bin.iFileLength - pending_file_length if not is_start_end_in_same_4k_sector else 0
                if not for_erase:
                    bin.pfile = bin.pfile[pending_file_length:]
                if not self.write_and_check_sector(end_sector_data, erase_start_addr):
                    BKLog.i('write sector @0x{:x} fail, retry'.format(erase_start_addr))
                    if not self.retry_write_sector(erase_start_addr, end_sector_data, reconnect_bus=reconnect_retry, reset_type=reset_type, link_type=link_type):
                        BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_start_addr))
                        return False
                BKLog.d(f'aligned start address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x}')
            if bin.iStartAddress + bin.iFileLength & 4095 and bin.bDataPort:
                bin_end_addr = bin.iStartAddress + bin.iFileLength
                BKLog.d(f'align end address: 0x{bin_end_addr:x}')
                erase_start_addr = int(bin_end_addr) & mask_4k
                read_retry_cnt = retry_cnt
                while read_retry_cnt > 0:
                    original_4k_sector_data = flash_control.read_sector(erase_start_addr)
                    if original_4k_sector_data is not None:
                        break
                    read_retry_cnt -= 1
                if original_4k_sector_data is None:
                    BKLog.e(f'read_sector fail @0x{erase_start_addr:x}.')
                    return False
                erase_retry_cnt = retry_cnt
                while erase_retry_cnt > 0:
                    erase_ret = self._erase_custom_size(erase_start_addr, FLASH_SIZE_DEF.SIZE_4K)
                    if erase_ret:
                        break
                    erase_retry_cnt -= 1
                if not erase_ret:
                    BKLog.e(f'erase_custom_size fail @0x{erase_start_addr:x}.')
                    return False
                pending_start_point = 0
                pending_end_point = bin_end_addr & 4095
                pending_file_length = pending_end_point - pending_start_point
                if for_erase:
                    end_sector_data = b'\xff' * pending_file_length + original_4k_sector_data[pending_end_point:]
                else:
                    end_sector_data = bin.pfile[-pending_file_length:] + original_4k_sector_data[pending_end_point:]
                bin.iFileLength = bin.iFileLength - pending_file_length
                if not for_erase:
                    bin.pfile = bin.pfile[:bin.iFileLength]
                if not self.write_and_check_sector(end_sector_data, erase_start_addr):
                    BKLog.i('write sector @0x{:x} fail, retry'.format(erase_start_addr))
                    if not self.retry_write_sector(erase_start_addr, end_sector_data, reconnect_bus=reconnect_retry, reset_type=reset_type, link_type=link_type):
                        BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_start_addr))
                        return False
                BKLog.d(f'aligned end address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x}')
            BKLog.i(f'original start address: 0x{original_start_addr:x}, length: 0x{original_file_length:x}, aligned start address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x},subsequent processing will be done using the aligned version of start address and length.')
        return True

    def check_aes_key_enable(self):
        return 1

    def check_aes_key_otp_data(self):
        return 0

    def check_aes_key_otp_permission(self):
        return 0

    def read_bl2_version(self):
        flashctrl = FlashController(serial_instance=self.ser, flash_cfg=self._flash_cfg)
        readout = flashctrl.read_flash_size(12292, 4)
        if readout is None:
            return False
        version = readout[0] + (readout[1] << 8) + (readout[2] << 16) + (readout[3] << 24)
        return version

    def reboot_and_enter_write_outter_flash_mode(self, reset_type=RESET_TYPE.DTR_RTS, max_retry_count=10):
        basectrl = BaseController(serial_instance=self.ser)
        adctrl = AdvancedController(serial_instance=self.ser)
        BKLog.i('do reboot...')
        if reset_type == RESET_TYPE.DTR_RTS:
            basectrl.do_reset(reset_type=RESET_TYPE.DTR_RTS, baudrate=115200)
        else:
            cnt = 3
            while cnt > 0:
                basectrl.do_reboot()
                cnt -= 1
                time.sleep(0.01)
        self.ser.reset(115200)
        time.sleep(2)
        cnt = max_retry_count
        while cnt > 0:
            if adctrl.enter_outter_flash_mode(max_retry_count=1):
                break
            if reset_type == RESET_TYPE.DTR_RTS:
                basectrl.do_reset(reset_type=RESET_TYPE.DTR_RTS, baudrate=115200)
            else:
                cnt = 3
                while cnt > 0:
                    basectrl.do_reboot()
                    cnt -= 1
                    time.sleep(0.01)
            time.sleep(2)
            cnt -= 1
        if cnt <= 0:
            BKLog.w('enter outter flash mode fail.')
            return False
        BKLog.i('enter outter flash mode ok.')
        if not adctrl.enter_outter_flash_mode_success(max_retry_count=3):
            BKLog.w('check enter outter flash mode success fail.')
            return False
        BKLog.i('enter outter flash mode success.')
        time.sleep(2)
        BKLog.i('outter flash do link check.')
        if not basectrl.do_link_check(linkcheck_obj=LINKCHECK.BOOTROM):
            BKLog.w('outter flash do link check fail.')
            return False
        BKLog.i('outter flash do link check ok.')
        BKLog.i('outter flash query chip info...')
        if basectrl.get_chip_id_retry(max_retry_count=3) is None:
            BKLog.w('outter flash query chip info fail.')
            return False
        BKLog.i('outter flash chip info ok')
        return True

    def cal_and_write_aes128_data(self, key):
        """
        生成8 bytes随机数，+读出来的8 bytes device id，使用aes128加密后写入otp170
        :param key: AES128密钥
        :returns:
            写入成功返回True，失败返回False
        """
        rdm_content = generate_random_8bytes()
        security = BK7236_Security(serial_instance=self.ser)
        if not security._set_otp_write_enable():
            BKLog.e('Set OTP write enable fail.')
            return False
        time.sleep(0.1)
        (ret, val) = security._read_otp_by_regaddr(security.security_otp_apb_start_addr + 952, 16)
        if not ret:
            BKLog.e(f'Read OTP fail, address: 0x{security.security_otp_apb_start_addr + 952:x}.')
            return False
        hash_result = hashlib.sha256(val).digest()
        result_m = bytearray(8)
        for i in range(8):
            result_m[i] = hash_result[i] ^ hash_result[i + 16]
        BKLog.progress_log('BK', 'Authorizing', int(20))
        enc_data = aes128_ecb_encrypt(rdm_content + result_m, key)
        if not enc_data:
            BKLog.e('aes128 encrypt fail.')
            return False
        BKLog.progress_log('BK', 'Authorizing', int(40))
        (ret, msg) = security._write_chip_otp(security.security_otp_apb_start_addr + 360, rdm_content.hex())
        if not ret:
            BKLog.e(f'_write_chip_otp fail, address: 0x{security.security_otp_apb_start_addr + 360:x}.')
            BKLog.e(msg)
            return False
        BKLog.progress_log('BK', 'Authorizing', int(60))
        (ret, msg) = security._write_chip_otp(security.security_otp_apb_start_addr + 368, enc_data.hex())
        if not ret:
            BKLog.e(f'_write_chip_otp fail, address: 0x{security.security_otp_apb_start_addr + 368:x}.')
            BKLog.e(msg)
            return (False, msg)
        BKLog.progress_log('BK', 'Authorizing', int(80))
        (ret, msg) = security._write_chip_otp(security.security_otp_apb_start_addr + 992, key.hex())
        if not ret:
            BKLog.e(f'_write_chip_otp fail, address: 0x{security.security_otp_apb_start_addr + 992:x}.')
            BKLog.e(msg)
            return (False, msg)
        BKLog.progress_log('BK', 'Authorizing', int(100))
        return (True, msg)

    def verify_chip_product_id(self, binfile: BinInfo):
        return

    def check_bkaesrdm_status(self, retry_cnt=5):
        """
        check flash address(0x00000044) content, if content is "BKAESRDM", raise exception and stop download
        """
        flashctrl = FlashController(serial_instance=self.ser, flash_cfg=self._flash_cfg)
        while retry_cnt > 0:
            readout = flashctrl.read_flash_size(68, 8)
            if readout is not None:
                break
            retry_cnt -= 1
        if retry_cnt <= 0:
            raise Exception('read flash @0x00000044 fail.')
        if readout == b'BKAESRDM':
            raise Exception('check BKAESRDM words in flash, stop download/erase.')

    def write_chip_otp(self, otp_addr: int, content: str, reverse_content=False, bigendian=False):
        """
        write otp by address information
        """
        security = BK7236_Security(serial_instance=self.ser)
        return security._write_chip_otp(otp_addr, content, reverse_content, bigendian)

    def set_otp_permission_oplen(self, reg_addr, oplen, permission):
        """
        reg_addr: start OTP address
        oplen: reg count
        permission: wr/ro/na
        """
        security = BK7236_Security(serial_instance=self.ser)
        return security._set_otp_permission_oplen(reg_addr, oplen, permission)

    def write_efuse_by_bit(self, reg_addr, bit, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7236_Security(serial_instance=self.ser)
        return security._write_efuse_by_bit(reg_addr, bit, value)

    def write_efuse(self, reg_addr, value):
        """
        write one byte value, 8 bits
        'addr' is the pos of efuse
        """
        security = BK7236_Security(serial_instance=self.ser)
        return security._write_efuse(reg_addr, value)

    def read_chip_otp(self, otp_addr, oplen, reverse_content=False, bigendian=False):
        security = BK7236_Security(serial_instance=self.ser)
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
        security = BK7236_Security(serial_instance=self.ser)
        if not security._set_otp_write_enable():
            BKLog.e(f'Set OTP write enable fail.')
            return (False, None)
        time.sleep(0.1)
        (ret, val) = security._read_otp_by_regaddr(1259341760, 5)
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
        security = BK7236_Security(serial_instance=self.ser)
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
        security = BK7236_Security(serial_instance=self.ser)
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
                (ret, msg) = security._read_efuse(0, int(security.security_efuse_length / 8))
                if not ret:
                    return (False, msg)
                BKLog.w(f'read efuse ok: 0x{bytes.hex(bytes(msg))}')
        return (True, None)

    def pre_switch_baudrate(self):
        return False
