import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from bk_loader import cli
from bkutils.flash_adapter.flash_config import FlashConfig


class CliTest(unittest.TestCase):
    def test_help_and_version_do_not_open_a_serial_port(self):
        with patch("serial.Serial") as serial:
            for args in [["--help"], ["--version"], ["download", "--help"], ["erase", "--help"]]:
                result = CliRunner().invoke(cli, args)
                self.assertEqual(result.exit_code, 0, result.output)
            serial.assert_not_called()

    def test_flash_database_is_packaged_with_the_modules(self):
        config = FlashConfig()
        self.assertTrue(Path(config.cfg_file_path).is_file())
        self.assertTrue(config.cfg_info)

    def test_installed_modules_and_configuration_work_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-c",
                 "import json; from bkutils.flash_adapter.flash_config import FlashConfig; "
                 "from bk_loader import cli; "
                 "print(json.dumps({'entries': len(FlashConfig().cfg_info)})); "
                 "cli(['--version'], prog_name='bk_loader')"],
                cwd=directory, capture_output=True, text=True, check=True,
            )
            self.assertGreater(json.loads(result.stdout.splitlines()[0])["entries"], 0)
            self.assertIn("bk_loader.py,v1.1.0.2", result.stdout)


if __name__ == "__main__":
    unittest.main()
