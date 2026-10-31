# Source provenance

`bk_loader` is Beken's host-side UART flashing utility. GizClaw now maintains
the complete Python implementation recovered from official BKFIL 4.1.7,
build 4.1.7.261014250. The source package is version 4.1.7 and its CLI prints
`bk_loader, version 4.1.7.250`.

## Source layout and verification

- `upstream/4.1.7/source/`: the unadapted recovery snapshot, containing 130
  executable modules and four empty namespace packages.
- `upstream/4.1.7/config/`: the four upstream YAML resources.
- `upstream/4.1.7/source-verification.json`: per-module source and original-code
  hashes plus runtime-field and instruction/control-flow comparisons.
- `src/`: the runnable maintained package and its explicit adaptations.
- `SOURCE.json`: current provenance, maintenance deltas and previous lineage.

111 recovered modules recompile to identical runtime fields under Python 3.9,
excluding filenames and line information. All 130 pass the typed instruction
and control-flow comparison, including nested code and exception handlers.
The complete entry point and download, batch, injection, secure-debug and
chip-controller services are recovered. Reproduction instructions and
comparison limits are in [the snapshot README](../upstream/4.1.7/README.md).

Recovery is from official PyInstaller bytecode, not an upstream Git tag or
published source archive. Original comments and formatting cannot be
reconstructed from bytecode. The vendor executable is not committed here.

## Maintained runtime changes

The unadapted snapshot is preserved so maintenance changes remain reviewable:

1. Version, flash-database and runtime configuration lookup use
   `bkutils/config` so installed wheels and PyInstaller executables work
   outside the checkout.
2. The unchanged `INITIATOR` enum lives in a small shared module and remains
   re-exported by `common`. This breaks the vendor's import cycle between
   common helpers, logging and configuration, which otherwise prevents fresh
   direct imports of `FlashConfig`.
3. The distribution entry point adds `tools selftest`, returning JSON and
   checking bundled data, native AES and P-256 signing without serial access.
   It suppresses the upstream tools banner for that one command.
4. Secure debug resolves the default private key next to the supplied public
   key. Public-key verification no longer requires an unrelated private key
   in the installed module directory; missing public keys raise a normal
   exception. No key material is bundled.

Upstream 4.1.7 already places the generic long-response status at byte 9,
matching the previous maintenance fix. Key-injection replies now include
an additional `0xf4` byte: command/status/data are at indexes 9/10/11.
The handshake response echoes `0x01`, and the start command ends in two CRLF
pairs. The AES-key reply handler preserves upstream's format-only acceptance;
the random-key handler checks status and echoed bytes. Offline tests record
these different contracts.

## Earlier lineage

The earlier `1.1.0.2.post2` package imported Python from
`h2vivi/firmware-devenv`, commit
`ff112cb8900a9c6398bfe5eea801e5139f182f34`,
directory `tools/bk_loader/src`. That source's backend constant was
`v1.1.0.2`; the old reference executable was product version
`4.0.2+260129055` with fallback backend `v1.1.0.5`.
Those backend constants do not establish an official BKFIL product version.
Historical optional Tizen modules and diagnostic scripts are retained but
are outside the recovered 4.1.7 module inventory and automated device tests.

## Validation boundary

Tests import every recovered module and exercise installed/frozen CLI help,
configuration, packet framing, mocked multi-entry writes, failed bus cleanup,
key-injection orchestration and real P-256 signing with a mocked transport.
They do not flash, erase, reset, provision or enumerate physical devices.

The recovered source includes the optional stdin/stdout bridge for a Flutter
frontend. No Flutter runtime or frontend metadata is needed by the CLI.
The package's `pubspec.lock` is therefore not included among runtime data.

Original Beken copyright and historical BSD/MIT declarations are retained.
See [NOTICE.md](../NOTICE.md) for the original declarations and scope.
