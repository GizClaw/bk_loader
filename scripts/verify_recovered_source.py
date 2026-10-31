"""Compare recovered source with a same-version Python code object without executing it."""

import argparse
import hashlib
import importlib.util
import json
import marshal
import sys
import types
from pathlib import Path


def runtime_fields(value):
    if isinstance(value, types.CodeType):
        return (
            "code", value.co_name, getattr(value, "co_qualname", value.co_name),
            value.co_argcount, value.co_posonlyargcount, value.co_kwonlyargcount,
            value.co_nlocals, value.co_stacksize, value.co_flags, value.co_code,
            tuple(runtime_fields(item) for item in value.co_consts),
            value.co_names, value.co_varnames, value.co_freevars, value.co_cellvars,
            getattr(value, "co_exceptiontable", b""),
        )
    if isinstance(value, tuple):
        return tuple(runtime_fields(item) for item in value)
    if isinstance(value, frozenset):
        return frozenset(runtime_fields(item) for item in value)
    return value


def verify(bytecode, source):
    data = Path(bytecode).read_bytes()
    if len(data) < 16 or data[:4] != importlib.util.MAGIC_NUMBER:
        raise ValueError("Use the Python version that produced the original bytecode")
    original = marshal.loads(data[16:])
    if not isinstance(original, types.CodeType):
        raise ValueError("The input does not contain a Python module code object")
    recovered = compile(Path(source).read_bytes(), str(source), "exec", dont_inherit=True, optimize=0)
    return {
        "schema": 1,
        "python": ".".join(str(part) for part in sys.version_info[:3]),
        "bytecodeSha256": hashlib.sha256(data).hexdigest(),
        "sourceSha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        "runtimeFieldsMatch": runtime_fields(original) == runtime_fields(recovered),
        "ignoredFields": ["filename", "first line", "line tables"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bytecode", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.bytecode, args.source)
    print(json.dumps(result, indent=2))
    return 0 if result["runtimeFieldsMatch"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
