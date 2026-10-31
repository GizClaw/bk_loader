"""
Inject Key 启动协议
发送 ASCII 命令: "insert_key_start\r
"
这是一个特殊的 ASCII 命令，不遵循标准的二进制协议格式
"""

class InjectKeyStartProtocol:
    """Inject Key 启动协议（ASCII命令）"""
    START_CMD = b'insert_key_start\r\n\r\n'

    def cmd(self):
        """生成启动命令
        
        Returns:
            bytes: ASCII命令字符串
        """
        return self.START_CMD

    @property
    def expect_length(self):
        """ASCII命令不需要等待响应，返回0"""
        return 0

    def response_check(self, response_content):
        """ASCII命令不需要验证响应
        
        Returns:
            tuple: (True, None) 表示成功
        """
        return (True, None)
