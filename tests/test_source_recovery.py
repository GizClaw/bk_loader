import importlib.util
import dis
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

    def test_comparison_distinguishes_equal_values_with_different_constant_types(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recovered.py"
            bytecode = root / "original.pyc"
            for original_value, changed_value in [
                ("False", "0"), ("True", "1"), ("1.0", "1"), ("-0.0", "0.0"),
                ("(False,)", "(0,)"), ("b'word'", "'word'"),
            ]:
                with self.subTest(original=original_value, recovered=changed_value):
                    original = compile(f"def value():\n    return {original_value}\n", "vendor.py", "exec")
                    bytecode.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(original))
                    source.write_text(f"def value():\n    return {changed_value}\n")
                    checked = CHECKER(bytecode, source)
                    self.assertFalse(checked["runtimeFieldsMatch"])
                    self.assertFalse(checked["instructionControlFlowMatch"])

    def test_instruction_comparison_can_ignore_unreachable_return_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recovered.py"
            bytecode = root / "original.pyc"
            text = "def value():\n    return 42\n"
            original = compile(text, "vendor.py", "exec")
            child = next(item for item in original.co_consts if isinstance(item, type(original)))
            extra = bytes([dis.opmap["LOAD_CONST"], 0, dis.opmap["RETURN_VALUE"], 0])
            changed_child = child.replace(co_code=child.co_code + extra)
            original = original.replace(co_consts=tuple(
                changed_child if item is child else item for item in original.co_consts
            ))
            bytecode.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(original))
            source.write_text(text)
            checked = CHECKER(bytecode, source)
            self.assertFalse(checked["runtimeFieldsMatch"])
            self.assertTrue(checked["instructionControlFlowMatch"])

    def test_instruction_comparison_preserves_branch_results_defaults_and_docstrings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "recovered.py"
            bytecode = root / "original.pyc"
            cases = [
                ("def value(flag, left, right):\n    if flag:\n        return left\n    return right\n",
                 "def value(flag, left, right):\n    if flag:\n        return right\n    return left\n"),
                ("def value(number=1):\n    return number\n",
                 "def value(number=2):\n    return number\n"),
                ("def value():\n    'original documentation'\n    return 42\n",
                 "def value():\n    'changed documentation'\n    return 42\n"),
                ("def value():\n    raise ValueError('failed')\n",
                 "def value():\n    raise RuntimeError('failed')\n"),
            ]
            for original_text, changed_text in cases:
                with self.subTest(source=original_text):
                    original = compile(original_text, "vendor.py", "exec")
                    bytecode.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(original))
                    source.write_text(changed_text)
                    self.assertFalse(CHECKER(bytecode, source)["instructionControlFlowMatch"])


if __name__ == "__main__":
    unittest.main()
