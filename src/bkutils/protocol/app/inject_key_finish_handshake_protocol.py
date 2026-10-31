"""
Inject Key 完成握手协议
命令: 0x01 0xE0 0xFC 0x01 0x28
响应: 0x04 0x0E 0x04 0x01 0xE0 0xFC 0x28（7 字节，无末尾状态字节）
"""
from .base_app_protocol import BaseAppProtocol

class InjectKeyFinishHandshakeProtocol(BaseAppProtocol):
    """Inject Key 完成握手协议（短命令）"""
    CMD_CODE = 40

    def cmd(self):
        """生成完成握手命令
        
        Returns:
            bytes: 命令字节数组
        """
        return self.command_generate(self.CMD_CODE)

    @property
    def expect_length(self):
        """期望响应长度
        
        Returns:
            int: 响应长度（无状态字节，与 HCI 长度字段 0x04 一致）
        """
        return self.rx_expect_length(0)

    def response_check(self, response_content):
        """验证响应
        
        Args:
            response_content: 响应内容
            
        Returns:
            tuple: (成功标志, 响应数据)
        """
        if len(response_content) < self.expect_length:
            return (False, None)
        elif not response_content.startswith(bytes(self.rx_header_and_event)):
            return (False, None)
        elif response_content[3:6] != bytes(self.base_tx_type_and_opcode):
            return (False, None)
        elif response_content[6] != self.CMD_CODE:
            return (False, None)
        return (True, None)
