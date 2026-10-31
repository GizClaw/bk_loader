# Decompiled with PyLingual (https://pylingual.io)
# Internal filename: 'bkutils/protocol/app/base_app_protocol.py'
# Bytecode version: 3.9.0beta5 (3425)
# Source timestamp: 1970-01-01 00:00:00 UTC (0)

from abc import ABC, abstractmethod
class BaseAppProtocol(ABC):
    def __init__(self):
        self.base_tx_type_and_opcode = [1, 224, 252]
        self.rx_header_and_event = [4, 14]
        self.long_cmd_marker = [255, 244]
    def command_generate(self, cmd, payload=[]):
        """生成短命令帧\n        格式: [0x01] [0xE0] [0xFC] [长度] [命令码] [数据...]\n        """
        command = bytearray()
        command.extend(self.base_tx_type_and_opcode)
        command.append(1 + len(payload))
        command.append(cmd)
        command.extend(payload)
        return command
    def command_generate_long(self, cmd, payload=[]):
        """生成长命令帧（带0xFF 0xF4标记）\n        格式: [0x01] [0xE0] [0xFC] [0xFF] [0xF4] [长度低] [长度高] [命令码] [数据...]\n        长度 = len(payload) + 1 (包含命令码)\n        """
        command = bytearray()
        command.extend(self.base_tx_type_and_opcode)
        command.extend(self.long_cmd_marker)
        total_length = 1 + len(payload)
        command.extend([total_length & 255, total_length >> 8 & 255])
        command.append(cmd)
        command.extend(payload)
        return command
    def rx_expect_length(self, payload_lenth):
        """计算短命令响应长度\n        响应格式: [0x04] [0x0E] [长度] [0x01] [0xE0] [0xFC] [命令码] [状态码] [数据...]\n        """
        return len(self.rx_header_and_event) + 1 + len(self.base_tx_type_and_opcode) + 1 + payload_lenth
    def rx_expect_length_long(self, payload_length):
        """计算长命令响应长度\n        响应格式: [0x04] [0x0E] [0xFF] [0x01] [0xE0] [0xFC] [长度低] [长度高] [命令码] [状态码] [数据...]\n        """
        return len(self.rx_header_and_event) + 1 + len(self.base_tx_type_and_opcode) + 2 + 1 + 1 + payload_length
    def get_response_status_code(self, response_content, is_long_cmd=False):
        """提取状态码\n        \n        Args:\n            response_content: 响应内容\n            is_long_cmd: 是否为长命令\n            \n        Returns:\n            int: 状态码，如果响应格式错误返回None\n        """
        if is_long_cmd:
            return response_content[9] if len(response_content) > 9 else None
        else:
            return response_content[7] if len(response_content) > 7 else None
    def get_response_payload_long(self, response_content):
        """提取长命令响应的数据部分\n        \n        Args:\n            response_content: 响应内容\n            \n        Returns:\n            bytes: 数据部分，如果响应格式错误返回空bytes\n        """
        return response_content[9:] if len(response_content) > 9 else b''
    @abstractmethod
    def cmd(self):
        return
    @abstractmethod
    def expect_length(self):
        return
    @abstractmethod
    def response_check(self):
        return