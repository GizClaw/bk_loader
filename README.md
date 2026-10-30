# bk_loader

Beken's UART flashing utility, maintained as Python source by GizClaw.
The installed command is `bk_loader`. It runs on the host computer and talks
to a Beken chip over serial.

The source originates from Beken's v1.1.0.2 loader and the maintained source
tree in `h2vivi/firmware-devenv`. This repository includes the Python CLI,
protocol and chip-controller modules, flash database, runtime configuration,
and offline regression tests. It contains no PyInstaller executable,
bundled Python interpreter, Flutter binary or firmware image.

## Install

Python 3.10 or newer is required:

```sh
git clone https://github.com/GizClaw/bk_loader.git
cd bk_loader
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/bk_loader --help
.venv/bin/bk_loader --version
```

On Windows, use `.venv\Scripts\python.exe` and
`.venv\Scripts\bk_loader.exe`. The package installs the flash database and
configuration alongside the Python modules, so the command works from any
directory.

GizOS's `@gizclaw/gizos` toolbox installs a pinned commit into its shared
tool store and exports `BK_LOADER_BIN` plus the command's directory on `PATH`.
The toolbox owns that installation; no firmware worktree needs a separate
copy.

## Commands

```sh
bk_loader --help
bk_loader tools list_ports
bk_loader download --help
bk_loader erase --help
bk_loader read --help
```

`list_ports` enumerates serial ports. The `download`, `erase`, `read`, reset
and authorization commands operate on the explicitly selected device; review
their options and the board's recovery procedure before using them.
The CLI does not require Flutter.

For example, the existing BK7258 loader integration uses:

```sh
bk_loader download -p PORT -b 500000 --reset_type 0 --link_type 0 -r -i all-app.bin -s 0x0
```

The full upstream command reference is in [docs/upstream-cli.md](docs/upstream-cli.md).

## Source and compatibility

The maintained Python implementation is not a byte-for-byte reconstruction of
the vendor's newer macOS reference application. Ordinary BK7258 CLI
download/read/erase paths are present. The reference application's newer
secure-debug, key-injection orchestration and some newer chip-controller
changes have not been reconstructed.

The recovered packet-framing and UI bridge modules are tested independently;
their presence does not establish support for every newer reference-binary
operation. Original source lineage and recovery scope are recorded in
[docs/source-provenance.md](docs/source-provenance.md) and [SOURCE.json](SOURCE.json).
Package version `1.1.0.2.post1` identifies GizClaw's packaging revision; the
upstream CLI version banner remains `bk_loader.py,v1.1.0.2`.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

CI runs these offline tests on Linux, macOS and Windows after installing the
package. The tests exercise protocol framing, response validation, runtime
configuration and the installed CLI. They do not open a device or flash,
erase, reset or provision a chip. Vendor diagnostic scripts under
`bkutils/protocol/test` are retained as source and are outside the automatic
test suite.

## Notices

Original Beken copyright and licensing declarations are preserved. The source
entry declares BSD distribution while the historical setup metadata declares
MIT; [NOTICE.md](NOTICE.md) records both without replacing either declaration.
