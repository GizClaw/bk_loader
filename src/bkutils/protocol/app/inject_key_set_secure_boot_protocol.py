"""
Inject Key 设置 Secure Boot 协议（与底层一致）

下发: 0x01 0xE0 0xFC 0x02 0x29 [0x01/0x00]  （0x01=enable, 0x00=disable）
回复: 0x04 0x0E 0x05 0x01 0xE0 0xFC 0x29 [0x01/0x00]  （共 8 字节；只要回复格式正确即视为成功，不判最后一字节）
"""
from .base_app_protocol import BaseAppProtocol
RX_RESPONSE_LENGTH = 8
RX_LENGTH_BYTE = 5

class InjectKeySetSecureBootProtocol(BaseAppProtocol):
    """Inject Key 设置 Secure Boot 协议（短命令）"""
    CMD_CODE = 41

    def cmd(self, enable: bool=True):
        """生成设置 Secure Boot 命令

        下发: 01 e0 fc 02 29 [01/00]

        Args:
            enable: True=启用(0x01)，False=禁用(0x00)

        Returns:
            bytes: 命令字节数组
        """
        value = 1 if enable else 0
        return self.command_generate(self.CMD_CODE, [value])

    @property
    def expect_length(self):
        """期望响应长度 = 8 字节。"""
        return RX_RESPONSE_LENGTH

    def response_check(self, response_content):
        """验证响应格式正确即可，不做状态码判断。

        回复: 04 0e 05 01 e0 fc 29 [01/00]
        """
        if len(response_content) < RX_RESPONSE_LENGTH:
            return (False, None)
        elif response_content[0:2] != bytes(self.rx_header_and_event):
            return (False, None)
        elif response_content[2] != RX_LENGTH_BYTE:
            return (False, None)
        elif response_content[3:6] != bytes(self.base_tx_type_and_opcode):
            return (False, None)
        elif response_content[6] != self.CMD_CODE:
            return (False, None)
        return (True, None)
