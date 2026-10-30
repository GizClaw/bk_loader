"""Short command that starts the binary key-injection handshake."""

from .base_app_protocol import BaseAppProtocol


class InjectKeyHandshakeProtocol(BaseAppProtocol):
    CMD_CODE = 0x00

    def cmd(self):
        return self.command_generate(self.CMD_CODE)

    @property
    def expect_length(self):
        return self.rx_expect_length(1)

    def response_check(self, response_content):
        if len(response_content) < self.expect_length:
            return False, None
        if not response_content.startswith(bytes(self.rx_header_and_event)):
            return False, None
        if response_content[3:6] != bytes(self.base_tx_type_and_opcode):
            return False, None
        if response_content[6] != self.CMD_CODE:
            return False, None
        if self.get_response_status_code(response_content, is_long_cmd=False) != 0:
            return False, None
        return True, None
