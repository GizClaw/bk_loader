import importlib.util
import marshal
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
CHECKER = runpy.run_path(str(ROOT / "scripts/verify_recovered_source.py"))["verify"]
SOURCE = ROOT / "upstream/4.1.7/source/bkutils/common/version.py"


class SourceRecoveryTest(unittest.TestCase):
    def test_version_comes_from_product_configuration_with_a_backend_fallback(self):
        namespace = runpy.run_path(str(SOURCE))
        version = namespace["get_tool_version"]
        for data, expected in [
            ("version: 4.1.7+261014250\n", "4.1.7.250"),
            ("version: 4.0.2+260129055\n", "4.0.2.55"),
            ("version: null\n", "v1.1.0.5"),
            ("version: malformed\n", "v1.1.0.5"),
            ("{}\n", "v1.1.0.5"),
        ]:
            with self.subTest(data=data), patch("builtins.open", mock_open(read_data=data)):
                self.assertEqual(version(), expected)
        with patch("builtins.open", side_effect=FileNotFoundError):
            self.assertEqual(version(), "v1.1.0.5")

    def test_comparison_ignores_locations_and_detects_changed_nested_logic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recovered.py"
            bytecode = root / "original.pyc"
            original = compile("def value():\n    return 42\n", "vendor.py", "exec")
            bytecode.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(original))
            source.write_text("# Recovered source\n\ndef value():\n    return 42\n")
            self.assertTrue(CHECKER(bytecode, source)["runtimeFieldsMatch"])
            source.write_text("def value():\n    return 43\n")
            self.assertFalse(CHECKER(bytecode, source)["runtimeFieldsMatch"])
            bytecode.write_bytes(b"nope" + bytecode.read_bytes()[4:])
            with self.assertRaisesRegex(ValueError, "Python version"):
                CHECKER(bytecode, source)


if __name__ == "__main__":
    unittest.main()
