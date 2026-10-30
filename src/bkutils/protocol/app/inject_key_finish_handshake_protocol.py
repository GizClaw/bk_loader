"""Short command that completes the binary key-injection handshake."""

from .inject_key_handshake_protocol import InjectKeyHandshakeProtocol


class InjectKeyFinishHandshakeProtocol(InjectKeyHandshakeProtocol):
    CMD_CODE = 0x28
