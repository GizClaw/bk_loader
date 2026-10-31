# bk_loader
#
# Copyright (c) BekenCorp. All rights reserved.
#

global crc32_table
from math import e
from pickletools import stringnl_noescape_pair
import struct
import sys
import platform
import os
import glob
import serial
from enum import Enum
from dataclasses import asdict, dataclass, field
from typing import List
from bkutils.common.bk_out_config import BinParser, BinParserConfig, CrcCheckInfo, CustomerVersionConfig
from bkutils.common.initiator import INITIATOR
from ..bk_log.log_utils import *
import json

class PM_CPU_FREQ_LIST:
    PM_CPU_FREQ_26M = 1
    PM_CPU_FREQ_40M = 2
    PM_CPU_FREQ_80M = 3
    PM_CPU_FREQ_120M = 4
    PM_CPU_FREQ_240M = 5
    PM_CPU_FREQ_320M = 6
    PM_CPU_FREQ_480M = 7
    PM_CPU_FREQ_DEFAULT = 8

class PM_FLASH_FREQ_LIST:
    PM_FLASH_FREQ_26M = 1
    PM_FLASH_FREQ_40M = 2
    PM_FLASH_FREQ_80M = 3

class CPU_CLOCK_LIST:
    CLOCK_XTAL_CPU_26M = 1
    CLOCK_PLL_CPU_32M = 2
    CLOCK_PLL_CPU_40M = 3
    CLOCK_PLL_CPU_64M = 4
    CLOCK_PLL_CPU_80M = 5
    CLOCK_PLL_CPU_96M = 6
    CLOCK_PLL_CPU_120M = 7

class FLASH_CLOCK_LIST:
    CLOCK_XTAL_FLASH_26M = 1
    CLOCK_PLL_FLASH_32M = 2
    CLOCK_PLL_FLASH_40M = 3
    CLOCK_PLL_FLASH_64M = 4
    CLOCK_PLL_FLASH_80M = 5

class PROGRAMING_MODE_LIST:
    PROGRAMING_INVALID = 0
    PROGRAMING_DBUS = 1
    PROGRAMING_CBUS = 2
    PROGRAMING_ALL = 3

class FLASH_SIZE_DEF:
    SIZE_PAGE = 256
    SIZE_4K = 4096
    SIZE_32K = 32768
    SIZE_64K = 65536

class FLASH_ERASE_CMD:
    SIZE_4K = 32
    SIZE_32K = 82
    SIZE_64K = 216

class FLASH_ERASE_CMD_EXT:
    SIZE_4K = 33
    SIZE_32K = 92
    SIZE_64K = 220

class LINKCHECK(Enum):
    BOOTROM = (0,)
    BL2 = (1,)
    BOOTROM_PRE = (2,)
    BOOTROM_EXT = (3,)
    MIXED = (4,)
    OTHER = 5

class BIN_TYPE(Enum):
    TYPE_NORMAL = (0,)
    TYPE_OTA = (1,)
    TYPE_BL1_ALL_BIN = (2,)
    TYPE_BL2_APP_BIN = (3,)
    TYPE_SECURE_FIX = (4,)
    TYPE_OUTTER_FLASH = (5,)
    TYPE_NORMAL_FIXED = (6,)
    TYPE_BL2_OTA = (7,)
    TYPE_SAM_UN = (8,)
    TYPE_SAM_EN = (9,)
    TYPE_CUSTOM_UNSECURE = (10,)
    TYPE_CUSTOM_SECURE = (11,)
    TYPE_BL1_SECUR_MODE = (12,)
    TYPE_BL1_SECURE_FIXED = (13,)
    TYPE_BL1_SECURE_EXTENSION = (14,)

class RESET_TYPE(Enum):
    DTR_RTS = (0,)
    CMD_ASCII = (1,)
    CMD_HEX = (2,)
    MULTI = 3

class TASK_TYPE(Enum):
    DOWNLOAD = (0,)
    ERASE = (1,)
    READ = (2,)
    TOOLS = 3

@dataclass
class user_operate:
    name: str = ''
    mode: str = ''
    permission: str = ''
    start_addr: str = ''
    end_addr: str = ''
    byte_len: str = ''
    data: str = ''
    data_type: str = ''
    encrypt: str = ''
    status: str = ''
    big_endian: bool = False
    reverse: bool = False
    specified_flag: int = 0

    def specify_reverse(self):
        self.specified_flag |= 1

    def is_reverse_specified(self):
        return self.specified_flag & 1 == 1

    def specify_big_endian(self):
        self.specified_flag |= 2

    def is_big_endian_specified(self):
        return self.specified_flag & 2 == 2

@dataclass
class efuse_info:
    name: str = ''
    mode: str = ''
    byte_addr: str = ''
    end_addr: str = ''
    length: str = ''
    data: str = ''
    status: str = ''

@dataclass
class safe_data:
    write_safe_config: bool = False
    read_safe_config: bool = False
    user_operate_enable: bool = False
    efuse_enable: bool = False
    security_ctrl_enable: bool = False
    security_data_enable: bool = False
    user_operate_list: List[user_operate] = field(default_factory=list)
    efuse_info_list: List[efuse_info] = field(default_factory=list)
    security_data_list: List[user_operate] = field(default_factory=list)
    security_ctrl: List[str] = field(default_factory=list)

@dataclass
class BinInfo:
    bCheck: bool = True
    bDataPort: bool = True
    iLinkCheckType: int = 0
    sFilePath: str = ''
    iStartAddress: int = 0
    iFileCRC: int = 0
    iFileLength: int = 0
    iPartition_start: int = 0
    iPartition_size: int = 0
    bOtpData: bool = False
    pfile: bytes = b''

@dataclass
class ExpandData:
    name: str = ''
    start_addr: int = 1
    length: int = 1
    value: bytes = b''

class ExpandDataType(Enum):
    HEX_LITTER = 0
    HEX_BIG = 1
    STRING_LITTER = 2
    STRING_BIG = 3

def format_expand_data_value_for_log(expand_data: ExpandData) -> str:
    """格式化拓展数据值用于日志：STRING 类型打印字符串，HEX/MAC 类型打印十六进制。"""
    if not expand_data.value:
        return ''
    elif expand_data.name and 'STRING' in expand_data.name.upper():
        return expand_data.value.decode('utf-8', errors='replace')
    else:
        return '0x' + expand_data.value.hex()

def describe_expand_data_out_of_flash_range(expand_data: ExpandData, flash_size_bits: int):
    """拓展数据地址越界诊断。地址合法返回 None，否则返回描述字符串。

    flash_size 单位为 bit，需换算成 byte 后再与地址比较。
    """
    flash_bytes = int(flash_size_bits / 8)
    if flash_bytes <= 0:
        return
    else:
        start = expand_data.start_addr
        end = start + expand_data.length
        if start >= 0 and end <= flash_bytes:
            return
        return f"expand data '{expand_data.name}' address out of flash range: 0x{start:x}+0x{expand_data.length:x} (end 0x{end:x}) exceeds flash size 0x{flash_bytes:x}, please check the address."

@dataclass
class SingleTypeBinInfo:
    binType: int = BIN_TYPE.TYPE_NORMAL
    binList: List[BinInfo] = field(default_factory=list)

@dataclass
class DownloadInfo:
    work_baudrate: int = 2000000
    vecbinInfo: List[BinInfo] = field(default_factory=list)
    mixedBinInfo: List[SingleTypeBinInfo] = field(default_factory=list)
    safeinfo: safe_data = field(default_factory=safe_data)
    aes_key: str = ''
    otp_info: str = ''
    otp_pm: str = ''
    efuse_info: str = ''
    bDownloadBin: bool = False
    bAllFlash: bool = False
    bSecureboot: bool = False
    bDownloadDeviceID: bool = False
    bDownloadDeviceName: bool = False
    bEnableBigEndian: bool = False
    device_id: bytes = field(default_factory=lambda : bytes([0] * 6))
    device_id_Addr: int = 0
    device_id_length: int = 0
    device_name: bytes = field(default_factory=lambda : bytes(32))
    device_name_Addr: int = 0
    device_name_length: int = 0
    reverse_content: bool = False
    otp_bigendian: bool = False
    pre_erase: int = 1
    check_words: str = ''
    custom_data: str = ''
    expand_data_list: List[ExpandData] = field(default_factory=list)
    flash_otp: str = ''

@dataclass
class ReadInfo:
    work_baudrate: int = 500000
    vecbinInfo: List[BinInfo] = field(default_factory=list)
    bAllFlash: bool = False
    read_uid: bool = False
    read_efuse: bool = False
    read_otp: str = ''
    bConsole: bool = False
    reverse_content: bool = False
    read_path: str = ''
    read_otp_efuse_uid: str = ''
    read_otp_efuse_auto: str = ''
    safeinfo: safe_data = field(default_factory=safe_data)
    flash_otp: str = ''

@dataclass
class EraseInfo:
    work_baudrate: int = 1000000
    vecbinInfo: List[BinInfo] = field(default_factory=list)
    bAllFlash: bool = False
    flash_otp: str = ''

@dataclass
class AuthorizeInfo:
    work_baudrate: int = 1000000
    aes_key: str = ''

@dataclass
class SecureDebugInfo:
    work_baudrate: int = 1000000
    key_path: str = ''

@dataclass
class ExtraData:
    just_read_file_info: bool = False
    bin_parser: BinParser = None

def BFD(v, bs, bl):
    return (v & (1 << bl) - 1) << bs

def BIT(n):
    return 1 << n

def get_os_type():
    os_type = platform.system()
    if os_type == 'Windows':
        return 'Windows'
    elif os_type == 'Linux':
        if is_raspberry_pi():
            return 'Raspberry Pi'
        return 'Linux'
    elif os_type == 'Darwin':
        return 'MacOS'
    else:
        return 'Unknown'

def is_raspberry_pi():
    try:
        with open('/proc/cpuinfo', 'r') as f:
            cpuinfo = f.read().lower()
            return 'raspberry pi' in cpuinfo
    except FileNotFoundError:
        return False
crc32_table = [0] * 256

def make_crc32_table():
    global crc32_table
    if crc32_table[255] != 0:
        return
    for i in range(256):
        c = i
        for bit in range(8):
            if c & 1:
                c = c >> 1 ^ 3988292384
            else:
                c = c >> 1
        crc32_table[i] = c

def crc32_ver2(crc, buf):
    make_crc32_table()
    for byte in buf:
        crc = crc >> 8 ^ crc32_table[(crc ^ byte) & 255]
    return crc

def crc32bytes(data: bytearray):
    """
    data length must be 0x20
    """
    crc = 65535
    for d in data:
        for idx in range(8):
            bit = 7 - idx
            dbit = d >> bit & 1 & 65535
            b15 = crc >> 15 & 1 & 65535
            crc <<= 1
            crc = crc & 65535
            crc |= dbit
            crc = crc & 65535
            crc ^= dbit << 15 | dbit << 2
            crc = crc & 65535
            crc ^= b15 << 15 | b15 << 2 | b15 << 0
            crc = crc & 65535
    crcdata = bytearray()
    crcdata = data + bytes([crc >> 8 & 255])
    crcdata = crcdata + bytes([crc & 255])
    return crcdata

def load_normal_bin(srcbuf: bytes) -> BinInfo:
    bin_info = BinInfo()
    bin_info.bCheck = True
    bin_info.pfile = srcbuf
    buf_len = len(srcbuf)
    padding_len = buf_len % 256
    if padding_len:
        bin_info.pfile += b'\xff' * (256 - padding_len)
        buf_len += 256 - padding_len
    bin_info.iFileLength = buf_len
    bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
    bin_info.iLinkCheckType = LINKCHECK.BOOTROM
    return bin_info

def load_ota_bin(srcbuf: bytes):
    bin_list = []
    bin_num = srcbuf[18] << 8 + srcbuf[19]
    for idx in range(0, bin_num):
        bin_info = BinInfo()
        bin_info.bCheck = True
        pos = 32 + 32 * idx
        file_len = srcbuf[pos] << 24 + srcbuf[pos + 1] << 16 + srcbuf[pos + 2] << 8 + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 4
        image_offset = srcbuf[pos] << 24 + srcbuf[pos + 1] << 16 + srcbuf[pos + 2] << 8 + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 8
        bin_info.iStartAddress = srcbuf[pos] << 24 + srcbuf[pos + 1] << 16 + srcbuf[pos + 2] << 8 + srcbuf[pos + 3]
        bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
        padding_len = file_len % 256
        if padding_len:
            bin_info.pfile += b'\xff' * (256 - padding_len)
            file_len += 256 - padding_len
        bin_info.iFileLength = file_len
        bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
        bin_info.iLinkCheckType = LINKCHECK.BOOTROM
        bin_list.append(bin_info)
    return bin_list if len(bin_list) > 0 else None

def load_bl2_ota_bin(srcbuf: bytes):
    head_len = 32
    big_endian = False
    bin_list = []
    start_section_index = 3
    sections = [('primary_manifest', start_section_index * head_len), ('secondary_manifest', (start_section_index + 1) * head_len), ('bta', (start_section_index + 2) * head_len), ('btb', (start_section_index + 3) * head_len)]
    for (_, offset) in sections:
        bin_info = combin_bl2_ota_bin(srcbuf, offset, big_endian)
        bin_list.append(bin_info)
    return bin_list

def combin_bl2_ota_bin(srcbuf: bytes, ptr: int, big_endian: bool) -> BinInfo:
    order_format = '>I' if big_endian else '<I'
    bin_info = BinInfo()
    bin_info.iLinkCheckType = LINKCHECK.BL2
    bin_info.iPartition_start = struct.unpack_from(order_format, srcbuf, ptr)[0]
    ptr += 4
    bin_info.iPartition_size = struct.unpack_from(order_format, srcbuf, ptr)[0]
    ptr += 4
    bin_info.iStartAddress = struct.unpack_from(order_format, srcbuf, ptr)[0]
    ptr += 4
    offset_addr = struct.unpack_from(order_format, srcbuf, ptr)[0]
    ptr += 4
    file_len = struct.unpack_from(order_format, srcbuf, ptr)[0]
    bin_info.pfile = srcbuf[offset_addr:offset_addr + file_len]
    padding_len = file_len % 256
    if padding_len:
        bin_info.pfile += b'\xff' * (256 - padding_len)
        file_len += 256 - padding_len
    bin_info.iFileLength = file_len
    bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
    return bin_info

def load_bl1_all_app_bin(srcbuf: bytes):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_list = []
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    for idx in range(0, bin_num):
        bin_info = BinInfo()
        bin_info.bCheck = True
        pos = 32 + 32 * idx
        bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 4
        bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 8
        bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 12
        image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 16
        file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 28
        port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
        if port_type > 0:
            bin_info.bDataPort = False
        else:
            bin_info.bDataPort = True
        bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
        padding_len = file_len % 256
        if padding_len:
            bin_info.pfile += b'\xff' * (256 - padding_len)
            file_len += 256 - padding_len
        bin_info.iFileLength = file_len
        bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
        bin_info.iLinkCheckType = LINKCHECK.BOOTROM
        bin_list.append(bin_info)
    return bin_list if len(bin_list) > 0 else None

def load_bl2_app_bin(srcbuf: bytes):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_list = []
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    for idx in range(0, bin_num):
        bin_info = BinInfo()
        bin_info.bCheck = True
        pos = 32 + 32 * idx
        bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 4
        bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 8
        bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 12
        image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 16
        file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 28
        port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
        if port_type > 0:
            bin_info.bDataPort = False
        else:
            bin_info.bDataPort = True
        bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
        padding_len = file_len % 256
        if padding_len:
            bin_info.pfile += b'\xff' * (256 - padding_len)
            file_len += 256 - padding_len
        bin_info.iFileLength = file_len
        bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
        bin_info.iLinkCheckType = LINKCHECK.BL2
        bin_list.append(bin_info)
    return bin_list if len(bin_list) > 0 else None

def load_secure_boot_bin(srcbuf: bytes):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_list = []
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    for idx in range(0, bin_num):
        bin_info = BinInfo()
        bin_info.bCheck = True
        pos = 32 + 32 * idx
        bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 4
        bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 8
        bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 12
        image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 16
        file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
        pos = 32 + 32 * idx + 28
        port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
        if port_type > 0:
            bin_info.bDataPort = False
        else:
            bin_info.bDataPort = True
        bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
        padding_len = file_len % 256
        if padding_len:
            bin_info.pfile += b'\xff' * (256 - padding_len)
            file_len += 256 - padding_len
        bin_info.iFileLength = file_len
        bin_info.iFileCRC = crc32_ver2(4294967295, bin_info.pfile)
        bin_info.iLinkCheckType = LINKCHECK.BOOTROM
        bin_list.append(bin_info)
    if len(bin_list) > 0:
        return bin_list

def bin_crc_check(srcbuf: bytes, extra_data: ExtraData=ExtraData()):
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    header_crc = (srcbuf[8] << 24) + (srcbuf[9] << 16) + (srcbuf[10] << 8) + srcbuf[11]
    header_crc_start_addr = 12
    header_crc_end_addr = bin_num * 32 + 32
    if header_crc_end_addr > len(srcbuf):
        raise Exception(f'bin header crc check failed, header crc end address is out of range, header crc end address: 0x{header_crc_end_addr:x}, file length: 0x{len(srcbuf):x}')
    else:
        header_crc_check = crc32_ver2(4294967295, srcbuf[header_crc_start_addr:header_crc_end_addr])
        if header_crc_check != header_crc:
            raise Exception(f'bin header crc check failed, header crc value in bin file: 0x{header_crc:x}, header crc value calculated from bin file: 0x{header_crc_check:x}')
        elif extra_data is not None and extra_data.bin_parser is not None and (extra_data.bin_parser.crc_check_info is not None) and extra_data.bin_parser.crc_check_info.is_legal():
            crc_check_start_addr = extra_data.bin_parser.crc_check_info.start_addr
            crc_check_oplen = extra_data.bin_parser.crc_check_info.oplen
            crc_start_addr = crc_check_start_addr + 32 * (bin_num + 1)
            crc_end_addr = crc_start_addr + crc_check_oplen
            if crc_end_addr >= len(srcbuf):
                raise Exception(f'crc check parameter error, crc check end address is out of range, crc check end address: 0x{crc_end_addr:x}, file length: 0x{len(srcbuf):x}')
            else:
                crc = (srcbuf[28] << 24) + (srcbuf[29] << 16) + (srcbuf[30] << 8) + srcbuf[31]
                crc_check = crc32_ver2(4294967295, srcbuf[crc_start_addr:crc_end_addr] + srcbuf[:8])
                if crc_check != crc:
                    raise Exception(f'bin crc check failed, crc value in bin file: 0x{crc:x}, crc value calculated from bin file: 0x{crc_check:x}')

def load_bl1_sam_un_bin(srcbuf: bytes, extra_data: ExtraData=ExtraData()):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    if extra_data is not None and extra_data.just_read_file_info:
        return [BinInfo()] * bin_num
    else:
        bin_list = []
        for idx in range(0, bin_num):
            bin_info = BinInfo()
            bin_info.bCheck = True
            pos = 32 + 32 * idx
            bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 4
            bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 8
            bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 12
            image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 16
            file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 28
            port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
            if port_type > 0:
                bin_info.bDataPort = False
            else:
                bin_info.bDataPort = True
            bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
            padding_len = file_len % 256
            if padding_len:
                bin_info.pfile += b'\xff' * (256 - padding_len)
                file_len += 256 - padding_len
            bin_info.iFileLength = file_len
            bin_info.iLinkCheckType = LINKCHECK.BOOTROM
            bin_list.append(bin_info)
        if len(bin_list) > 0:
            return bin_list

def load_bl2_sam_en_bin(srcbuf: bytes, extra_data: ExtraData=ExtraData()):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    if extra_data is not None and extra_data.just_read_file_info:
        return [BinInfo()] * bin_num
    else:
        bin_crc_check(srcbuf, extra_data)
        bin_list = []
        for idx in range(0, bin_num):
            bin_info = BinInfo()
            bin_info.bCheck = True
            pos = 32 + 32 * idx
            bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 4
            bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 8
            bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 12
            image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 16
            file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 28
            port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
            if port_type > 0:
                bin_info.bDataPort = False
            else:
                bin_info.bDataPort = True
            bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
            padding_len = file_len % 256
            if padding_len:
                bin_info.pfile += b'\xff' * (256 - padding_len)
                file_len += 256 - padding_len
            bin_info.iFileLength = file_len
            bin_info.iLinkCheckType = LINKCHECK.BL2
            bin_list.append(bin_info)
        if len(bin_list) > 0:
            return bin_list

def load_custom_bin(srcbuf: bytes, extra_data: ExtraData=ExtraData()):
    """
    global header size = 32 bytes
    single header size = 32 bytes
    """
    bin_num = (srcbuf[18] << 8) + srcbuf[19]
    if extra_data is not None and extra_data.just_read_file_info:
        return [BinInfo()] * bin_num
    else:
        bin_crc_check(srcbuf, extra_data)
        bin_list = []
        for idx in range(0, bin_num):
            bin_info = BinInfo()
            bin_info.bCheck = True
            pos = 32 + 32 * idx
            bin_info.iPartition_start = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 4
            bin_info.iPartition_size = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 8
            bin_info.iStartAddress = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 12
            image_offset = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 16
            file_len = (srcbuf[pos] << 24) + (srcbuf[pos + 1] << 16) + (srcbuf[pos + 2] << 8) + srcbuf[pos + 3]
            pos = 32 + 32 * idx + 28
            port_type = (srcbuf[pos] << 8) + srcbuf[pos + 1]
            if port_type > 0:
                bin_info.bDataPort = False
            else:
                bin_info.bDataPort = True
            bin_info.pfile = srcbuf[image_offset:image_offset + file_len]
            padding_len = file_len % 256
            if padding_len:
                bin_info.pfile += b'\xff' * (256 - padding_len)
                file_len += 256 - padding_len
            bin_info.iFileLength = file_len
            bin_info.iLinkCheckType = LINKCHECK.BL2
            bin_list.append(bin_info)
        if len(bin_list) > 0:
            return bin_list

def LoadBinFile(path: str, startaddr: int, oplen: int=0, extra_data: ExtraData=ExtraData()):
    with open(path, 'rb') as f:
        pfile = f.read()
        f.close()
    used_bin_parser = None
    for bin_parser in BinParserConfig.bin_parser:
        for magic_word in bin_parser.magic_words:
            magic_word_bytes = magic_word.encode('utf-8')
            magic_word_len = len(magic_word_bytes)
            if len(pfile) >= magic_word_len and pfile[0:magic_word_len] == magic_word_bytes:
                used_bin_parser = bin_parser
        if used_bin_parser is not None:
            break
    if used_bin_parser is not None:
        extra_data.bin_parser = used_bin_parser
        bin_type = BIN_TYPE.TYPE_CUSTOM_SECURE if used_bin_parser.link == 1 else BIN_TYPE.TYPE_CUSTOM_UNSECURE
        return (bin_type, load_custom_bin(pfile, extra_data=extra_data))
    else:
        is_default_version = CustomerVersionConfig.is_default_version(CustomerVersionConfig.customer_version)
        if pfile[0:8] == b'beken...':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_OTA
                listbin = load_ota_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BKDLV10.':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL2_APP_BIN
                listbin = load_bl2_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL1DLV10':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL1_ALL_BIN
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BLXDLV20':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_SECURE_FIX
                listbin = load_secure_boot_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'QSPI_DL.':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_OUTTER_FLASH
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BKFIXED.':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_NORMAL_FIXED
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL2DLV10':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL2_OTA
                listbin = load_bl2_ota_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL1DLV30':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL1_SECUR_MODE
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL1DLV40':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL1_SECURE_FIXED
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL1DLV41':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_BL1_SECURE_EXTENSION
                listbin = load_bl1_all_app_bin(pfile)
                return (bin_type, listbin)
        elif pfile[0:8] == b'BL1SAMUN':
            if extra_data is None:
                extra_data = ExtraData()
            bin_type = BIN_TYPE.TYPE_SAM_UN
            listbin = load_bl1_sam_un_bin(pfile, extra_data=extra_data)
            return (bin_type, listbin)
        elif pfile[0:8] == b'BL2SAMEN':
            if is_default_version:
                bin_type = BIN_TYPE.TYPE_SAM_EN
                if extra_data is None:
                    extra_data = ExtraData()
                extra_data.bin_parser = BinParser(name='BL2SAMEN', type='secure', link=1, magic_words=[b'BL2SAMEN'], crc_check_info=CrcCheckInfo(start_addr=1024, oplen=4096))
                listbin = load_bl2_sam_en_bin(pfile, extra_data=extra_data)
                return (bin_type, listbin)
        elif is_default_version:
            bin_type = BIN_TYPE.TYPE_NORMAL
            src_file_len = len(pfile)
            bininfo = load_normal_bin(pfile)
            bininfo.iStartAddress = startaddr
            if 0 < oplen < src_file_len:
                bininfo.iFileLength = oplen
                bininfo.pfile = bininfo.pfile[0:oplen]
            bininfo.sFilePath = path
            bin_list = [bininfo]
            return (bin_type, bin_list)
        raise Exception('Unsupported bin file')

def _split_binfile_range_spec(subbin: str):
    """
    Parse multi-segment form 'p@ath@start-olen' (addresses in hex, same as legacy '.bin@').
    Last '@' separates file path from range so paths may contain '@'.
    Returns (path, startaddress, oplen) or None if not a range spec.
    """
    if '@' not in subbin:
        return
    else:
        at = subbin.rfind('@')
        path_part = subbin[:at]
        if not path_part:
            return
        else:
            range_part = subbin[at + 1:]
            if '-' not in range_part:
                return
            else:
                dash = range_part.index('-')
                st0 = range_part[:dash].strip()
                st1 = range_part[dash + 1:].strip()
                try:
                    startaddress = int(st0, 16)
                    oplen = int(st1, 16)
                except ValueError:
                    return
                return (path_part, startaddress, oplen)

def _merge_parsed_bin(parsed_type: BIN_TYPE, parsed_bins: list, normal_bins: list, other_bins: list):
    """
    Merge parsed bin results and group non-normal bins by their type.
    """
    if parsed_type == BIN_TYPE.TYPE_NORMAL:
        normal_bins.extend(parsed_bins)
    else:
        for single_type_bin in other_bins:
            if single_type_bin.binType == parsed_type:
                single_type_bin.binList.extend(parsed_bins)
                break
        else:
            other_bins.append(SingleTypeBinInfo(binType=parsed_type, binList=list(parsed_bins)))
    return (normal_bins, other_bins)

def _check_mixed_bin_info(normal_bins: List[BinInfo], other_bins: List[SingleTypeBinInfo]):
    if len(other_bins) > 1:
        if normal_bins:
            return (None, [SingleTypeBinInfo(binType=BIN_TYPE.TYPE_NORMAL, binList=list(normal_bins)), *other_bins])
        else:
            return (None, other_bins)
    elif len(other_bins) == 1:
        other_bins[0].binList = list(normal_bins) + other_bins[0].binList
        return (other_bins[0].binType, other_bins)
    else:
        return (BIN_TYPE.TYPE_NORMAL, [SingleTypeBinInfo(binType=BIN_TYPE.TYPE_NORMAL, binList=list(normal_bins))])

def parse_binfile_info(main_bin: str, start_addr: int, extra_data: ExtraData=ExtraData()):
    """
    parse main_bin such as './all-app.bin' or './app.trpk' with start address
    or parse multi_bin such as './bootloader.bin,./bsp.bin@1100,./app.bin@5200-50000'
    Range form also supports non-.bin extensions, e.g. './app.trpk@0x1000-0x1000'.
    """
    strlist = []
    normal_bin_list = []
    other_bin_list = []
    path_list = []
    if main_bin:
        if main_bin.find(',') == -1:
            strlist = [main_bin]
        else:
            strlist = main_bin.split(',')
        for subbin in strlist:
            subbin = subbin.strip()
            range_spec = _split_binfile_range_spec(subbin)
            if range_spec is None:
                (bintype, binlist) = LoadBinFile(subbin, start_addr, extra_data=extra_data)
                path_list.append(subbin)
            else:
                (path_part, startaddress, oplen) = range_spec
                (bintype, binlist) = LoadBinFile(path_part, startaddress, oplen, extra_data=extra_data)
                path_list.append(path_part)
            (normal_bin_list, other_bin_list) = _merge_parsed_bin(bintype, binlist, normal_bin_list, other_bin_list)
        (bin_type, bin_info) = _check_mixed_bin_info(normal_bin_list, other_bin_list)
        return (bin_type, bin_info, path_list)
    else:
        return (None, None, None)

def _parse_infile_json_int(value, default_value: int):
    if value is None or value == '':
        return default_value
    elif isinstance(value, int):
        return value
    else:
        return int(str(value), 16)

def parse_binfile_info_json(infile_json: str, start_addr: int, extra_data: ExtraData=ExtraData()):
    """
    Parse JSON bin input.
    Example: [{"path":"D:/fw/app,v1.bin","start":"0x0","len":"0x1000"}]
    """
    if not infile_json:
        return (None, None, None)
    else:
        try:
            file_items = json.loads(infile_json)
        except Exception as e:
            raise Exception(f'Invalid infile_json: {e}')
        if not isinstance(file_items, list) or len(file_items) == 0:
            raise Exception('Invalid infile_json: expected a non-empty list.')
        else:
            normal_bin_list = []
            other_bin_list = []
            path_list = []
            for item in file_items:
                if not isinstance(item, dict):
                    raise Exception('Invalid infile_json: each item must be an object.')
                else:
                    path = item.get('path')
                    if not path:
                        raise Exception('Invalid infile_json: missing path.')
                    else:
                        item_start_addr = _parse_infile_json_int(item.get('start'), start_addr)
                        item_len = _parse_infile_json_int(item.get('len'), 0)
                        (bin_type, binlist) = LoadBinFile(path, item_start_addr, item_len, extra_data=extra_data)
                        (normal_bin_list, other_bin_list) = _merge_parsed_bin(bin_type, binlist, normal_bin_list, other_bin_list)
                        path_list.append(path)
            (bin_type, bin_info) = _check_mixed_bin_info(normal_bin_list, other_bin_list)
            return (bin_type, bin_info, path_list)

def parse_device_name_info(dev_name: str):
    """
    string like "beken@0x2e000-5"
    return result,address,name,length
    """
    if dev_name and dev_name.find('@') != -1:
        ftmp = dev_name.split('@')
        if len(ftmp) < 2:
            return (False, None, None, 0)
        name = bytes(ftmp[0], 'ascii')
        stmp = ftmp[1].split('-')
        if len(stmp) < 2:
            return (False, None, None, 0)
        Addr = int(stmp[0], 16)
        length = int(stmp[1])
    return (True, name, Addr, length)

def parse_device_mac_info(dev_mac: str):
    """
    string like "aabbccddeeff@0x1e000-6"
    return result,address,mac,length
    """
    if dev_mac and dev_mac.find('@') != -1:
        ftmp = dev_mac.split('@')
        if len(ftmp) < 2:
            return (False, None, None, 0)
        devid = bytes.fromhex(ftmp[0])
        stmp = ftmp[1].split('-')
        if len(stmp) < 2:
            return (False, None, None, 0)
        addr = int(stmp[0], 16)
        length = int(stmp[1])
    return (True, devid, addr, length)

def parse_erase_info(freedom_erase: str):
    """
    parse string such as '0-1000,2000-1000,3000-2000'
    """
    binlist = []
    if freedom_erase:
        splittmp = freedom_erase.split(',')
        for suberase in splittmp:
            stmp = suberase.split('-')
            if len(stmp) == 2:
                eraseinfo = BinInfo()
                eraseinfo.bCheck = True
                eraseinfo.iStartAddress = int(stmp[0], 16)
                eraseinfo.iFileLength = int(stmp[1], 16)
                binlist.append(eraseinfo)
    return binlist if len(binlist) > 0 else None

def parse_dump_info(freedom_read: str):
    """
    parse string such as '0-1000,2000-1000,3000-2000'
    or './dump_1.bin@0-1000,./dump_2.bin@2000-1000,./dump_3.bin@3000-2000'
    """
    binlist = []
    gen_bin_idx = 0
    if freedom_read:
        splittmp = freedom_read.split(',')
        for subread in splittmp:
            readinfo = BinInfo()
            readinfo.bCheck = True
            if subread.find('@') == -1:
                readinfo.sFilePath = f'dump{gen_bin_idx}.bin'
                stmp = subread.split('-')
            else:
                ptmp = subread.split('@')
                if len(ptmp) == 2:
                    readinfo.sFilePath = ptmp[0]
                    stmp = ptmp[1].split('-')
            if len(stmp) == 2:
                readinfo.iStartAddress = int(stmp[0], 16)
                readinfo.iFileLength = int(stmp[1], 16)
                binlist.append(readinfo)
            gen_bin_idx += 1
    return binlist if len(binlist) > 0 else None

def parse_safe_json_file(jsfile: str):
    with open(jsfile, 'r') as f:
        jess = f.read()
        jess = jess.lower()
        f.close()
    try:
        decoder = json.JSONDecoder()
        (jroot, idx) = decoder.raw_decode(jess)
    except json.JSONDecodeError as e:
        try:
            jroot = json.loads(jess)
        except json.JSONDecodeError:
            raise Exception(f'Invalid JSON in file {jsfile}: {str(e)}')
    jroot = dict(jroot)
    safeinfo = safe_data()
    if 'user_operate_enable' in jroot.keys():
        safeinfo.user_operate_enable = True if jroot['user_operate_enable'] == 'true' else False
    if 'efuse_enable' in jroot.keys():
        safeinfo.efuse_enable = True if jroot['efuse_enable'] == 'true' else False
    if 'security_ctrl_enable' in jroot.keys():
        safeinfo.security_ctrl_enable = True if jroot['security_ctrl_enable'] == 'true' else False
    if 'security_data_enable' in jroot.keys():
        safeinfo.security_data_enable = True if jroot['security_data_enable'] == 'true' else False
    if 'user_operate' in jroot.keys():
        for userinfo in jroot['user_operate']:
            usr = user_operate()
            if 'name' in userinfo.keys():
                usr.name = userinfo['name']
            if 'mode' in userinfo.keys():
                usr.mode = userinfo['mode']
            if 'permission' in userinfo.keys():
                usr.permission = userinfo['permission']
            if 'start_addr' in userinfo.keys():
                usr.start_addr = userinfo['start_addr']
            if 'last_valid_addr' in userinfo.keys():
                usr.end_addr = userinfo['last_valid_addr']
            if 'byte_len' in userinfo.keys():
                usr.byte_len = userinfo['byte_len']
            if 'data' in userinfo.keys():
                usr.data = userinfo['data']
            if 'data_type' in userinfo.keys():
                usr.data_type = userinfo['data_type']
            if 'status' in userinfo.keys():
                usr.status = userinfo['status']
            if 'big_endian' in userinfo.keys():
                usr.big_endian = userinfo['big_endian']
                usr.specify_big_endian()
            if 'reverse' in userinfo.keys():
                usr.reverse = userinfo['reverse']
                usr.specify_reverse()
            safeinfo.user_operate_list.append(usr)
    if 'efuse' in jroot.keys():
        for efuseinfo in jroot['efuse']:
            efs = efuse_info()
            if 'name' in efuseinfo.keys():
                efs.name = efuseinfo['name']
            if 'mode' in efuseinfo.keys():
                efs.mode = efuseinfo['mode']
            if 'byte_addr' in efuseinfo.keys():
                efs.byte_addr = efuseinfo['byte_addr']
            if 'last_valid_addr' in efuseinfo.keys():
                efs.end_addr = efuseinfo['last_valid_addr']
            if 'length' in efuseinfo.keys():
                efs.length = efuseinfo['length']
            if 'data' in efuseinfo.keys():
                efs.data = efuseinfo['data']
            if 'status' in efuseinfo.keys():
                efs.status = efuseinfo['status']
            safeinfo.efuse_info_list.append(efs)
    if 'security_data' in jroot.keys():
        for secinfo in jroot['security_data']:
            secu = user_operate()
            if 'name' in secinfo.keys():
                secu.name = secinfo['name']
            if 'mode' in secinfo.keys():
                secu.mode = secinfo['mode']
            if 'permission' in secinfo.keys():
                secu.permission = secinfo['permission']
            if 'start_addr' in secinfo.keys():
                secu.start_addr = secinfo['start_addr']
                if int(secu.start_addr, 16) % 4 != 0:
                    raise Exception('security data start address must be 4 multiple')
            if 'last_valid_addr' in secinfo.keys():
                secu.end_addr = secinfo['last_valid_addr']
            if 'byte_len' in secinfo.keys():
                secu.byte_len = secinfo['byte_len']
                if int(secu.byte_len, 16) % 4 != 0:
                    raise Exception('security data length must be 4 multiple')
            if 'data' in secinfo.keys():
                secu.data = secinfo['data']
            if 'data_type' in secinfo.keys():
                secu.data_type = secinfo['data_type']
            if 'status' in secinfo.keys():
                secu.status = secinfo['status']
            if 'big_endian' in secinfo.keys():
                secu.big_endian = secinfo['big_endian']
                secu.specify_big_endian()
            if 'reverse' in secinfo.keys():
                secu.reverse = secinfo['reverse']
                secu.specify_reverse()
            safeinfo.security_data_list.append(secu)
    if 'security_ctrl' in jroot.keys():
        ctrlitems = jroot['security_ctrl'][0]
        for items in ctrlitems.items():
            safeinfo.security_ctrl.append(items[1])
    return safeinfo

def parse_readinfo_otp(otpinfo: str):
    """
    string like '0x4b010000-4'
    return list[address, length]
    """
    otp_list = []
    splittmp = otpinfo.split(',')
    for info in splittmp:
        tmp = info.split('-')
        if len(tmp) >= 2:
            address = int(tmp[0], 16)
            oplen = int(tmp[1], 16)
            otp_list.append([address, oplen])
    if len(otp_list) > 0:
        return otp_list

def parse_writeinfo_otp(otpinfo: str):
    """
    string like '73c7bf397f2ad6bf@0x4b100460-8'
    return list[value, address, length]
    """
    info_list = []
    splittmp = otpinfo.split(',')
    for info in splittmp:
        tmp = info.split('@')
        if len(tmp) >= 2:
            value = tmp[0]
            tmp = tmp[1].split('-')
            if len(tmp) >= 2:
                address = int(tmp[0], 16)
                oplen = int(tmp[1])
                info_list.append([value, address, oplen])
    return info_list if len(info_list) > 0 else None

def parse_writeinfo_efuse(efusinfo: str):
    """
    string like '0x1-0x7', byte index - bit index
    return list[address, bit]
    """
    info_list = []
    splittmp = efusinfo.split(',')
    for info in splittmp:
        if info.find('@') != -1:
            sp_tmp = efusinfo.split('@')
            v = int(sp_tmp[0])
            tmp = sp_tmp[1].split('-')
            if len(tmp) >= 2:
                address = int(tmp[0], 16)
                bit = int(tmp[1], 16)
                info_list.append([v, address, bit])
        else:
            tmp = info.split('-')
            if len(tmp) >= 2:
                address = int(tmp[0], 16)
                v = int(tmp[1], 16)
                info_list.append([address, v])
    if len(info_list) > 0:
        return info_list

def is_buf_all_0xff(buf):
    return buf.count(b'\xff') == len(buf)

def get_script_dir():
    script_dir = os.path.abspath(__file__)
    script_dir = os.path.dirname(script_dir)
    return script_dir

def bytes_reverse(buf: bytes):
    oplen = len(buf)
    tmp = bytearray()
    for i in range(oplen):
        tmp.append(buf[oplen - 1 - i])
    return tmp

def bytes_reverse_per4bytes(buf: bytes):
    oplen = len(buf)
    tmp = bytearray()
    idx = 0
    while idx < oplen:
        byss = buf[oplen - idx - 4:oplen - idx]
        tmp += byss
        idx += 4
    return tmp

def available_serial_ports():
    """
    lists serial port names
    :raises EnvironmentError:
        On unsupported or unknown platforms
    :returns:
        A list of the serial ports available on the system
    """
    os = get_os_type()
    if os == 'Windows':
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif os == 'Linux' or os == 'Raspberry Pi':
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif os == 'MacOS':
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')
    res = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            res.append(port)
        except (OSError, serial.SerialException):
            pass
    return res

def parse_expand_data(expand_data: str):
    expand_data_list = []
    for data in expand_data.split(','):
        temp_list = data.split('@')
        if len(temp_list) < 4:
            continue
        else:
            name = temp_list[0]
            type = int(temp_list[1])
            start_addr = int(temp_list[2], 16)
            value = temp_list[3]

            def convert_hex(data, big_endian):
                if data.startswith('0x'):
                    data = value[2:]
                if len(data) % 2 != 0:
                    data = '0' + data
                bytes_data = bytes.fromhex(data)
                if not big_endian:
                    bytes_data = bytes(reversed(bytes_data))
                return bytes_data
            if type == ExpandDataType.HEX_BIG.value:
                bytes_data = convert_hex(value, True)
            elif type == ExpandDataType.HEX_LITTER.value:
                bytes_data = convert_hex(value, False)
            elif type == ExpandDataType.STRING_LITTER.value:
                bytes_data = bytes(reversed(value.encode()))
            elif type == ExpandDataType.STRING_BIG.value:
                bytes_data = value.encode()
            expand_data_list.append(ExpandData(name, start_addr, len(bytes_data), bytes_data))
    return expand_data_list
MAC_ADDRESS_BYTE_LEN = 6

def _value_to_bytes_for_type(value: str, data_type: int):
    """Convert value string to bytes according to ExpandDataType. Used by parse_expand_data_batch."""

    def convert_hex(data, big_endian):
        if data.startswith('0x'):
            data = data[2:]
        if len(data) % 2 != 0:
            data = '0' + data
        bytes_data = bytes.fromhex(data)
        if not big_endian:
            bytes_data = bytes(reversed(bytes_data))
        return bytes_data
    if data_type == ExpandDataType.HEX_BIG.value:
        return convert_hex(value, True)
    elif data_type == ExpandDataType.HEX_LITTER.value:
        return convert_hex(value, False)
    elif data_type == ExpandDataType.STRING_LITTER.value:
        return bytes(reversed(value.encode()))
    elif data_type == ExpandDataType.STRING_BIG.value:
        return value.encode()
    else:
        return convert_hex(value, True)

def _normalize_mac_address_bytes(bytes_data: bytes, big_endian: bool) -> bytes:
    """将 MAC 地址规范为 6 字节：大端左补零，小端右补零；超过 6 字节时大端取低 6 字节，小端取高 6 字节。"""
    if len(bytes_data) >= MAC_ADDRESS_BYTE_LEN:
        return bytes_data[-MAC_ADDRESS_BYTE_LEN:] if big_endian else bytes_data[:MAC_ADDRESS_BYTE_LEN]
    else:
        pad = MAC_ADDRESS_BYTE_LEN - len(bytes_data)
        return bytes(pad) + bytes_data if big_endian else bytes_data + bytes(pad)

def parse_expand_data_batch(expand_data_batch: str, factory_mode: bool=True):
    expand_data_list = []
    step_list = []
    for data in expand_data_batch.split(','):
        data = data.strip()
        if not data:
            continue
        else:
            temp_list = data.split('@')
            if len(temp_list) < 4:
                continue
            else:
                name = temp_list[0]
                data_type = int(temp_list[1])
                start_addr = int(temp_list[2], 16)
                value = temp_list[3]
                step = 0
                if len(temp_list) >= 5 and temp_list[4].strip().isdigit():
                    step = int(temp_list[4])
                bytes_data = _value_to_bytes_for_type(value, data_type)
                if factory_mode and name and ('MAC' in name.upper()) and (data_type in (ExpandDataType.HEX_BIG.value, ExpandDataType.HEX_LITTER.value)):
                    bytes_data = _normalize_mac_address_bytes(bytes_data, data_type == ExpandDataType.HEX_BIG.value)
                expand_data_list.append(ExpandData(name, start_addr, len(bytes_data), bytes_data))
                step_list.append(step)
    return (expand_data_list, step_list)
