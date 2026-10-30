from abc import ABC, abstractmethod


class BaseAppProtocol(ABC):

    def __init__(self):
        self.base_tx_type_and_opcode = [0x01, 0xe0, 0xfc]
        self.rx_header_and_event = [0x04, 0x0e]
        self.long_cmd_marker = [0xff, 0xf4]

    def command_generate(self, cmd, payload=[]):
        command = bytearray()
        command.extend(self.base_tx_type_and_opcode)
        command.append(1 + len(payload))
        command.append(cmd)
        command.extend(payload)
        return command

    def command_generate_long(self, cmd, payload=[]):
        command = bytearray()
        command.extend(self.base_tx_type_and_opcode)
        command.extend(self.long_cmd_marker)
        total_length = 1 + len(payload)
        command.extend([total_length & 0xff, (total_length >> 8) & 0xff])
        command.append(cmd)
        command.extend(payload)
        return command
    
    def rx_expect_length(self, payload_lenth):
        return len(self.rx_header_and_event) + 1 + len(self.base_tx_type_and_opcode) + 1 + payload_lenth

    def rx_expect_length_long(self, payload_length):
        return (
            len(self.rx_header_and_event)
            + 1
            + len(self.base_tx_type_and_opcode)
            + 2
            + 1
            + 1
            + payload_length
        )

    def get_response_status_code(self, response_content, is_long_cmd=False):
        if is_long_cmd:
            # Long responses carry the command at byte 8 and status at byte 9.
            return response_content[9] if len(response_content) > 9 else None
        return response_content[7] if len(response_content) > 7 else None

    def get_response_payload_long(self, response_content):
        return response_content[10:] if len(response_content) > 10 else b''
    
    @abstractmethod
    def cmd(self):
        pass

    @abstractmethod
    def expect_length(self):
        pass

    @abstractmethod
    def response_check(self):
        pass
