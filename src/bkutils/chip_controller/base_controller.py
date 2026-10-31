# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/chip_controller/base_controller.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

import time
from bkutils.common.bk_out_config import BklinkcheckConfig, BklinkcheckConfigV2, BklinkcheckConfigV3
from ..bk_log import BKLog
from .serial_helper import SerialHelper
from ..common.common import RESET_TYPE, LINKCHECK
from ..protocol.app import AppRebootProtocol
from ..protocol.bootrom.v2_0 import LinkCheckProtocol, Bl2LinkCheckProtocol, StayRomProtocol, GetChipIdProtocol, RebootProtocol, LinkCheckExtProtocol
class BaseController(object):
    allow_change_linkcheck_obj = True
    def _normalize_linkcheck_obj(self, linkcheck_obj):
        """入参只保留 BOOTROM / BL2 / MIXED（含义见 get_bus）；其余一律视为 BL1→BOOTROM。未传(None) 视为 MIXED（交替）。"""
        if linkcheck_obj is None:
            return LINKCHECK.MIXED
        else:
            if linkcheck_obj in [LINKCHECK.BOOTROM, LINKCHECK.BL2, LINKCHECK.MIXED]:
                return linkcheck_obj
            else:
                return LINKCHECK.BOOTROM
    def __init__(self, serial_instance: SerialHelper) -> None:
        self.serial_instance = serial_instance
    def do_reset(self, reset_type, baudrate):
        if reset_type == RESET_TYPE.DTR_RTS:
            self.serial_instance.ser.dtr = 0
            self.serial_instance.ser.rts = 1
            time.sleep(0.2)
            self.serial_instance.ser.rts = 0
        else:
            if reset_type == RESET_TYPE.CMD_ASCII:
                if baudrate != 115200:
                    self.serial_instance.reset(baudrate=baudrate)
                self.serial_instance.write_cmd(AppRebootProtocol().cmd(reboot_type='at'))
                if baudrate != 115200:
                    self.serial_instance.reset(baudrate=115200)
            else:
                if reset_type == RESET_TYPE.CMD_HEX:
                    if baudrate != 115200:
                        self.serial_instance.reset(baudrate=baudrate)
                    self.serial_instance.write_cmd(AppRebootProtocol().cmd(reboot_type='hex'))
                    if baudrate != 115200:
                        self.serial_instance.reset(baudrate=115200)
                else:
                    raise Exception('Not support {0}'.format(reset_type))
    def setStaticLinkcheckobj(self, link_check_obj):
        BaseController.link_check_obj = link_check_obj
    def do_link_check(self, linkcheck_obj, max_try_count=60, link_key=None, use_mixed_detection=False):
        cnt = max_try_count
        while cnt > 0:
            if linkcheck_obj == LINKCHECK.BOOTROM:
                lcp = LinkCheckProtocol()
                res, content = self.serial_instance.write_cmd_and_wait_response_without_drain(lcp.cmd(), lcp.expect_length, 0.0015)
                if res:
                    if use_mixed_detection:
                        res, isBl1 = lcp.response_check_mixed(content)
                        if res:
                            self.setStaticLinkcheckobj(LINKCHECK.BOOTROM if isBl1 else LINKCHECK.BL2)
                            return True
                    else:
                        if lcp.response_check(content):
                            self.setStaticLinkcheckobj(linkcheck_obj)
                            return True
            else:
                if linkcheck_obj == LINKCHECK.BL2:
                    bl2_lcp = Bl2LinkCheckProtocol()
                    res, content = self.serial_instance.write_cmd_and_wait_response_without_drain(bl2_lcp.cmd(), bl2_lcp.expect_length, 0.0015)
                    if res:
                        if use_mixed_detection:
                            res, isBl2 = bl2_lcp.response_check_mixed(content)
                            if res:
                                self.setStaticLinkcheckobj(LINKCHECK.BL2 if isBl2 else LINKCHECK.BOOTROM)
                                return True
                        else:
                            if bl2_lcp.response_check(content):
                                self.setStaticLinkcheckobj(linkcheck_obj)
                                return True
                else:
                    if linkcheck_obj == LINKCHECK.BOOTROM_PRE:
                        srp = StayRomProtocol()
                        res, content = self.serial_instance.write_cmd_and_wait_response_without_drain(srp.cmd(), srp.expect_length, 0.0015)
                        if res and srp.response_check(content):
                                return True
                    else:
                        if linkcheck_obj == LINKCHECK.BOOTROM_EXT:
                            lcp = LinkCheckExtProtocol()
                            res, content = self.serial_instance.write_cmd_and_wait_response_without_drain(lcp.cmd(link_key, 96), lcp.expect_length, 0.0015)
                            if res and lcp.response_check(content):
                                    return True
                        else:
                            raise Exception('Not support {0}'.format(linkcheck_obj))
            cnt -= 1
        return False
    def get_bus(self, reset_type=None, linkcheck_obj=None, reset_baudrate=115200, max_try_count=100, link_key=None, allow_change_linkcheck_obj=True):
        BaseController.allow_change_linkcheck_obj = allow_change_linkcheck_obj
        linkcheck_obj = self._normalize_linkcheck_obj(linkcheck_obj)
        if BklinkcheckConfig.use_version == 1:
            return self.get_bus_v1(reset_type=reset_type, linkcheck_obj=linkcheck_obj, reset_baudrate=reset_baudrate, max_try_count=max_try_count, link_key=link_key)
        else:
            if BklinkcheckConfig.use_version == 2:
                return self.get_bus_v2(reset_type=reset_type, linkcheck_obj=linkcheck_obj, reset_baudrate=reset_baudrate, max_try_count=max_try_count, link_key=link_key)
            else:
                if BklinkcheckConfig.use_version == 3:
                    return self.get_bus_v3(reset_type=reset_type, linkcheck_obj=linkcheck_obj, reset_baudrate=reset_baudrate, max_try_count=max_try_count, link_key=link_key)
    def get_bus_v2(self, reset_type=None, linkcheck_obj=None, reset_baudrate=115200, max_try_count=100, link_key=None):
        if linkcheck_obj is LINKCHECK.MIXED:
            log_info = 'Getting bus v2,alternating...'
        else:
            log_info = f'Getting bus v2,specified {linkcheck_obj}...'
        BKLog.i(log_info)
        self.do_reset(RESET_TYPE.DTR_RTS, baudrate=reset_baudrate)
        link_check_ret = False
        outter_cnt = 0
        while outter_cnt < BklinkcheckConfigV2.max_recycle_count:
            inner_cnt = 0
            while inner_cnt < BklinkcheckConfigV2.max_retry_interval:
                if linkcheck_obj is not LINKCHECK.MIXED:
                    link_check_ret = self.do_link_check(linkcheck_obj, link_key=link_key, max_try_count=1, use_mixed_detection=False)
                    if link_check_ret:
                        break
                else:
                    link_check_ret = self.do_link_check(LINKCHECK.BOOTROM, link_key=link_key, max_try_count=1, use_mixed_detection=BklinkcheckConfigV2.use_mixed_detection)
                    if link_check_ret:
                        break
                    else:
                        link_check_ret = self.do_link_check(LINKCHECK.BL2, link_key=link_key, max_try_count=1, use_mixed_detection=BklinkcheckConfigV2.use_mixed_detection)
                        if link_check_ret:
                            break
                inner_cnt += 1
            if link_check_ret:
                break
            if outter_cnt % 2 == 0:
                self.do_reset(RESET_TYPE.CMD_HEX, baudrate=reset_baudrate)
            else:
                self.do_reset(RESET_TYPE.CMD_ASCII, baudrate=reset_baudrate)
            outter_cnt += 1
        if link_check_ret:
            BKLog.i('Get bus success, type: {0}'.format(BaseController.link_check_obj))
            return (True, BaseController.link_check_obj)
        else:
            BKLog.i('Please reset the chip')
            BKLog.i('Waiting reset......')
            start_time = time.time()
            while time.time() - start_time < BklinkcheckConfigV2.max_wait_time:
                if linkcheck_obj is not LINKCHECK.MIXED:
                    link_check_ret = self.do_link_check(linkcheck_obj, link_key=link_key, max_try_count=1, use_mixed_detection=False)
                    if link_check_ret:
                        break
                else:
                    link_check_ret = self.do_link_check(LINKCHECK.BOOTROM, link_key=link_key, max_try_count=1, use_mixed_detection=BklinkcheckConfigV2.use_mixed_detection)
                    if link_check_ret:
                        break
                    else:
                        link_check_ret = self.do_link_check(LINKCHECK.BL2, link_key=link_key, max_try_count=1, use_mixed_detection=BklinkcheckConfigV2.use_mixed_detection)
                        if link_check_ret:
                            break
            if link_check_ret:
                BKLog.i('Get bus success, type: {0}'.format(BaseController.link_check_obj))
                return (True, BaseController.link_check_obj)
            else:
                BKLog.i('Get bus failed')
                return (False, None)
    def get_bus_v1(self, reset_type=None, linkcheck_obj=None, reset_baudrate=115200, max_try_count=100, link_key=None):
        """\n            reset_type 如果指定，则使用指定的类型，否则尝试所有类型\n            linkcheck_obj  如果指定，则先尝试指定的类型，再尝试其他的，否则按照默认顺序尝试\n        """
        res = False
        if reset_type is None:
            reset_type_try = [RESET_TYPE.DTR_RTS, RESET_TYPE.CMD_ASCII, RESET_TYPE.CMD_HEX, RESET_TYPE.MULTI]
        else:
            reset_type_try = [reset_type]
        link_check_try = [LINKCHECK.BOOTROM, LINKCHECK.BL2]
        if linkcheck_obj == LINKCHECK.BL2:
            link_check_try.reverse()
        for tmp_reset_type in reset_type_try:
            for tmp_link_check_type in link_check_try:
                if tmp_link_check_type == LINKCHECK.BOOTROM:
                    BKLog.w('Get bus v1...')
                else:
                    BKLog.w('Bl2 Get bus v1...')
                if tmp_reset_type == RESET_TYPE.MULTI:
                    self.do_reset(RESET_TYPE.DTR_RTS, baudrate=reset_baudrate)
                    for _ in range(max_try_count):
                        res = self.do_link_check(tmp_link_check_type, link_key=link_key)
                        if res:
                            BKLog.i('Get bus success')
                            return (True, tmp_link_check_type)
                        else:
                            self.do_reset(RESET_TYPE.CMD_ASCII, baudrate=reset_baudrate)
                else:
                    for _ in range(max_try_count):
                        self.do_reset(tmp_reset_type, baudrate=reset_baudrate)
                        res = self.do_link_check(tmp_link_check_type, link_key=link_key)
                        if res:
                            BKLog.i('Get bus success')
                            return (True, tmp_link_check_type)
        return (False, None)
    def line_break(self, timeout_sec=0.001) -> bool:
        try:
            self.serial_instance.write_cmd(b'\n')
            if timeout_sec > 0:
                ret = self.serial_instance.wait_for_cmd_response_free(10000, timeout_sec)
                return len(ret) > 0
            else:
                return True
        except Exception as e:
            BKLog.e(f'line break failed: {e}')
            return False
    def get_bus_v3(self, reset_type=None, linkcheck_obj=None, reset_baudrate=115200, max_try_count=100, link_key=None):
        if linkcheck_obj is not LINKCHECK.MIXED:
            log_info = f'Getting bus v3,specified {linkcheck_obj}...'
        else:
            log_info = 'Getting bus v3,alternating...'
        BKLog.i(log_info)
        link_check_ret = False
        outter_cnt = 0
        max_recycle_count = BklinkcheckConfigV3.max_recycle_count
        max_retry_interval = BklinkcheckConfigV3.max_retry_interval
        use_mixed_detection = BklinkcheckConfigV3.use_mixed_detection
        delay_time_before_reboot = BklinkcheckConfigV3.delay_time_before_reboot
        delay_time_after_reboot = BklinkcheckConfigV3.delay_time_after_reboot
        line_break_timeout_ms = BklinkcheckConfigV3.line_break_timeout_ms
        self.do_reset(RESET_TYPE.CMD_ASCII, baudrate=reset_baudrate)
        if delay_time_before_reboot > 0:
            time.sleep(delay_time_before_reboot / 1000)
        while outter_cnt < max_recycle_count:
            inner_cnt = 0
            while inner_cnt < max_retry_interval:
                if linkcheck_obj is not LINKCHECK.MIXED:
                    link_check_ret = self.do_link_check(linkcheck_obj, link_key=link_key, max_try_count=1, use_mixed_detection=False)
                    if link_check_ret:
                        break
                else:
                    link_check_ret = self.do_link_check(LINKCHECK.BOOTROM, link_key=link_key, max_try_count=1, use_mixed_detection=use_mixed_detection)
                    if link_check_ret:
                        break
                    else:
                        link_check_ret = self.do_link_check(LINKCHECK.BL2, link_key=link_key, max_try_count=1, use_mixed_detection=use_mixed_detection)
                        if link_check_ret:
                            break
                inner_cnt += 1
            if link_check_ret:
                break
            if self.line_break(line_break_timeout_ms / 1000):
                if delay_time_before_reboot > 0:
                    time.sleep(delay_time_before_reboot / 1000)
                self.do_reset(RESET_TYPE.CMD_ASCII, baudrate=reset_baudrate)
                if delay_time_after_reboot > 0:
                    time.sleep(delay_time_after_reboot / 1000)
            outter_cnt += 1
        if link_check_ret:
            BKLog.i('Get bus success, type: {0}'.format(BaseController.link_check_obj))
            return (True, BaseController.link_check_obj)
        else:
            BKLog.i('Get bus failed')
            return (False, None)
    def reconnect_bus(self, reset_type=None, linkcheck_obj=None, reset_baudrate=115200, max_retry_count=60, link_key=None):
        self.serial_instance.reset(115200)
        ret, linktype = self.get_bus(reset_type, linkcheck_obj, reset_baudrate, max_retry_count, link_key)
        if not ret:
            return False
        else:
            return True
    def get_chip_id(self):
        chip_id_reg_list = [1140916228, 8388608, 872480772]
        gcip = GetChipIdProtocol()
        self.serial_instance.drain()
        for tmp_reg in chip_id_reg_list:
            res, content = self.serial_instance.write_cmd_and_wait_response(gcip.cmd(tmp_reg), gcip.expect_length, 0.5)
            if res and gcip.response_check(content, tmp_reg):
                tmp_chip_id = gcip.get_chip_id(content)
                if tmp_chip_id > 0 and tmp_chip_id != 4294967295:
                    return tmp_chip_id
            time.sleep(0.001)
        BKLog.w('Cant get chip id')
        return
    def get_second_chip_id(self):
        reg_addr = 1140851184
        gcip = GetChipIdProtocol()
        self.serial_instance.drain()
        res, content = self.serial_instance.write_cmd_and_wait_response(gcip.cmd(reg_addr), gcip.expect_length, 0.5)
        if res and gcip.response_check(content, reg_addr):
            tmp_chip_id = gcip.get_chip_id(content)
            if tmp_chip_id > 0 and tmp_chip_id != 4294967295:
                return tmp_chip_id
        BKLog.w('Cant get second chip id')
        return
    def get_chip_id_retry(self, max_retry_count=5, link_key=None):
        cnt = max_retry_count
        delay = 0.15
        while cnt > 0:
            chipid = self.get_chip_id()
            if chipid is not None:
                return chipid
            else:
                if not self.reconnect_bus(RESET_TYPE.DTR_RTS, None, 115200, 30, link_key):
                    return
                else:
                    time.sleep(delay)
                    delay += 0.05
                    cnt -= 1
    def do_reboot(self):
        rb_protocol = RebootProtocol()
        self.serial_instance.write_cmd(rb_protocol.cmd())