# bk_loader

Beken's UART flashing utility, maintained as Python source by GizClaw.
The command runs on the host computer and talks to a Beken chip over serial.

This source release is recovered from official **BKFIL 4.1.7**, build
**4.1.7.261014250**. It replaces the older `1.1.0.2.post2` implementation.
The package version is `4.1.7`; `bk_loader --version` reports
`bk_loader, version 4.1.7.250`, just like the official macOS CLI.

All **130 executable Python modules** and four namespace packages have been
recovered, including the complete CLI, batch/single-port download services,
secure-debug and key-injection services, protocols and chip controllers.
Recompilation under Python 3.9 matches the vendor's runtime fields for 111
modules. All 130 match the typed instructions and control-flow graph, allowing
only documented compiler-layout differences. The checked report records every
module's source and original-bytecode hash.

See [source provenance](docs/source-provenance.md),
[the recovery snapshot and verification instructions](upstream/4.1.7/README.md)
and [the official package audit](docs/upstream-4.1.7.md).
The repository contains editable Python and YAML resources. It does not
install or execute the vendor `.pkg` to build GizClaw releases.

## Install a Release executable

Release builds produce these standalone archives:

| Host | Archive suffix | Command inside |
| --- | --- | --- |
| macOS Apple Silicon | `darwin-arm64.tar.gz` | `bin/bk_loader` |
| macOS Intel | `darwin-x64.tar.gz` | `bin/bk_loader` |
| Linux x86_64 | `linux-x64.tar.gz` | `bin/bk_loader` |
| Linux arm64 | `linux-arm64.tar.gz` | `bin/bk_loader` |
| Windows x86_64 | `win32-x64.zip` | `bin/bk_loader.exe` |

Archive names are `bk-loader-<version>-<host>.<format>`. Download an available
version from [Releases](https://github.com/GizClaw/bk_loader/releases), verify
it against `SHA256SUMS`, extract it, and add its `bin` directory to PATH.
No Python or pip installation is needed to run these executables. Linux builds
use Ubuntu 22.04 (glibc 2.35); older glibc is unsupported.

The release's `index.json` records the source commit, host, archive size and
SHA-256, executable SHA-256 and offline self-test results. Publication requires
successful native builds and tests on all five platforms. Each build runs
outside the checkout with host Python removed from PATH.

```sh
bk_loader --version
bk_loader tools selftest
```

`tools selftest` returns JSON describing the package/upstream versions, bundled
flash database, AES check and P-256 signing check. It does not access a device.

GizOS installs BK Loader in its shared tool directory and exports
`BK_LOADER_BIN` and its directory on PATH. Firmware worktrees share that
installation. Its current catalog uses the official 4.1.7 runtime; it can
switch to these source-built archives after their release checksums are
published.

## Install from source

Python 3.10 or newer is required to run the maintained package:

```sh
git clone https://github.com/GizClaw/bk_loader.git
cd bk_loader
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/bk_loader --version
.venv/bin/bk_loader tools selftest
```

On Windows, use `.venv\Scripts\python.exe` and
`.venv\Scripts\bk_loader.exe`. The wheel installs configuration and the flash
database alongside the modules, so it works from another directory.
Runtime dependencies include Click, PyYAML, PySerial, PyCryptodome and
cryptography. Decompilers and their models are not runtime dependencies.

## Commands

```sh
bk_loader --help
bk_loader tools list_ports
bk_loader download --help
bk_loader erase --help
bk_loader read --help
bk_loader secure --help
bk_loader inject_key --help
```

The CLI includes the upstream batch workflow and its stdin/stdout bridge for
an optional Flutter frontend. Flutter is not required by the CLI.
For example, the BK7258 firmware integration uses:

```sh
bk_loader download -p PORT -b 500000 --reset_type 0 --link_type 0 -r -i all-app.bin -s 0x0
```

Download, erase, reset and provisioning commands operate on the selected
physical device. Source recovery and offline tests do not establish
physical-device acceptance for every chip or security operation.
The previous CLI reference is retained in
[docs/upstream-cli.md](docs/upstream-cli.md); use the executable's help for the
current 4.1.7 options and defaults.

For secure debug, `--key_path` selects the public PEM file. Keep the matching
private key in the same directory as `ec_256_privkey.pem`. No private keys are
bundled. Public-key verification does not require a private key.

## Tests and builds

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip install -r requirements-build.txt .
.venv/bin/python scripts/build_binary.py
```

Tests cover recovery-report hashes, importability, framing, runtime data,
multi-entry OTP/eFuse processing, failed download/read/erase cleanup,
key-injection success/failure and a real P-256 signature in a mocked
secure-debug exchange. Serial transports are replaced with test doubles;
no connected device is used.

The native executable self-test checks both crypto libraries and the bundled
resources without host Python. CI also checks CLI help for download, read,
erase, secure debug and key injection.

Maintainers publish an immutable version by tagging its source commit
`v<project-version>`. The Release workflow rebuilds and verifies the complete
matrix before publishing archives, `index.json` and `SHA256SUMS`.

## Notices

The Beken copyright and historical BSD/MIT declarations are retained in
[NOTICE.md](NOTICE.md). GizClaw's packaging and maintenance code uses the
BSD 3-Clause terms in `LICENSE`. Recovery reconstructs executable behavior;
it does not restore original comments or assert a new license for Beken code.
