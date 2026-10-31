# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/chip_set/bk3436.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import time
from typing import List, Tuple
from .bk7231N import BK7231N
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...bk_log import BKLog
from ...common.common import safe_data
from ...common.common import FLASH_SIZE_DEF, LINKCHECK, FLASH_ERASE_CMD_EXT, FLASH_ERASE_CMD, safe_data, BinInfo, is_buf_all_0xff, BIT, BFD, crc32_ver2, bytes_reverse, bytes_reverse_per4bytes
from ...chip_controller import BaseController, FlashController, RegController
class BK3436(BK7231N):
    CHIP_ID = 13366
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL
    def __init__(self):
        super().__init__()
    def align_sector_address_for_erase(self, addr: int, start_or_end: bool, reset_type=None, link_type=None, read_baudrate=500000):
        flash_control = FlashController(self.ser, self._flash_cfg)
        erase_addr = int(addr / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
        baudrate_backup = self.ser.baudrate
        if not self.set_baudrate(read_baudrate):
            BKLog.w(f'Set baudrate: {read_baudrate} fail.')
            return False
        else:
            time.sleep(0.1)
            ret = flash_control.read_sector(erase_addr)
            if ret is None:
                return False
            res = self._erase_sector(erase_addr)
            if not res:
                return False
            if not self.set_baudrate(baudrate_backup):
                BKLog.e(f'Set baudrate: {baudrate_backup} fail.')
                return False
            else:
                if start_or_end:
                    ret = ret[:addr & 4095] + b'\xff' * (FLASH_SIZE_DEF.SIZE_4K - addr & 4095)
                else:
                    ret = b'\xff' * (addr & 4095) + ret[addr & 4095:]
                if not self.write_and_check_sector(ret, erase_addr):
                    BKLog.i('write sector @0x{:x} fail, retry'.format(erase_addr))
                    if not self.retry_write_sector(erase_addr, ret, reconnect_bus=False, reset_type=reset_type, link_type=link_type):
                        BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_addr))
                        return False
                return True
    def align_sector_address_for_write(self, addr: int, start_or_end: bool, content: bytes, reset_type=None, link_type=None, read_baudrate=500000):
        BKLog.i(f'input content length is: 0x{len(content):x}')
        BKLog.i(f'address is: 0x{addr:x}')
        flash_control = FlashController(self.ser, self._flash_cfg)
        erase_addr = int(addr / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
        baudrate_backup = self.ser.baudrate
        if not self.set_baudrate(read_baudrate):
            BKLog.e(f'Set baudrate: {read_baudrate} fail.')
            return False
        else:
            time.sleep(0.1)
            ret = flash_control.read_sector(erase_addr)
            if ret is None:
                return False
            res = self._erase_sector(erase_addr)
            if not res:
                return False
            if not self.set_baudrate(baudrate_backup):
                BKLog.e(f'Set baudrate: {baudrate_backup} fail.')
                return False
            else:
                if start_or_end:
                    ret = ret[:addr & 4095] + content[:FLASH_SIZE_DEF.SIZE_4K - addr & 4095]
                else:
                    ret = content[-(addr & 4095):] + ret[addr & 4095:]
                if not self.write_and_check_sector(ret, erase_addr):
                    BKLog.i('write sector @0x{:x} fail, retry'.format(erase_addr))
                    if not self.retry_write_sector(erase_addr, ret, reconnect_bus=False, reset_type=reset_type, link_type=link_type):
                        BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_addr))
                        return False
                return True
    def parse_flash_info(self):
        BKLog.i('ignore read flash mid.')
        self._flash_mid = 4344577
        self._flash_cfg.parse_flash_info(self._flash_mid)
        return True
    def un_protect_flash(self, protect: bool):
        BKLog.i('ignore unprotect/protect flash.')
        return True
    def _erase_sector_with_reconnect_bus(self, flash_addr: int, reconnect_bus: bool=True) -> Tuple[bool, bool]:
        flash_control = FlashController(self.ser, self._flash_cfg)
        ret, permission_denied = flash_control.erase_sector_new(flash_addr)
        if ret:
            return (True, False)
        else:
            if not permission_denied:
                return (False, False)
            else:
                if not reconnect_bus:
                    return (False, True)
                else:
                    if BaseController.link_check_obj == LINKCHECK.BOOTROM:
                        return (False, True)
                    else:
                        if not self._reboot_and_reconnect_bus(LINKCHECK.BOOTROM):
                            return (False, True)
                        else:
                            return flash_control.erase_sector_new(flash_addr)
    def _erase_sector(self, flash_addr: int) -> bool:
        ret, permission_denied = self._erase_sector_with_reconnect_bus(flash_addr, reconnect_bus=True)
        if not ret:
            BKLog.e(f'erase sector fail @0x{flash_addr:x}.')
            return False
        else:
            return True
    def align_all_bin_buf(self, binlist: List[BinInfo], for_erase=False, reconnect_retry=False, reset_type=None, link_type=None, retry_cnt=5):
        """\n        align start or end address for each bin\n        """
        flash_control = FlashController(self.ser, self._flash_cfg)
        for bin in binlist:
            BKLog.i(f'start address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x}')
            if bin.iStartAddress & 4095 or bin.iStartAddress + bin.iFileLength & 4095:
                if bin.iStartAddress & 4095:
                    BKLog.i(f'align start address: 0x{bin.iStartAddress:x}')
                    erase_addr = int(bin.iStartAddress / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                else:
                    BKLog.i(f'align end address: 0x{bin.iStartAddress + bin.iFileLength:x}')
                    erase_addr = int((bin.iStartAddress + bin.iFileLength) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                cnt = retry_cnt
                while cnt > 0:
                    ret = flash_control.read_sector(erase_addr)
                    if ret is not None:
                        break
                    cnt -= 1
                if ret is None:
                    BKLog.e(f'read_sector fail @0x{erase_addr:x}.')
                    return False
                else:
                    cnt = retry_cnt
                    while cnt > 0:
                        res = self._erase_sector(erase_addr)
                        if res:
                            break
                        cnt -= 1
                    if not res:
                        BKLog.e(f'erase_custom_size fail @0x{erase_addr:x}.')
                        return False
                    else:
                        if bin.iStartAddress & 4095:
                            if for_erase:
                                ret = ret[:bin.iStartAddress & 4095] + b'\xff' * (FLASH_SIZE_DEF.SIZE_4K - bin.iStartAddress & 4095)
                                bin.iFileLength = bin.iFileLength - (FLASH_SIZE_DEF.SIZE_4K - bin.iStartAddress & 4095)
                                bin.iStartAddress = int((bin.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                            else:
                                ret = ret[:bin.iStartAddress & 4095] + bin.pfile[:FLASH_SIZE_DEF.SIZE_4K - bin.iStartAddress & 4095]
                                bin.pfile = bin.pfile[FLASH_SIZE_DEF.SIZE_4K - bin.iStartAddress & 4095:]
                                bin.iStartAddress = int((bin.iStartAddress + FLASH_SIZE_DEF.SIZE_4K) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                                bin.iFileLength = len(bin.pfile)
                        else:
                            if for_erase:
                                ret = b'\xff' * (bin.iStartAddress + bin.iFileLength & 4095) + ret[bin.iStartAddress + bin.iFileLength & 4095:]
                                end_addr = int((bin.iStartAddress + bin.iFileLength) / FLASH_SIZE_DEF.SIZE_4K) * FLASH_SIZE_DEF.SIZE_4K
                                bin.iFileLength = end_addr - bin.iStartAddress
                            else:
                                ret = bin.pfile[-(bin.iStartAddress + bin.iFileLength & 4095):] + ret[bin.iStartAddress + bin.iFileLength & 4095:]
                                bin.pfile = bin.pfile[:len(bin.pfile) - (bin.iStartAddress + bin.iFileLength & 4095)]
                                bin.iFileLength = len(bin.pfile)
                        if not self.write_and_check_sector(ret, erase_addr):
                            BKLog.i('write sector @0x{:x} fail, retry'.format(erase_addr))
                            if not self.retry_write_sector(erase_addr, ret, reconnect_bus=reconnect_retry, reset_type=reset_type, link_type=link_type):
                                BKLog.e('Write and check sector @0x{:x} fail.'.format(erase_addr))
                                return False
                        BKLog.i(f'start address: 0x{bin.iStartAddress:x}, length: 0x{bin.iFileLength:x}')
        return True
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
                else:
                    BKLog.i('chip erase fail, retry')
            if not erase_res:
                raise Exception('chip erase fail.')
            else:
                BKLog.progress_log('BK', 'Erasing Flash', int(cprog + sprog))
        else:
            BKLog.i('erase start address @0x{:x}, '.format(start_addr) + 'end address @0x{:x}.'.format(end_addr))
            if start_addr is None or end_addr is None:
                BKLog.e('Error, address parameters is None.')
                return False
            else:
                if start_addr > end_addr:
                    BKLog.e('Error, start address is over end.')
                    return False
                else:
                    erase_size = end_addr - start_addr
                    i = 0
                    while i < erase_size:
                        current_progress = cprog + sprog * i / erase_size
                        BKLog.progress_log('BK', 'Erasing Flash', int(current_progress))
                        task_progress = 100 * i / erase_size
                        BKLog.progress_log('BK', 'Erasing Flash', int(task_progress), task_progress=True)
                        cnt = retry
                        ret = False
                        while cnt > 0 and (not ret):
                            BKLog.i('Erase sector @0x{:x} .'.format(start_addr + i))
                            ret = self._erase_custom_size(start_addr + i, FLASH_SIZE_DEF.SIZE_4K)
                            cnt -= 1
                        if not ret:
                            BKLog.e('Erase sector @0x{:x} fail.'.format(start_addr + i))
                            return False
                        else:
                            i += FLASH_SIZE_DEF.SIZE_4K
                    BKLog.i('end erase.')
        return True