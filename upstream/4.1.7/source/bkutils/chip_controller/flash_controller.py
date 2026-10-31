# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/flash_controller.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import time
from ..common.bk_out_config import BkReadFlashConfig
from ..bk_log import BKLog
from .serial_helper import SerialHelper
from ..flash_adapter.flash_config import FlashConfig
from ..protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ..common.common import FLASH_ERASE_CMD, FLASH_ERASE_CMD_EXT, FLASH_SIZE_DEF, crc32_ver2
from typing import List, Tuple
class FlashController(object):
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL
    def __init__(self, serial_instance: SerialHelper, flash_cfg: FlashConfig) -> None:
        self.serial_instance = serial_instance
        self._flash_cfg = flash_cfg
    def check_crc_ver2(self, buf: bytes, flash_addr: int, buf_len: int, timeout=1.8, recnt=5):
        crc_protocol = self.BOOTROM_PROTOCOL.CheckCrcProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            crc_protocol = self.BOOTROM_PROTOCOL.CheckCrcExtProtocol()
        crc_me = crc32_ver2(4294967295, buf)
        BKLog.d('buf crc is: 0x{:x}'.format(crc_me))
        for _ in range(recnt):
            crc_res, crc_content = self.serial_instance.write_cmd_and_wait_response(crc_protocol.cmd(flash_addr, flash_addr + buf_len - 1), crc_protocol.expect_length, timeout)
            if crc_res and crc_protocol.response_check(crc_content):
                    break
        if not crc_res:
            return False
        else:
            crc_read = crc_protocol.get_crc_value(response_content=crc_content)
            BKLog.d('read crc is: 0x{:x}'.format(crc_read))
            if crc_me != crc_read:
                return False
            else:
                return True
    def _write_flash_reg_enable(self, retry=5):
        wfe = self.BOOTROM_PROTOCOL.FlashWriteEnableProtocol()
        tmp_res = False
        for _ in range(retry):
            res, content = self.serial_instance.write_cmd_and_wait_response(wfe.cmd(), wfe.expect_length, 0.8)
            if res and wfe.response_check(content):
                    tmp_res = True
                    break
            BKLog.i('write flash register enable fail, retry')
            continue
        if tmp_res is False:
            raise Exception('write flash register enable fail')
    def _read_flash_status_reg_val(self, retry=5):
        frsp = self.BOOTROM_PROTOCOL.FlashReadSRProtocol()
        read_reg_code = self._flash_cfg.flash_status_reg_read_code
        sr_val = []
        for _ in range(len(read_reg_code)):
            tmp_reg = read_reg_code[_]
            tmp_val = None
            for _ in range(retry):
                res, content = self.serial_instance.write_cmd_and_wait_response(frsp.cmd(tmp_reg), frsp.expect_length, 0.8)
                if res and frsp.response_check(content, tmp_reg):
                        tmp_val = frsp.get_status_regist_val(content)
                        break
                BKLog.i('read flash status register fail, retry')
                continue
            if tmp_val is None:
                raise Exception('read flash status register fail')
            else:
                sr_val.append(tmp_val)
        return sr_val
    def _write_flash_status_reg_val(self, write_val, retry=5):
        fwsp = self.BOOTROM_PROTOCOL.FlashWriteSRProtocol()
        write_reg_code = self._flash_cfg.flash_status_reg_write_code
        if len(write_reg_code) == 1:
            tmp_res = False
            for _ in range(retry):
                res, content = self.serial_instance.write_cmd_and_wait_response(fwsp.cmd(write_reg_code[0], write_val), fwsp.expect_length(len(write_val)), 0.8)
                if res and fwsp.response_check(content, write_reg_code[0]):
                        tmp_res = True
                        break
                BKLog.i('write flash status register fail, retry')
                time.sleep(0.01)
                continue
            if tmp_res is False:
                raise Exception('write flash status register fail')
        else:
            for idx in range(len(write_reg_code)):
                tmp_res = False
                for _ in range(retry):
                    res, content = self.serial_instance.write_cmd_and_wait_response(fwsp.cmd(write_reg_code[idx], [write_val[idx]]), fwsp.expect_length(1), 0.8)
                    if res and fwsp.response_check(content, write_reg_code[idx]):
                            tmp_res = True
                            break
                    BKLog.i('write flash status register fail, retry')
                    time.sleep(0.01)
                    continue
                if tmp_res is False:
                    raise Exception('write flash status register fail')
                else:
                    time.sleep(0.01)
    def unprotect_flash(self, retry_cnt=5):
        unprotect_reg_val, mask = self._flash_cfg.unprotect_register_value
        reg_val = self._read_flash_status_reg_val()
        if self._flash_cfg.compare_register_value(reg_val, unprotect_reg_val, mask):
            return True
        else:
            write_val = unprotect_reg_val
            for _ in range(len(write_val)):
                write_val[_] = write_val[_] | reg_val[_] & (mask[_] ^ 255)
            cnt = retry_cnt
            while cnt > 0:
                self._write_flash_status_reg_val(write_val)
                reg_val = self._read_flash_status_reg_val()
                if self._flash_cfg.compare_register_value(reg_val, unprotect_reg_val, mask):
                    return True
                else:
                    cnt -= 1
            return False
    def protect_flash(self, retry_cnt=5):
        protect_reg_val, mask = self._flash_cfg.protect_register_value
        reg_val = self._read_flash_status_reg_val()
        if self._flash_cfg.compare_register_value(reg_val, protect_reg_val, mask):
            return True
        else:
            write_val = protect_reg_val
            for _ in range(len(write_val)):
                write_val[_] = write_val[_] | reg_val[_] & (mask[_] ^ 255)
            cnt = retry_cnt
            while cnt > 0:
                self._write_flash_status_reg_val(write_val)
                reg_val = self._read_flash_status_reg_val()
                if self._flash_cfg.compare_register_value(reg_val, protect_reg_val, mask):
                    return True
                else:
                    cnt -= 1
            return False
    def write_sector(self, flash_addr, buf):
        write_flash_protocol = self.BOOTROM_PROTOCOL.FlashWrite4kProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            write_flash_protocol = self.BOOTROM_PROTOCOL.FlashWrite4kExtProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(write_flash_protocol.cmd(flash_addr, buf), write_flash_protocol.expect_length, 0.8)
        if tmp_res and write_flash_protocol.response_check(content, flash_addr=flash_addr):
                return True
        return False
    all_retry_cnt = 0
    def read_sector(self, flash_addr):
        read_flash_protocol = self.BOOTROM_PROTOCOL.FlashRead4kProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            read_flash_protocol = self.BOOTROM_PROTOCOL.FlashRead4kExtProtocol()
        retry_cnt = BkReadFlashConfig.retry_count
        timeout_ms = BkReadFlashConfig.fixed_timeout_ms / 1000
        if timeout_ms <= 0:
            timeout_ms = BkReadFlashConfig.timeout_factor * read_flash_protocol.expect_length * 10 / self.serial_instance.baudrate
        delay_after_fail = BkReadFlashConfig.delay_after_fail_ms / 1000
        for attempt in range(retry_cnt):
            tmp_res, content = self.serial_instance.write_cmd_and_wait_response(read_flash_protocol.cmd(flash_addr), read_flash_protocol.expect_length, timeout_ms)
            if tmp_res and read_flash_protocol.response_check(content, flash_addr=flash_addr):
                return read_flash_protocol.get_read_content(content)
            else:
                if attempt < retry_cnt - 1:
                    FlashController.all_retry_cnt += 1
                    BKLog.w('Read sector failed at addr 0x{:x}, attempt {}/{}, received length: {}, retrying...'.format(flash_addr, attempt + 1, retry_cnt, len(content) if content else 0))
        BKLog.e('Read sector failed at addr 0x{:x} after {} attempts, received length: {}'.format(flash_addr, retry_cnt, len(content) if content else 0))
    def erase_sector(self, flash_addr):
        erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashErase4kProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashErase4kExtProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(erase_flash_protocol.cmd(flash_addr), erase_flash_protocol.expect_length, 1.0)
        if tmp_res and erase_flash_protocol.response_check(content, flash_addr=flash_addr):
                return True
        return False
    def erase_sector_new(self, flash_addr: int) -> Tuple[bool, bool]:
        erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashErase4kProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashErase4kExtProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(erase_flash_protocol.cmd(flash_addr), erase_flash_protocol.expect_length, 1.0)
        if tmp_res and erase_flash_protocol.response_check(content, flash_addr=flash_addr):
                return (True, False)
        return (False, erase_flash_protocol.check_response_permission_denied(content))
    def erase_all(self) -> Tuple[bool, bool]:
        erase_res = False
        erase_all_protocol = self.BOOTROM_PROTOCOL.FlashEraseAllProtocol()
        if self._flash_cfg.flash_size >= 268435456:
            erase_all_protocol = self.BOOTROM_PROTOCOL.FlashEraseAllExtProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(erase_all_protocol.cmd(20), erase_all_protocol.expect_length, timeout_sec=20)
        if tmp_res and erase_all_protocol.response_check(content):
                return (True, False)
        return (False, erase_all_protocol.check_response_permission_denied(content))
    def erase_custom_size(self, flash_addr, cmd):
        """\n        cmd:\n        normal,4k/32k/64k->0x20/0x52/0xd8\n        ext,4k/32k/64k->0x21/0x5c/0xdc\n        """
        erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashCustomEraseProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(erase_flash_protocol.cmd(flash_addr, cmd), erase_flash_protocol.expect_length, 1.0)
        if tmp_res and erase_flash_protocol.response_check(content, cmd, flash_addr=flash_addr):
                return True
        return False
    def erase_custom_size_new(self, flash_addr: int, erase_size: int) -> Tuple[bool, bool]:
        """\n        erase_size: 4k/32k/64k\n        return: True,False if permission denied\n                False,True if permission denied\n                False,False if other error\n        """
        if self._flash_cfg.flash_size >= 268435456:
            if erase_size == FLASH_SIZE_DEF.SIZE_4K:
                cmd = FLASH_ERASE_CMD_EXT.SIZE_4K
            else:
                if erase_size == FLASH_SIZE_DEF.SIZE_32K:
                    cmd = FLASH_ERASE_CMD_EXT.SIZE_32K
                else:
                    if erase_size == FLASH_SIZE_DEF.SIZE_64K:
                        cmd = FLASH_ERASE_CMD_EXT.SIZE_64K
                    else:
                        raise Exception(f'not support erase size: {erase_size}')
        else:
            if erase_size == FLASH_SIZE_DEF.SIZE_4K:
                cmd = FLASH_ERASE_CMD.SIZE_4K
            else:
                if erase_size == FLASH_SIZE_DEF.SIZE_32K:
                    cmd = FLASH_ERASE_CMD.SIZE_32K
                else:
                    if erase_size == FLASH_SIZE_DEF.SIZE_64K:
                        cmd = FLASH_ERASE_CMD.SIZE_64K
                    else:
                        raise Exception(f'not support erase size: {erase_size}')
        erase_flash_protocol = self.BOOTROM_PROTOCOL.FlashCustomEraseProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(erase_flash_protocol.cmd(flash_addr, cmd), erase_flash_protocol.expect_length, 1.0)
        if tmp_res and erase_flash_protocol.response_check(content, cmd, flash_addr=flash_addr):
                return (True, False)
        return (False, erase_flash_protocol.check_response_permission_denied(content))
    def read_flash_security(self, addr: int, oplen: int):
        fs_protocol = self.BOOTROM_PROTOCOL.FlashSecurityReadProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fs_protocol.cmd(addr, oplen), fs_protocol.expect_length(oplen), 1.0)
        if tmp_res and fs_protocol.response_check(content):
            return fs_protocol.get_read_val(content, oplen)
        else:
            return None
    def write_flash_security(self, addr: int, buf):
        fs_protocol = self.BOOTROM_PROTOCOL.FlashSecurityWriteProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fs_protocol.cmd(addr, buf), fs_protocol.expect_length(len(buf)), 1.0)
        if tmp_res and fs_protocol.response_check(content):
                return True
        return False
    def erase_flash_security(self, addr: int):
        """\n        erase 4k size\n        """
        fs_protocol = self.BOOTROM_PROTOCOL.FlashSecurityEraseProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fs_protocol.cmd(addr), fs_protocol.expect_length, 1.0)
        if tmp_res and fs_protocol.response_check(content):
                return True
        return False
    def erase_flash_security_new(self, addr: int) -> Tuple[bool, bool]:
        fs_protocol = self.BOOTROM_PROTOCOL.FlashSecurityEraseProtocol()
        tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fs_protocol.cmd(addr), fs_protocol.expect_length, 1.0)
        if tmp_res and fs_protocol.response_check(content, addr):
                return (True, False)
        return (False, fs_protocol.check_response_permission_denied(content))
    def write_flash_size(self, addr: int, buf: bytes):
        """\n        write flash size<=256 \n        """
        if len(buf) > 256:
            BKLog.e('error, buf size cannt be over 256')
            return False
        else:
            fs_protocol = self.BOOTROM_PROTOCOL.FlashCustomWriteProtocol()
            if self._flash_cfg.flash_size >= 268435456:
                fs_protocol = self.BOOTROM_PROTOCOL.FlashCustomWriteExtProtocol()
            tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fs_protocol.cmd(addr, buf), fs_protocol.expect_length, 1.0)
            if tmp_res and fs_protocol.response_check(content, addr):
                    return True
            return False
    def read_flash_size(self, addr: int, oplen: int):
        """\n        write flash size<=256 \n        """
        if oplen > 256:
            BKLog.e('error, read size cannt be over 256')
            return
        else:
            fcrp_protocol = self.BOOTROM_PROTOCOL.FlashCustomReadProtocol()
            if self._flash_cfg.flash_size >= 268435456:
                fcrp_protocol = self.BOOTROM_PROTOCOL.FlashCustomReadExtProtocol()
            tmp_res, content = self.serial_instance.write_cmd_and_wait_response(fcrp_protocol.cmd(addr=addr, oplen=oplen), fcrp_protocol.expect_length(oplen=oplen), 1.0)
            if tmp_res and fcrp_protocol.response_check(content, addr):
                return fcrp_protocol.get_read_content(content)
            else:
                return None