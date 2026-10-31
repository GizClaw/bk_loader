# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/flash_adapter/flash_config.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import os
import sys
import yaml
from bkutils.common.bk_global import BkFlashConfigOut
class FlashConfig(object):
    def __init__(self) -> None:
        self.cfg_file_path = self.get_config_file_path()
        self.cfg_info = self.parse_flash_config()
        self.flash_info = None
        self.merge_outter()
    def merge_outter(self):
        try:
            self.cfg_file_path_out = BkFlashConfigOut.flash_config_path_out
            self.cfg_info_out = None
            if self.cfg_file_path_out is None:
                return
            else:
                if not os.path.isfile(self.cfg_file_path_out):
                    return
                else:
                    with open(self.cfg_file_path_out, 'r', encoding='utf-8') as f:
                        self.cfg_info_out = yaml.safe_load(f)
                for temp_out in self.cfg_info_out:
                    find_flag = False
                    for temp_inner in self.cfg_info:
                        find_flag = temp_inner[0] == temp_out[0]
                        if find_flag:
                            break
                    if not find_flag:
                        self.cfg_info.append(temp_out)
        except:
            pass
    def get_config_file_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'flash_info.yml')
    def parse_flash_config(self):
        if not os.path.isfile(self.cfg_file_path):
            raise Exception('{0} not exist'.format(self.cfg_file_path))
        else:
            with open(self.cfg_file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
    def parse_flash_info(self, flash_id):
        for tmp_flash in self.cfg_info:
            if tmp_flash[0] == flash_id:
                self.flash_info = tmp_flash
        if self.flash_info is None:
            raise Exception('No support flash, please update flash config')
    @property
    def flash_status_reg_read_code(self) -> list:
        if type(self.flash_info[7]) == list:
            return self.flash_info[7]
        else:
            return [self.flash_info[7]]
    @property
    def flash_status_reg_write_code(self) -> list:
        if type(self.flash_info[8]) == list:
            return self.flash_info[8]
        else:
            return [self.flash_info[8]]
    @property
    def flash_size(self) -> int:
        src = self.flash_info[3].split('*')
        size = 1
        for tmp_num in src:
            size *= int(tmp_num)
        return size
    def __format_register_bit_info(self, bit_list):
        val = []
        mask = []
        tmp_mask_val = 0
        tmp_val = 0
        for index in range(len(bit_list)):
            if bit_list[index] is not None:
                tmp_mask_val |= 1 << len(bit_list) - index - 1
                tmp_val |= bit_list[index] << len(bit_list) - index - 1
        for _ in range(len(bit_list) // 8):
            val.append(tmp_val >> 8 * _ & 255)
            mask.append(tmp_mask_val >> 8 * _ & 255)
        return (val, mask)
    @property
    def unprotect_register_value(self) -> list:
        return self.__format_register_bit_info(self.flash_info[4])
    @property
    def protect_register_value(self) -> list:
        return self.__format_register_bit_info(self.flash_info[5])
    def compare_register_value(self, src: list, dest: list, mask: list):
        for _ in range(len(src)):
            if src[_] & mask[_] != dest[_] & mask[_]:
                return False
        return True