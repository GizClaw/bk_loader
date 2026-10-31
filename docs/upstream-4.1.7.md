# Official BKFIL 4.1.7 audit

Verified on October 31, 2026 against Beken's own download directory, version
manifest, signed macOS packages and native CLI output. This audit records
official runtime availability and the completed recovery of its Python source.
The maintained source package is now `4.1.7`.

## Version identifiers

| Identifier | Meaning |
| --- | --- |
| `4.1.7` | Official BKFIL product release |
| `4.1.7.261014250` | Official full build and package version |
| `4.1.7.250` | CLI version printed by both macOS executables |
| `4.1.7+261014250` | Bundled macOS `config/version.yaml` version |
| `v1.1.0.5` | Fallback constant in the newer version module; product configuration normally overrides it |
| `1.1.0.2.post2` | Previous GizClaw source maintenance/package revision |
| `4.1.7` (package) | Current GizClaw package built from recovered 4.1.7 source |
| `v1.1.0.2` | Version constant in that imported older Python source |

The official `version.json` lists product release time
`2026-10-14T10:30:00+08:00`. The CLI download directory lists the 4.1.7 files
as modified on October 15, 2026. Neither date establishes an official product
release corresponding to the old `v1.1.0.2` backend constant.

## Official distributions

The following packages were downloaded from Beken's own directory. Archive
and executable SHA-256 values are in [the manifest](../upstream/4.1.7.json).

| Host | Distribution | Inspection |
| --- | --- | --- |
| macOS arm64 | `.pkg`, 14,463,822 bytes | Apple-trusted Beken installer signature and notarization; native `--version` and help passed |
| macOS x86_64 | `.pkg`, 15,664,760 bytes | CLI `--version` passed on this Mac through its existing x86_64 support |
| Linux x86_64 | `.zip`, 12,520,749 bytes | Nuitka standalone executable; `--version` and `download --help` passed in an x86_64 Linux container |
| Windows x86_64 | `.zip`, 9,850,159 bytes | PE x86_64 standalone executable with Nuitka onefile markers; not executed on Windows |

No Linux arm64 4.1.7 distribution was found in the checked official directory.
GizClaw builds its recovered Python implementation natively for Linux arm64.
The official documentation states that separate macOS CLI installers for
arm64 and x86_64 have been provided since product version 4.1.2.

The official Linux executable requires a UTF-8 locale. An initial check under
the container's ASCII locale failed in Click before command execution.
Repeating with `LANG=C.UTF-8` and `LC_ALL=C.UTF-8` passed. Both checks used no
network access and a read-only mount of the executable; no serial device was
attached. Windows execution has not been verified.

## Python source availability

The macOS package embeds Python 3.9.6 and a PyInstaller archive with 133
`bkutils` modules. These are compiled bytecode. The package does not contain
the complete `.py` source or a source wheel/sdist. The Linux and Windows ZIPs
contain their executable only; they are not Python source distributions.

The checked 4.x directory exposes `cli` and `gui` downloads, not a source
release. A complete upstream `.py` distribution has not been located.
GizClaw has now recovered all 130 executable modules and four namespace
packages from the pinned macOS executable and imported them into the maintained
runtime. This includes CLI parsing, download/batch orchestration, configuration,
chip controllers, secure debug and key injection.

The [source snapshot](../upstream/4.1.7/README.md) preserves the unadapted
reconstruction. Recompiling with Python 3.9 matches the complete runtime fields
for 111 modules, excluding file/line metadata. All 130 match the typed
instructions and control-flow graph under the documented layout-normalization
rules. [The verification report](../upstream/4.1.7/source-verification.json)
records each source and original-code hash; the verifier can repeat the check
from the pinned executable without executing it.

The version module's fallback remains `v1.1.0.5`. Its `get_tool_version()` reads
`config/version.yaml` and turns `4.1.7+261014250` into `4.1.7.250`. This explains
why the fallback backend number and product version cannot be equated.
The maintained package version is now `4.1.7`, based on the recovered source.
See [source provenance](source-provenance.md) for explicit packaging/import
adaptations and offline-validation limits.

## Installer contents

The macOS package installs 311 payload entries under `/usr/local/lib/bk_loader`.
These include the CLI, its private Python 3.9 framework, Python extension
modules, OpenSSL libraries and configuration. Its only `postinstall` script
creates `/usr/local/bin/bk_loader` as a symlink to that executable and marks
the executable runnable. It does not download packages, run pip, or install
a separate GUI application.

GizOS expands that payload without executing the script. The runtime stays
under the configured shared root; the package's global installation paths
are not used.

## GizOS integration

`gizos install bk-loader 4.1.7` installs and selects the official runtime under
the shared root. The CLI checks the catalog's archive and executable hashes.
The macOS package is expanded with `pkgutil --expand-full`; its `postinstall`
script is not executed, and `/usr/local` is not used. Runtime framework links,
configuration and the complete `_internal` directory are retained.

The download site may require browser verification. After downloading the
matching package through the official directory, import it without changing
installation path configuration:

```sh
gizos install bk-loader 4.1.7 \
  --archive ~/Downloads/bk_loader_macos_arm64_4.1.7.261014250.pkg
gizos env bk-loader 4.1.7
gizos run -- bk_loader --version
```

Import verifies the exact host archive checksum before caching and installing
it. Offline version/help checks do not establish physical-device flashing
acceptance.

## Primary references

- [Official product version manifest](https://dl.bekencorp.com/tools/bkfil/version.json)
- [Official CLI downloads](https://dl.bekencorp.com/tools/bkfil/v4/cli)
- [Official installation guide](https://docs.bekencorp.com/arminodoc/bk_app/bkfil_v4/en/latest/download/download_guide/download_guide.html)
- [Official release notes](https://docs.bekencorp.com/arminodoc/bk_app/bkfil_v4/en/latest/release_notes/release_notes.html)
