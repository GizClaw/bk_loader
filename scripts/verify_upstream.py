"""Verify every recovered module against the pinned official macOS executable."""

import argparse
import hashlib
import importlib.util
import json
import marshal
import sys
from pathlib import Path

from verify_recovered_source import instruction_control_flow_match, runtime_fields


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "upstream" / "4.1.7"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(executable, source_root):
    # marshal code objects are version-specific. Nothing extracted is executed.
    if sys.version_info[:2] != (3, 9):
        raise ValueError("Use Python 3.9 to read the official Python 3.9 bytecode")
    from PyInstaller.archive.readers import CArchiveReader

    upstream = json.loads((ROOT / "upstream/4.1.7.json").read_text())
    expected = upstream["platforms"]["darwin-arm64"]["executableSha256"]
    actual = digest(executable.read_bytes())
    if actual != expected:
        raise ValueError(f"Official executable SHA-256 mismatch: {actual}")
    archive = CArchiveReader(str(executable))
    pyz = archive.open_embedded_archive("PYZ.pyz")
    modules = []
    namespaces = []
    entries = sorted(
        (name, item[0]) for name, item in pyz.toc.items()
        if name == "bkutils" or name.startswith("bkutils.")
    ) + [("bk_loader", 0)]
    for name, kind in entries:
        relative = name.replace(".", "/") + ("/__init__.py" if kind in (1, 3) else ".py")
        path = source_root / relative
        text = path.read_bytes()
        if kind == 3:
            if text.strip():
                raise ValueError(f"Expected empty namespace package: {relative}")
            namespaces.append(relative)
            continue
        raw = archive.extract(name) if name == "bk_loader" else pyz.extract(name, raw=True)
        original = marshal.loads(raw)
        recovered = compile(text, str(path), "exec", dont_inherit=True, optimize=0)
        modules.append({
            "module": name,
            "source": relative,
            "originalMarshalSha256": digest(raw),
            "sourceSha256": digest(text),
            "runtimeFieldsMatch": runtime_fields(original) == runtime_fields(recovered),
            "instructionControlFlowMatch": instruction_control_flow_match(original, recovered),
        })
    if len(modules) != 130 or len(namespaces) != 4:
        raise ValueError("Unexpected upstream module inventory")
    return {
        "schema": 1,
        "python": ".".join(map(str, sys.version_info[:3])),
        "bytecodeMagic": importlib.util.MAGIC_NUMBER.hex(),
        "productVersion": upstream["productVersion"],
        "buildVersion": upstream["buildVersion"],
        "executableSha256": actual,
        "codeModules": len(modules),
        "namespacePackages": namespaces,
        "runtimeFieldsMatches": sum(item["runtimeFieldsMatch"] for item in modules),
        "instructionControlFlowMatches": sum(item["instructionControlFlowMatch"] for item in modules),
        "complete": all(item["instructionControlFlowMatch"] for item in modules),
        "comparison": {
            "exactModeIgnores": ["filenames", "first lines", "line tables"],
            "controlFlowModeAlsoIgnores": [
                "constant/name table indexes", "NOP and EXTENDED_ARG",
                "unconditional jump trampolines", "unreachable return cleanup",
            ],
            "preserves": [
                "typed constants", "arguments and locals", "defaults and docstrings",
                "operations", "branch and handler edges", "nested code objects",
            ],
        },
        "modules": modules,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=SNAPSHOT / "source")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.executable, args.source_root)
    text = json.dumps(result, indent=2) + "\n"
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "modules"}, indent=2))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
