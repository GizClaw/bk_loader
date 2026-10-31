from abc import ABC, abstractmethod
from functools import wraps
from typing import List
from ..serial_helper import SerialHelper
from ...bk_log import BKLog
from ...flash_adapter.flash_config import FlashConfig
from ...protocol.bootrom import v2_0 as V2_0_BOOTROM_PROTOCOL
from ...common.common import safe_data, BinInfo
from ..flash_controller import FlashController

class BaseChip(ABC):
    CHIP_ID = None
    BOOTROM_PROTOCOL = V2_0_BOOTROM_PROTOCOL

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        set_baudrate = cls.__dict__.get('set_baudrate')
        if set_baudrate is None or getattr(set_baudrate, '_reports_baudrate', False):
            return

        @wraps(set_baudrate)
        def wrapped_set_baudrate(self, *args, **kwargs):
            baudrate = kwargs.get('baudrate')
            if baudrate is None and args:
                baudrate = args[0]
            if baudrate is None or self.ser is None or (not hasattr(self.ser, 'report_baudrate_as')):
                return set_baudrate(self, *args, **kwargs)
            with self.ser.report_baudrate_as(baudrate):
                return set_baudrate(self, *args, **kwargs)
        wrapped_set_baudrate._reports_baudrate = True
        cls.set_baudrate = wrapped_set_baudrate

    def __init__(self):
        self.ser = None
        self._flash_mid = None
        self._flash_cfg = FlashConfig()

    def update_serial_instance(self, serial_instance: SerialHelper):
        self.ser = serial_instance

    @abstractmethod
    def parse_flash_info(self):
        pass

    @abstractmethod
    def write_tool_version(self, ver: str):
        pass

    @abstractmethod
    def pre_check_image_file(self, bin_list: list):
        pass

    @abstractmethod
    def pre_check_img_file_crc(self, bin_list: list):
        pass

    @abstractmethod
    def pre_set_efuse_nocrc(self):
        pass

    @abstractmethod
    def un_protect_flash(self, protect: bool):
        pass

    @abstractmethod
    def set_baudrate(self, baudrate, delay_ms: 20):
        pass

    @abstractmethod
    def read_and_check_sector(self, addr: int, recnt=5):
        pass

    @abstractmethod
    def write_and_check_sector(self, buf_sec: bytes, addr: int):
        pass

    @abstractmethod
    def write_flash_info(self, flash_addr, buf):
        pass

    @abstractmethod
    def erase_flash(self, full_erase: bool, start_addr=None, end_addr=None, retry=5, cprog=0, sprog=100):
        pass

    @abstractmethod
    def dump_flash(self, start_addr, oplen, file, recnt=5, console=False, cprog=0, sprog=100):
        pass

    @abstractmethod
    def download_flash(self, wbuf: bytes, start_addr: int, retry=5, reconnect_retry=False, reset_type=None, link_type=None, cprog=0, sprog=100):
        pass

    @abstractmethod
    def download_flash_cbus(self, wbuf: bytes, partition_start: int, partition_size: int, start_addr: int, retry=5, reset_type=None, link_type=None, cprog=0, sprog=100):
        pass

    def download_flash_cbus_dbg(self, wbuf: bytes, start_addr: int, retry=5, reset_type=None, link_type=None, cprog=0, sprog=100):
        pass

    @abstractmethod
    def align_all_bin_buf(self, binlist: List[BinInfo], for_erase=False, reconnect_retry=False, reset_type=None, link_type=None, retry_cnt=5):
        pass

    @abstractmethod
    def reboot_and_enter_write_outter_flash_mode(self, reset_type=0, max_retry_count=10):
        pass

    @abstractmethod
    def cal_and_write_aes128_data(self, key):
        pass

    @abstractmethod
    def verify_chip_product_id(self, binfile: BinInfo):
        pass

    @abstractmethod
    def write_efuse_by_bit(self, reg_addr, bit, value):
        pass

    @abstractmethod
    def write_efuse(self, reg_addr, value):
        pass

    @abstractmethod
    def set_otp_permission_oplen(self, reg_addr, oplen, permission):
        pass

    @abstractmethod
    def write_chip_otp(self, otp_addr: int, content: str, reverse_content=False, bigendian=False):
        pass

    @abstractmethod
    def read_chip_otp(self, otp_addr, oplen, reverse_content=False, bigendian=False):
        pass

    def read_otp_efuse_auto(self, addr, oplen, reverse_content=False, bigendian=False):
        return self.read_chip_otp(addr, oplen, reverse_content, bigendian)

    @abstractmethod
    def read_chip_uid(self):
        pass

    @abstractmethod
    def read_efuse(self, addr, oplen):
        pass

    @abstractmethod
    def write_safe_json(self, safeinfo: safe_data):
        pass

    @abstractmethod
    def read_as_safe_json(self, safeinfo: safe_data):
        pass

    @abstractmethod
    def read_bl2_version(self):
        pass

    @abstractmethod
    def check_aes_key_enable(self):
        pass

    @abstractmethod
    def check_aes_key_otp_data(self):
        pass

    @abstractmethod
    def check_aes_key_otp_permission(self):
        pass

    @abstractmethod
    def set_baudrate_correct(self):
        pass

    @abstractmethod
    def check_bkaesrdm_status(self, retry_cnt=5):
        pass

    @abstractmethod
    def write_chip_flash_security(self, addr: int, buf):
        pass

    @abstractmethod
    def read_chip_flash_security(self, addr: int, oplen: int, file, console: bool=False):
        pass

    @abstractmethod
    def erase_chip_flash_security(self, addr: int, oplen):
        pass

    @abstractmethod
    def pre_switch_baudrate(self):
        pass
