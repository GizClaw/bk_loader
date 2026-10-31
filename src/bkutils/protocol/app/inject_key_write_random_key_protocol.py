"""
Inject Key 写入 Random 密钥协议
命令: 长命令格式，命令码 0x27
回复: 与写 AES(0x26) 同帧结构 — 04 0e ff 01 e0 fc f4 [len_lo] [len_hi] 27 [status] [密钥回显]
"""
from .base_app_protocol import BaseAppProtocol
from .inject_key_write_aes_key_protocol import RX_LONG_HEADER, RX_CMD_INDEX, RX_STATUS_INDEX, RX_PAYLOAD_INDEX, rx_expect_length_long_with_f4

class InjectKeyWriteRandomKeyProtocol(BaseAppProtocol):
    """Inject Key 写入 Random 密钥协议（长命令）"""
    CMD_CODE = 39

    def cmd(self, key_data: bytes):
        """生成写入 Random 密钥命令

        Args:
            key_data: Random密钥数据（bytes）

        Returns:
            bytes: 命令字节数组
        """
        return self.command_generate_long(self.CMD_CODE, list(key_data))

    def expect_length(self, key_length: int):
        """期望响应长度（与设备 04 0e ff 01 e0 fc f4 ... 实测一致）"""
        return rx_expect_length_long_with_f4(key_length)

    def response_check(self, response_content, expected_key_data: bytes):
        """验证响应并检查密钥回显（回显从索引 11 起，与 0x26 回复一致）"""
        n = len(expected_key_data)
        need_len = RX_PAYLOAD_INDEX + n
        if len(response_content) < need_len:
            return (False, None)
        elif response_content[0:len(RX_LONG_HEADER)] != bytes(RX_LONG_HEADER):
            return (False, None)
        elif response_content[RX_CMD_INDEX] != self.CMD_CODE:
            return (False, None)
        elif response_content[RX_STATUS_INDEX] != 0:
            return (False, None)
        echo_data = response_content[RX_PAYLOAD_INDEX:RX_PAYLOAD_INDEX + n]
        if echo_data != expected_key_data:
            return (False, None)
        return (True, echo_data)
