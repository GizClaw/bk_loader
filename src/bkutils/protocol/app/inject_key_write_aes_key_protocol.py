"""Long command used to inject an AES key."""

from .base_app_protocol import BaseAppProtocol


class InjectKeyWriteAesKeyProtocol(BaseAppProtocol):
    CMD_CODE = 0x26

    def cmd(self, key_data: bytes):
        return self.command_generate_long(self.CMD_CODE, list(key_data))

    def expect_length(self, key_length: int):
        return self.rx_expect_length_long(key_length)

    def response_check(self, response_content, expected_key_data: bytes):
        if len(response_content) < 10:
            return False, None
        if response_content[0:2] != bytes(self.rx_header_and_event):
            return False, None
        if response_content[2] != 0xff:
            return False, None
        if response_content[3:6] != bytes(self.base_tx_type_and_opcode):
            return False, None
        if len(response_content) <= 8 or response_content[8] != self.CMD_CODE:
            return False, None
        if self.get_response_status_code(response_content, is_long_cmd=True) != 0:
            return False, None
        echo_data = self.get_response_payload_long(response_content)
        if echo_data != expected_key_data:
            return False, None
        return True, echo_data
