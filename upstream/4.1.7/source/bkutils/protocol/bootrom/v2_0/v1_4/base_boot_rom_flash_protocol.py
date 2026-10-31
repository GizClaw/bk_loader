from abc import ABC, abstractmethod
from bkutils.common.bk_out_config import BkOutConfig
from .....bk_log import BKLog

class BaseBootRomFlashProtocol(ABC):

    def __init__(self):
        self.base_tx_header = [1, 224, 252, 255, 244]
        self.base_rx_header = [4, 14, 255, 1, 224, 252, 244]
        self.STATUS_INFO = [{'code': 0, 'desc': 'normal'}, {'code': 1, 'desc': 'FLASH_STATUS_BUSY'}, {'code': 2, 'desc': 'spi timeout'}, {'code': 3, 'desc': 'flash operate timeout'}, {'code': 4, 'desc': 'package payload lenth error'}, {'code': 5, 'desc': 'package lenth error'}, {'code': 6, 'desc': 'flash operate PARAM_ERROR'}, {'code': 7, 'desc': 'unkown cmd'}, {'code': 10, 'desc': 'permission denied'}]

    def command_generate(self, cmd, payload=[]):
        command = bytearray()
        command.extend(self.base_tx_header)
        command.extend([1 + len(payload) & 255, 1 + len(payload) >> 8 & 255])
        command.append(cmd)
        command.extend(payload)
        return command

    def rx_expect_length(self, payload_lenth):
        return len(self.base_rx_header) + 2 + 1 + 1 + payload_lenth

    def get_response_payload(self, response_content):
        return response_content[11:]

    def get_response_cmd(self, response_content):
        return response_content[9:10]

    def check_response_base_header(self, response_content):
        return response_content.startswith(bytes(self.base_rx_header))

    def check_response_status(self, response_content):
        if not BkOutConfig.check_response_code:
            return True
        status_code = response_content[10]
        if status_code == 0:
            return True
        for tmp_status in self.STATUS_INFO:
            if status_code == tmp_status['code']:
                BKLog.w('Check status error: err_code: {0}  err_msg: {1}'.format(status_code, tmp_status['desc']))
                return False
        BKLog.w('Check status error: err_code: {0}  err_msg: unknown'.format(status_code))
        return False

    def check_response_permission_denied(self, response_content):
        return len(response_content) >= 11 and response_content[10] == 10

    def check_response_length_seg(self, response_content):
        return response_content[7:9] == bytes([len(response_content) - 9 & 255, len(response_content) - 9 >> 8 & 255])

    def response_check(self, response_content):
        return self.check_response_base_header(response_content) and self.check_response_length_seg(response_content) and self.check_response_status(response_content)

    @abstractmethod
    def cmd(self):
        pass

    @abstractmethod
    def expect_length(self):
        pass
