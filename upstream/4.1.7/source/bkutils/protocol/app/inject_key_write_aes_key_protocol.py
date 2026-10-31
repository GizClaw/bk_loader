"""
Inject Key 写入 AES 密钥协议（与实测指令一致）

下发: 01 e0 fc ff f4 [len_lo] [len_hi] 26 [密钥数据]
回复: 04 0e ff 01 e0 fc f4 [len_lo] [len_hi] 26 [status] [密钥回显]
      （回复头多一字节 0xf4，命令码在索引 9，状态在 10，数据从 11 起；格式正确即视为成功，不校验状态与回显）
"""
from .base_app_protocol import BaseAppProtocol
RX_LONG_HEADER = [4, 14, 255, 1, 224, 252, 244]
RX_CMD_INDEX = 9
RX_STATUS_INDEX = 10
RX_PAYLOAD_INDEX = 11

def rx_expect_length_long_with_f4(payload_length: int) -> int:
    """长命令回复长度：04 0e ff 01 e0 fc f4(7) + len(2) + cmd(1) + status(1) + payload"""
    return len(RX_LONG_HEADER) + 2 + 1 + 1 + payload_length

class InjectKeyWriteAesKeyProtocol(BaseAppProtocol):
    """Inject Key 写入 AES 密钥协议（长命令）"""
    CMD_CODE = 38

    def cmd(self, key_data: bytes):
        """生成写入 AES 密钥命令。下发: 01 e0 fc ff f4 [len] 26 [key_data]"""
        return self.command_generate_long(self.CMD_CODE, list(key_data))

    def expect_length(self, key_length: int):
        """期望响应长度（与设备回复 04 0e ff 01 e0 fc f4 ... 一致）"""
        return rx_expect_length_long_with_f4(key_length)

    def response_check(self, response_content, expected_key_data: bytes):
        """只验证回复格式正确（头、长度、命令码），不做状态码与密钥回显校验。"""
        if len(response_content) < RX_PAYLOAD_INDEX:
            return (False, None)
        elif response_content[0:len(RX_LONG_HEADER)] != bytes(RX_LONG_HEADER):
            return (False, None)
        elif response_content[RX_CMD_INDEX] != self.CMD_CODE:
            return (False, None)
        return (True, None)
