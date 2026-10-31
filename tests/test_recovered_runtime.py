import hashlib
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

from bkutils.action_service.download import Download
from bkutils.action_service.dump import Dump
from bkutils.action_service.erase import Erase
from bkutils.action_service.inject_key import InjectKey
from bkutils.action_service.secure import SecDebug
from bkutils.action_service.single_port_download import SinglePortDownload
from bkutils.chip_controller.chip_set.bk7259 import BK7259
from bkutils.common.common import DownloadInfo, EraseInfo, ReadInfo
from bkutils.secure_debug.secure_debug import SD


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "upstream/4.1.7"


class RecoveredRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch("serial.Serial", side_effect=AssertionError("Unexpected UART access")).start()
        patch("bkutils.bk_log.BKLog.ifclose", True).start()

    def test_complete_recovery_report_binds_every_source_module_and_import(self):
        report = json.loads((SNAPSHOT / "source-verification.json").read_text())
        self.assertTrue(report["complete"])
        self.assertEqual(report["codeModules"], 130)
        self.assertEqual(report["instructionControlFlowMatches"], 130)
        for module in report["modules"]:
            with self.subTest(module=module["module"]):
                source = SNAPSHOT / "source" / module["source"]
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), module["sourceSha256"])
                self.assertTrue(module["instructionControlFlowMatch"])
                importlib.import_module(module["module"])
        for namespace in report["namespacePackages"]:
            self.assertEqual((SNAPSHOT / "source" / namespace).read_bytes(), b"")

    def test_download_post_actions_process_every_efuse_and_otp_entry(self):
        for service_type in (Download, SinglePortDownload):
            with self.subTest(service=service_type.__name__):
                service = service_type.__new__(service_type)
                service.task_flag = Mock()
                service._log = Mock()
                chip = Mock(_flash_mid=0)
                chip.write_efuse.return_value = (True, None)
                chip.write_chip_otp.return_value = (True, None)
                info = DownloadInfo(
                    efuse_info="0x1-0x10,0x2-0x20",
                    otp_info="aabb@0x1000-2,ccdd@0x2000-2",
                )
                self.assertEqual(service.download_common_post_action(info, chip, Mock(), 90), 95)
                self.assertEqual(chip.write_efuse.call_args_list, [call(1, 16), call(2, 32)])
                self.assertEqual(chip.write_chip_otp.call_args_list, [
                    call(0x1000, "aabb", False), call(0x2000, "ccdd", False),
                ])

    def test_failed_bus_stops_download_read_erase_and_closes_transport(self):
        for service_type, method, info in [
            (Download, "download_base_task", DownloadInfo()),
            (Dump, "read_task", ReadInfo()),
            (Erase, "erase_task", EraseInfo()),
        ]:
            with self.subTest(service=service_type.__name__):
                transport = Mock(ser=SimpleNamespace(name="offline"))
                module = importlib.import_module(service_type.__module__)
                with patch("bkutils.action_service.action_base.SerialHelper", return_value=transport), \
                        patch.object(module, "BaseController") as controller:
                    controller.return_value.get_bus.return_value = (False, None)
                    service = service_type(reboot_after_donwload=False)
                    service._init_log_level = Mock()
                    service._get_chip_set = Mock()
                    self.assertFalse(getattr(service, method)(info))
                    service._get_chip_set.assert_not_called()
                    transport.disconnect.assert_called_once_with()

    def test_security_data_is_processed_when_user_operations_are_disabled(self):
        module = importlib.import_module(BK7259.__module__)
        data = SimpleNamespace(
            status="true", name="aes_key", start_addr="0x1000", byte_len="16",
            permission="rw", reverse=False, big_endian=False,
            is_reverse_specified=lambda: False, is_big_endian_specified=lambda: False,
        )
        info = SimpleNamespace(
            user_operate_enable=False, security_data_enable=True,
            security_data_list=[data], efuse_enable=False, security_ctrl_enable=False,
        )
        with patch.object(module, "BK7259_Security") as security:
            security.return_value._write_otp_info.return_value = (True, None)
            security.return_value._write_otp_permission.return_value = (True, None)
            self.assertEqual(BK7259()._work_as_safe_json(info), (True, None))
            self.assertTrue(data.reverse)
            self.assertTrue(data.big_endian)
            security.return_value._write_otp_info.assert_called_once_with(data)
            security.return_value._write_otp_permission.assert_called_once_with("0x1000", "16", "rw")

    def test_inject_key_parses_both_files_and_cleans_up_success_and_failure(self):
        module = importlib.import_module(InjectKey.__module__)
        with tempfile.TemporaryDirectory() as directory:
            aes = Path(directory) / "aes.json"
            random = Path(directory) / "random.json"
            aes.write_text('# Test fixture\n{"AES_KEY": "000102030405060708090a0b0c0d0e0f"}')
            random.write_text('{"RANDOM_KEY": ["sample", "random"]}')
            for handshake_ok in (True, False):
                with self.subTest(handshake=handshake_ok), \
                        patch("bkutils.action_service.action_base.SerialHelper") as transport, \
                        patch.object(module, "ui_bridge"):
                    service = InjectKey()
                    service._init_log_level = Mock()
                    service._start_inject_key_mode = Mock(return_value=True)
                    service._handshake = Mock(return_value=handshake_ok)
                    service._set_secure_boot = Mock(return_value=True)
                    service._write_aes_key = Mock(return_value=True)
                    service._write_random_key = Mock(return_value=True)
                    service._finish_handshake = Mock(return_value=True)
                    self.assertEqual(service.inject_key_task(str(aes), str(random)), handshake_ok)
                    transport.return_value.disconnect.assert_called_once_with()
                    if handshake_ok:
                        service._write_aes_key.assert_called_once_with(bytes(range(16)), max_retry=5)
                        service._write_random_key.assert_called_once_with(b"samplerandom", max_retry=5)
                    else:
                        service._write_aes_key.assert_not_called()
                        service._set_secure_boot.assert_not_called()

    def test_secure_debug_retries_challenge_and_signs_real_p256_request(self):
        module = importlib.import_module(SecDebug.__module__)
        private = ec.generate_private_key(ec.SECP256R1())
        public = private.public_key()
        challenge = bytes(range(32))
        with tempfile.TemporaryDirectory() as directory:
            private_path = Path(directory) / "ec_256_privkey.pem"
            public_path = Path(directory) / "ec_256_pubkey.pem"
            private_path.write_bytes(private.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ))
            public_path.write_bytes(public.public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo,
            ))
            public_data = public.public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint,
            )
            with patch("bkutils.action_service.action_base.SerialHelper") as transport, \
                    patch.object(module, "BaseController") as controller, \
                    patch.object(module, "get_chip_set_with_chip_id") as chip, \
                    patch.object(module.time, "sleep"):
                controller.return_value.get_bus.return_value = (True, None)
                service = SecDebug(chipid=0x7258, reboot_after_donwload=False)
                service._init_log_level = Mock()
                service.enter_secure_debug = Mock(side_effect=[(False, None), (True, challenge)])
                service.request_secure_debug = Mock()
                info = SimpleNamespace(key_path=str(public_path), work_baudrate=2000000)
                self.assertTrue(service.secure_debug_task(info))
                self.assertEqual(service.enter_secure_debug.call_count, 2)
                service.enter_secure_debug.assert_called_with(public_data)
                mode, request = service.request_secure_debug.call_args.args
                self.assertEqual(mode, 0)
                self.assertEqual(request[:2], b"\x00\x40")
                r, s = int.from_bytes(request[2:34], "big"), int.from_bytes(request[34:], "big")
                public.verify(encode_dss_signature(r, s), b"\0" + challenge, ec.ECDSA(hashes.SHA256()))
                chip.return_value.update_serial_instance.assert_called_once_with(transport.return_value)
                transport.return_value.disconnect.assert_called_once_with()
            signature = private.sign(challenge, ec.ECDSA(hashes.SHA256()))
            private_path.unlink()
            self.assertTrue(SD(str(public_path)).verify_hash(str(public_path), challenge, signature))


if __name__ == "__main__":
    unittest.main()
