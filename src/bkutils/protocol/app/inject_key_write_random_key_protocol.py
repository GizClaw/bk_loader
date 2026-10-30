"""Long command used to inject a random key."""

from .inject_key_write_aes_key_protocol import InjectKeyWriteAesKeyProtocol


class InjectKeyWriteRandomKeyProtocol(InjectKeyWriteAesKeyProtocol):
    CMD_CODE = 0x27
