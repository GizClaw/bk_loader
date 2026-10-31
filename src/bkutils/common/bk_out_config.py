# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/common/bk_out_config.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from dataclasses import dataclass
from typing import List
import json
import os
import yaml
class BkOutConfig(object):
    check_response_code = True
    chip_name = ''
    @staticmethod
    def set_bk_loader_config_path_out(bk_loader_config_path_out: str):
        try:
            BkOutConfig(bk_loader_config_path_out)
        except Exception as e:
            from bkutils.bk_log import BKLog
            BKLog.e(f'set bk loader config path failed, error: {e}')
    def __init__(self, outter_path) -> None:
        inner_path = self.get_config_file_path()
        if outter_path is not None and os.path.exists(outter_path) and os.path.isfile(outter_path):
            path = outter_path
        else:
            if inner_path is not None and os.path.exists(inner_path) and os.path.isfile(inner_path):
                path = inner_path
            else:
                return None
        with open(path, 'r', encoding='utf-8') as f:
            self.cfg_info = yaml.safe_load(f)
            if not self.cfg_info.get('enable', False):
                return
            else:
                BkOutConfig.chip_name = self.cfg_info.get('chip_name', BkOutConfig.chip_name)
                BkOutConfig.check_response_code = self.cfg_info.get('check_response_code', BkOutConfig.check_response_code)
                link_check_info = self.cfg_info.get('linkcheck', {})
                if len(link_check_info) > 0:
                    BklinkcheckConfig(link_check_info)
                read_flash_info = self.cfg_info.get('read_flash', {})
                if len(read_flash_info) > 0:
                    BkReadFlashConfig(read_flash_info)
                if 'read_flash_mid' in self.cfg_info:
                    BkReadFlashMidConfig(self.cfg_info.get('read_flash_mid') or {})
                set_baudrate_info = self.cfg_info.get('set_baudrate', {})
                if len(set_baudrate_info) > 0:
                    BkSetBaudrateConfig(set_baudrate_info)
                download_flow_info = self.cfg_info.get('download_flow', {})
                if len(download_flow_info) > 0:
                    BkDownloadFlowConfig(download_flow_info)
                if 'enable_random_bin_verify' in self.cfg_info:
                    BkDownloadFlowConfig.cli_enable_random_bin_verify = bool(self.cfg_info['enable_random_bin_verify'])
                erase_flow_info = self.cfg_info.get('erase_flow', {})
                if len(erase_flow_info) > 0:
                    BkEraseFlowConfig(erase_flow_info)
                otp_config_info = self.cfg_info.get('otp_config', {})
                if len(otp_config_info) > 0:
                    BKOTPConfig(otp_config_info)
    def get_config_file_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'bk_loader_config_inner.yaml')
class BkSetBaudrateConfig(object):
    cmd_delay_ms = 90
    switch_delay_ms = 50
    wait_response_timeout_ms = 200
    def __init__(self, set_baudrate_info) -> None:
        BkSetBaudrateConfig.cmd_delay_ms = set_baudrate_info.get('cmd_delay_ms', BkSetBaudrateConfig.cmd_delay_ms)
        BkSetBaudrateConfig.switch_delay_ms = set_baudrate_info.get('switch_delay_ms', BkSetBaudrateConfig.switch_delay_ms)
        BkSetBaudrateConfig.wait_response_timeout_ms = set_baudrate_info.get('wait_response_timeout_ms', BkSetBaudrateConfig.wait_response_timeout_ms)
class BkReadFlashConfig(object):
    retry_count = 10
    fixed_timeout_ms = 1000
    delay_after_fail_ms = 100
    timeout_factor = 2
    def __init__(self, read_flash_info) -> None:
        BkReadFlashConfig.retry_count = read_flash_info.get('retry_count', BkReadFlashConfig.retry_count)
        BkReadFlashConfig.fixed_timeout_ms = read_flash_info.get('fixed_timeout_ms', BkReadFlashConfig.fixed_timeout_ms)
        BkReadFlashConfig.delay_after_fail_ms = read_flash_info.get('delay_after_fail_ms', BkReadFlashConfig.delay_after_fail_ms)
        BkReadFlashConfig.timeout_factor = read_flash_info.get('timeout_factor', BkReadFlashConfig.timeout_factor)
class BkReadFlashMidConfig(object):
    """读 Flash MID（0x9f / parse_flash_info）重试，与 read_flash 数据读独立。"""
    retry_count = 5
    delay_after_fail_ms = 200
    wait_response_timeout_sec = 0.1
    def __init__(self, read_flash_mid_info) -> None:
        BkReadFlashMidConfig.retry_count = read_flash_mid_info.get('retry_count', BkReadFlashMidConfig.retry_count)
        BkReadFlashMidConfig.delay_after_fail_ms = read_flash_mid_info.get('delay_after_fail_ms', BkReadFlashMidConfig.delay_after_fail_ms)
        BkReadFlashMidConfig.wait_response_timeout_sec = read_flash_mid_info.get('wait_response_timeout_sec', BkReadFlashMidConfig.wait_response_timeout_sec)
class BklinkcheckConfig(object):
    use_version = 2
    def __init__(self, link_check_info) -> None:
        BklinkcheckConfig.use_version = link_check_info.get('use_version', 2)
        if BklinkcheckConfig.use_version == 1:
            pass
        else:
            if BklinkcheckConfig.use_version == 2:
                link_check_info_v2 = link_check_info.get('version_2', {})
                if len(link_check_info_v2) > 0:
                    BklinkcheckConfigV2(link_check_info_v2)
            else:
                if BklinkcheckConfig.use_version == 3:
                    link_check_info_v3 = link_check_info.get('version_3', {})
                    if len(link_check_info_v3) > 0:
                        BklinkcheckConfigV3(link_check_info_v3)
class BklinkcheckConfigV2(object):
    max_recycle_count = 2
    max_retry_interval = 80
    max_wait_time = 10
    use_mixed_detection = True
    def __init__(self, link_check_info_v2) -> None:
        BklinkcheckConfigV2.max_recycle_count = link_check_info_v2.get('max_recycle_count', 2)
        BklinkcheckConfigV2.max_retry_interval = link_check_info_v2.get('max_retry_interval', 80)
        BklinkcheckConfigV2.max_wait_time = link_check_info_v2.get('max_wait_time', 10)
        BklinkcheckConfigV2.use_mixed_detection = link_check_info_v2.get('use_mixed_detection', False)
class BklinkcheckConfigV3(object):
    max_recycle_count = 30
    max_retry_interval = 200
    line_break_timeout_ms = 1
    delay_time_before_reboot = 10
    delay_time_after_reboot = 5
    use_mixed_detection = True
    def __init__(self, link_check_info_v3) -> None:
        BklinkcheckConfigV3.max_recycle_count = link_check_info_v3.get('max_recycle_count', BklinkcheckConfigV3.max_recycle_count)
        BklinkcheckConfigV3.max_retry_interval = link_check_info_v3.get('max_retry_interval', BklinkcheckConfigV3.max_retry_interval)
        BklinkcheckConfigV3.line_break_timeout_ms = link_check_info_v3.get('line_break_timeout_ms', BklinkcheckConfigV3.line_break_timeout_ms)
        BklinkcheckConfigV3.delay_time_before_reboot = link_check_info_v3.get('delay_time_before_reboot', BklinkcheckConfigV3.delay_time_before_reboot)
        BklinkcheckConfigV3.delay_time_after_reboot = link_check_info_v3.get('delay_time_after_reboot', BklinkcheckConfigV3.delay_time_after_reboot)
        BklinkcheckConfigV3.use_mixed_detection = link_check_info_v3.get('use_mixed_detection', BklinkcheckConfigV3.use_mixed_detection)
class BkDownloadFlowConfig(object):
    check_bin_board_crc_sync = True
    verify_product_id = True
    allow_change_linkcheck_obj = False
    develop_set_baudrate_before_align = False
    factory_set_baudrate_before_align = False
    develop_switch_baudrate_for_expand_data = False
    factory_switch_baudrate_for_expand_data = False
    cli_enable_random_bin_verify = False
    crc_verify_chunk_bytes = 4096
    @staticmethod
    def _normalize_crc_verify_chunk_kb(value):
        """YAML 值为 4KiB 扇区个数：1=4K，2=8K，4=16K。"""
        default = 4096
        size_4k = 4096
        try:
            n = int(value)
            return n * size_4k if n >= 1 else default
        except Exception:
            return default
    def __init__(self, download_flow_info) -> None:
        BkDownloadFlowConfig.check_bin_board_crc_sync = download_flow_info.get('check_bin_board_crc_sync', BkDownloadFlowConfig.check_bin_board_crc_sync)
        BkDownloadFlowConfig.verify_product_id = download_flow_info.get('verify_product_id', BkDownloadFlowConfig.verify_product_id)
        BkDownloadFlowConfig.allow_change_linkcheck_obj = download_flow_info.get('allow_change_linkcheck_obj', BkDownloadFlowConfig.allow_change_linkcheck_obj)
        BkDownloadFlowConfig.develop_set_baudrate_before_align = download_flow_info.get('develop_set_baudrate_before_align', BkDownloadFlowConfig.develop_set_baudrate_before_align)
        BkDownloadFlowConfig.factory_set_baudrate_before_align = download_flow_info.get('factory_set_baudrate_before_align', BkDownloadFlowConfig.factory_set_baudrate_before_align)
        BkDownloadFlowConfig.develop_switch_baudrate_for_expand_data = download_flow_info.get('develop_switch_baudrate_for_expand_data', BkDownloadFlowConfig.develop_switch_baudrate_for_expand_data)
        BkDownloadFlowConfig.factory_switch_baudrate_for_expand_data = download_flow_info.get('factory_switch_baudrate_for_expand_data', BkDownloadFlowConfig.factory_switch_baudrate_for_expand_data)
        BkDownloadFlowConfig.cli_enable_random_bin_verify = download_flow_info.get('cli_enable_random_bin_verify', BkDownloadFlowConfig.cli_enable_random_bin_verify)
        BkDownloadFlowConfig.crc_verify_chunk_bytes = BkDownloadFlowConfig._normalize_crc_verify_chunk_kb(download_flow_info.get('crc_verify_chunk_kb', 1))
class BkEraseFlowConfig(object):
    allow_change_linkcheck_obj = True
    develop_set_baudrate_before_align = False
    def __init__(self, erase_flow_info) -> None:
        BkEraseFlowConfig.allow_change_linkcheck_obj = erase_flow_info.get('allow_change_linkcheck_obj', BkEraseFlowConfig.allow_change_linkcheck_obj)
        BkEraseFlowConfig.develop_set_baudrate_before_align = erase_flow_info.get('develop_set_baudrate_before_align', BkEraseFlowConfig.develop_set_baudrate_before_align)
class BKOTPConfig(object):
    must_use_bl1 = False
    def __init__(self, otp_config_info) -> None:
        BKOTPConfig.must_use_bl1 = otp_config_info.get('must_use_bl1', BKOTPConfig.must_use_bl1)
@dataclass
class CrcCheckInfo:
    start_addr: int = 0
    oplen: int = 0
    def is_legal(self):
        if self.start_addr < 0 or self.oplen <= 0:
            return False
        else:
            return True
def _parse_hex_int(value):
    """Parse a value as hexadecimal to int. \n    All input values are treated as hexadecimal format.\n    Supports both \"0x400\" and \"400\" formats.\n    """
    if isinstance(value, int):
        return value
    else:
        if isinstance(value, str):
            return int(value, 16)
        else:
            if value:
                return int(value, 16)
            else:
                return 0
@dataclass
class BinParser:
    name: str = ''
    type: str = 'secure'
    link: int = 1
    magic_words: List[str] = None
    crc_check_info: CrcCheckInfo = None
    def __post_init__(self):
        if self.magic_words is None:
            self.magic_words = []
        if self.crc_check_info is None:
            self.crc_check_info = CrcCheckInfo()
class BinParserConfig(object):
    bin_parser: List[BinParser] = []
    def __init__(self, bin_parser_path: str) -> None:
        try:
            if bin_parser_path is not None and os.path.exists(bin_parser_path) and os.path.isfile(bin_parser_path):
                        with open(bin_parser_path, 'r', encoding='utf-8') as f:
                            cfg_info = yaml.safe_load(f)
                            if cfg_info is not None and len(cfg_info) > 0:
                                    bin_parser = cfg_info.get('bin_parser', [])
                                    if bin_parser is not None and len(bin_parser) > 0:
                                            BinParserConfig.bin_parser = []
                                            for bp in bin_parser:
                                                try:
                                                    bp_copy = bp.copy()
                                                    crc_info_dict = bp_copy.pop('crc_check_info', None)
                                                    crc_check_info = None
                                                    if crc_info_dict is not None and len(crc_info_dict) > 0:
                                                            try:
                                                                start_addr = _parse_hex_int(crc_info_dict.get('start_addr', 0))
                                                                oplen = _parse_hex_int(crc_info_dict.get('oplen', 0))
                                                                crc_check_info = CrcCheckInfo(start_addr=start_addr, oplen=oplen)
                                                            except Exception as e:
                                                                crc_check_info = CrcCheckInfo()
                                                    parser = BinParser(name=bp_copy.get('name', ''), type=bp_copy.get('type', ''), link=bp_copy.get('link', 1), magic_words=bp_copy.get('magic_words', []), crc_check_info=crc_check_info)
                                                    BinParserConfig.bin_parser.append(parser)
                                                except Exception as e:
                                                    pass
        except Exception as e:
            BinParserConfig.bin_parser = []
class CustomerVersionConfig(object):
    default_customer_version = '2'
    customer_version = default_customer_version
    def __init__(self) -> None:
        path = self.get_config_file_path()
        if path is not None and os.path.exists(path) and os.path.isfile(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        cfg_info = yaml.safe_load(f)
                        if cfg_info is not None and len(cfg_info) > 0:
                                customer_version = cfg_info.get('customer_version', '')
                                if customer_version is not None and len(customer_version) > 0:
                                        CustomerVersionConfig.customer_version = customer_version
    def get_config_file_path(self):
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'version.yaml')
    @staticmethod
    def is_default_version(customer_version: str) -> bool:
        if customer_version is None or len(customer_version) == 0:
            return False
        else:
            if customer_version == CustomerVersionConfig.default_customer_version:
                return True
            else:
                return False