import unittest
import logging

from bkutils.protocol.app.base_app_protocol import BaseAppProtocol
from bkutils.protocol.app.inject_key_finish_handshake_protocol import (
    InjectKeyFinishHandshakeProtocol,
)
from bkutils.protocol.app.inject_key_handshake_protocol import (
    InjectKeyHandshakeProtocol,
)
from bkutils.protocol.app.inject_key_set_secure_boot_protocol import (
    InjectKeySetSecureBootProtocol,
)
from bkutils.protocol.app.inject_key_start_protocol import InjectKeyStartProtocol
from bkutils.protocol.app.inject_key_write_aes_key_protocol import (
    InjectKeyWriteAesKeyProtocol,
)
from bkutils.protocol.app.inject_key_write_random_key_protocol import (
    InjectKeyWriteRandomKeyProtocol,
)
from bkutils.bk_log.log_utils import BKLog
from bkutils.common.bk_out_config import (
    BkOutConfig,
    BkReadFlashConfig,
    BkSetBaudrateConfig,
    BklinkcheckConfigV2,
)
from bkutils.common.ui_bridge_data import OutputData, MsgType, SerialInfo


class ConcreteProtocol(BaseAppProtocol):
    def cmd(self):
        raise NotImplementedError

    def expect_length(self):
        raise NotImplementedError

    def response_check(self):
        raise NotImplementedError


class InjectKeyProtocolTest(unittest.TestCase):
    def test_start_command(self):
        protocol = InjectKeyStartProtocol()
        self.assertEqual(protocol.cmd(), b'insert_key_start\r\n')
        self.assertEqual(protocol.expect_length, 0)

    def test_short_commands(self):
        self.assertEqual(
            InjectKeyHandshakeProtocol().cmd(),
            bytes([0x01, 0xe0, 0xfc, 0x01, 0x00]),
        )
        self.assertEqual(
            InjectKeyFinishHandshakeProtocol().cmd(),
            bytes([0x01, 0xe0, 0xfc, 0x01, 0x28]),
        )
        self.assertEqual(
            InjectKeySetSecureBootProtocol().cmd(True),
            bytes([0x01, 0xe0, 0xfc, 0x02, 0x29, 0x01]),
        )

    def test_short_response_validation(self):
        protocol = InjectKeyHandshakeProtocol()
        good = bytes([0x04, 0x0e, 0x05, 0x01, 0xe0, 0xfc, 0x00, 0x00])
        self.assertEqual(protocol.response_check(good), (True, None))
        self.assertEqual(protocol.response_check(good[:-1]), (False, None))

    def test_long_command_frame(self):
        protocol = ConcreteProtocol()
        self.assertEqual(
            protocol.command_generate_long(0x26, [0xaa, 0xbb]),
            bytes([0x01, 0xe0, 0xfc, 0xff, 0xf4, 0x03, 0x00, 0x26, 0xaa, 0xbb]),
        )

    def test_key_echo_validation(self):
        key = bytes(range(16))
        for protocol_type, command in (
            (InjectKeyWriteAesKeyProtocol, 0x26),
            (InjectKeyWriteRandomKeyProtocol, 0x27),
        ):
            protocol = protocol_type()
            response = bytes([
                0x04, 0x0e, 0xff, 0x01, 0xe0, 0xfc,
                len(key) + 2, 0x00, command, 0x00,
            ]) + key
            self.assertEqual(protocol.response_check(response, key), (True, key))
            self.assertEqual(protocol.response_check(response, b'wrong'), (False, None))

    def test_ui_json_contract(self):
        data = OutputData(MsgType.PROGRESS, 'writing', 25)
        self.assertEqual(
            data.to_json(),
            '{"msg_type": "progress", "msg_inner": "writing", "extra": "25"}',
        )
        ports = SerialInfo.list_to_json([SerialInfo('/dev/cu.test', 'test', 'USB')])
        self.assertIn('/dev/cu.test', ports)

    def test_packaged_runtime_configuration(self):
        if None not in BKLog.LOGGER_MAP:
            BKLog(logger_level=logging.CRITICAL, threading_id=None)
        BkOutConfig()
        self.assertEqual(BkSetBaudrateConfig.switch_delay_ms, 40)
        self.assertEqual(BkSetBaudrateConfig.wait_response_timeout_ms, 400)
        self.assertEqual(BkReadFlashConfig.retry_count, 20)
        self.assertEqual(BklinkcheckConfigV2.max_recycle_count, 3)


if __name__ == '__main__':
    unittest.main()
