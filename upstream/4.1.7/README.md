# Partial reconstruction of official BKFIL 4.1.7

This directory is an incomplete source recovery, not a buildable 4.1.7 SDK or
a replacement for this repository's maintained `src/` tree.

The recovered `source/bkutils/common/version.py` compiles under Python 3.9 to
the same runtime fields as the code object extracted from official package
`bk_loader_macos_arm64_4.1.7.261014250.pkg`. Filenames and line tables are
excluded; code, nested constants, flags, stack sizes, arguments and variable
tables are compared without executing the vendor code.

To repeat the check after extracting its `.pyc`:

```sh
python3.9 scripts/verify_recovered_source.py \
  --bytecode /path/to/extracted/bkutils/common/version.pyc \
  --source upstream/4.1.7/source/bkutils/common/version.py
```

The check rejects a different bytecode interpreter version and fails when
runtime fields differ. The current upstream manifest records the package
hash and recovery status. The other changed/missing modules still require
recovery and validation before the source release version can advance.
