"""Short command used to select the secure-boot setting during injection."""

from .inject_key_handshake_protocol import InjectKeyHandshakeProtocol


class InjectKeySetSecureBootProtocol(InjectKeyHandshakeProtocol):
    CMD_CODE = 0x29

    def cmd(self, enable):
        return self.command_generate(self.CMD_CODE, [1 if enable else 0])
