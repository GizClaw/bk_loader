# Recovered official BKFIL 4.1.7 source

`source/` contains all 130 executable modules and four namespace packages
recovered from `bk_loader_macos_arm64_4.1.7.261014250.pkg`.
`config/` contains the four runtime YAML files from that package.

The executable SHA-256 is
`04d69c91aafaba5d02b5e71647cb2591c972e5942e91ae6769930731fe4c501e`.
The package SHA-256 and official download URL are recorded in
[`../4.1.7.json`](../4.1.7.json).

This snapshot preserves the recovered upstream implementation before the
packaging/import adaptations in `src/`. It contains source, not a bytecode
loader or a wrapper around the vendor executable.

## Repeat the complete check

Use Python 3.9 for bytecode verification. The maintained executable itself
runs on newer Python and does not need this recovery environment.
After downloading the pinned official package:

```sh
pkgutil --expand-full bk_loader_macos_arm64_4.1.7.261014250.pkg /tmp/bkfil-417
python3.9 -m venv .recovery-venv
.recovery-venv/bin/python -m pip install -r requirements-recovery.txt
.recovery-venv/bin/python scripts/verify_upstream.py \
  --executable /tmp/bkfil-417/Payload/bk_loader \
  --report /tmp/source-verification.json
```

The verifier first checks the executable's pinned SHA-256. It extracts the
PyInstaller entry script and `bkutils` code objects without executing them,
compiles every recovered source module and checks:

- arguments, locals, closure variables, defaults and docstrings;
- constant types and values, including bytes, booleans and signed float zero;
- every operation, conditional branch and explicit exception-handler edge;
- all nested functions, comprehensions and generators.

111 modules match the complete compiled runtime fields after excluding file
and line metadata. The remaining 19 match the instruction/control-flow graph.
Graph comparison also ignores constant/name table indexes, NOP/EXTENDED_ARG,
unconditional jump trampolines and unreachable return cleanup. It does not
ignore changed branches, conditions, calls, values or exception types.

[`source-verification.json`](source-verification.json) binds every module to
its source SHA-256 and original marshaled-code SHA-256. The script exits
unsuccessfully on a mismatched module or unexpected inventory.

## Recovery process

The recovery combined matching historical source, multiple decompilers and
manual disassembly-guided repairs. Tool revisions used:

| Tool | Revision |
| --- | --- |
| PyLingual | `11a1516d84a6c2aa71ec23fbd11e4b99dc8c4a86` |
| pycdc | `b4289760970dbc399684f1e155ec6d1ea1cc787e` |
| pycdc Python 3.9 work | `5db1488fb21d967604404b83c27a41d2c07ab1c7` |
| depyo.js | `2995e02cd13cbabd5a38aab5feb7154b678bfdd2` |

PyLingual ran locally with downloaded models; source was not uploaded to a
decompilation service. Decompiler output alone was not accepted. Repairs
included incorrectly nested loops, lost `finally` cleanup, incorrect guard
polarity, dropped starred arguments and incorrectly typed constants. Every
accepted complete module passed the comparison above.

The macOS product version comes from `config/version.yaml`:
`4.1.7+261014250` becomes CLI version `4.1.7.250`. The version module's fallback
constant remains `v1.1.0.5`. The snapshot preserves both values.
