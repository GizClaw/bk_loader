"""Compare recovered source with a same-version Python code object without executing it."""

import argparse
import dis
import hashlib
import importlib.util
import inspect
import json
import marshal
import struct
import sys
import types
from pathlib import Path
from collections import Counter, deque


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
        return ("tuple", tuple(runtime_fields(item) for item in value))
    if isinstance(value, frozenset):
        return ("frozenset", frozenset(runtime_fields(item) for item in value))
    if isinstance(value, float):
        return ("float", struct.pack("!d", value))
    if isinstance(value, complex):
        return ("complex", struct.pack("!dd", value.real, value.imag))
    return (type(value).__name__, value)


def instruction_control_flow_match(original, recovered):
    """Compare typed instructions and branch edges independently of byte offsets."""
    metadata = (
        "co_name", "co_argcount", "co_posonlyargcount", "co_kwonlyargcount",
        "co_flags", "co_varnames", "co_freevars", "co_cellvars",
    )
    if any(getattr(original, field) != getattr(recovered, field) for field in metadata):
        return False
    if runtime_fields(original) == runtime_fields(recovered):
        return True
    # Python 3.9 encodes its exception handlers with SETUP_* instructions.
    # Later versions need a separate exception-table comparison, not this mode.
    if getattr(original, "co_exceptiontable", b"") or getattr(recovered, "co_exceptiontable", b""):
        return False
    if original.co_flags & inspect.CO_NEWLOCALS:
        first = original.co_consts[0] if original.co_consts else None
        second = recovered.co_consts[0] if recovered.co_consts else None
        if runtime_fields(first) != runtime_fields(second):
            return False

    def children(code):
        counts = Counter()
        result = {}
        identities = {}
        for value in code.co_consts:
            if isinstance(value, types.CodeType):
                counts[value.co_name] += 1
                key = (value.co_name, counts[value.co_name])
                result[key] = value
                identities[id(value)] = key
        return result, identities

    left_children, left_ids = children(original)
    right_children, right_ids = children(recovered)
    if left_children.keys() != right_children.keys():
        return False
    for key in left_children:
        if not instruction_control_flow_match(left_children[key], right_children[key]):
            return False

    class Graph:
        def __init__(self, code, identities):
            instructions = list(dis.get_instructions(code))
            self.instructions = {item.offset: item for item in instructions}
            self.next = {
                item.offset: instructions[index + 1].offset if index + 1 < len(instructions) else None
                for index, item in enumerate(instructions)
            }
            self.identities = identities
            self.entry = self.resolve(instructions[0].offset if instructions else None)

        def resolve(self, offset):
            seen = set()
            while offset is not None:
                if offset in seen:
                    return ("spin", min(seen))
                seen.add(offset)
                item = self.instructions.get(offset)
                if item is None:
                    return ("invalid", offset)
                if item.opname in {"NOP", "EXTENDED_ARG"}:
                    offset = self.next[offset]
                elif item.opname in {
                    "JUMP_FORWARD", "JUMP_ABSOLUTE", "JUMP_BACKWARD",
                    "JUMP_BACKWARD_NO_INTERRUPT",
                }:
                    offset = item.argval
                else:
                    return offset
            return None

        def node(self, offset):
            if offset is None:
                return ("end",), {}
            if isinstance(offset, tuple):
                return (offset[0],), {"loop": offset} if offset[0] == "spin" else {}
            item = self.instructions[offset]
            jump = item.opcode in dis.hasjabs or item.opcode in dis.hasjrel
            if isinstance(item.argval, types.CodeType):
                argument = ("code", self.identities[id(item.argval)])
            else:
                argument = runtime_fields(item.argval) if item.arg is not None and not jump else None
            label = (item.opname, argument)
            if item.opname in {"RETURN_VALUE", "RETURN_CONST", "RAISE_VARARGS", "RERAISE"}:
                return label, {}
            edges = {"next": self.resolve(self.next[offset])}
            if jump:
                edges["jump"] = self.resolve(item.argval)
            return label, edges

    left = Graph(original, left_ids)
    right = Graph(recovered, right_ids)
    pending = deque([(left.entry, right.entry)])
    mapping = {}
    reverse = {}
    while pending:
        first, second = pending.popleft()
        if first in mapping:
            if mapping[first] != second:
                return False
            continue
        if second in reverse:
            return False
        mapping[first] = second
        reverse[second] = first
        first_label, first_edges = left.node(first)
        second_label, second_edges = right.node(second)
        if first_label != second_label or first_edges.keys() != second_edges.keys():
            return False
        pending.extend((first_edges[key], second_edges[key]) for key in sorted(first_edges))
    return True


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
        "instructionControlFlowMatch": instruction_control_flow_match(original, recovered),
        "ignoredFields": ["filename", "first line", "line tables"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bytecode", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--control-flow", action="store_true")
    args = parser.parse_args()
    result = verify(args.bytecode, args.source)
    print(json.dumps(result, indent=2))
    accepted = result["instructionControlFlowMatch"] if args.control_flow else result["runtimeFieldsMatch"]
    return 0 if accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
