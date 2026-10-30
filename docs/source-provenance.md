# BK Loader

`bk_loader` is Beken's host-side UART flashing utility. It is not a target
bootloader and it does not run on the BK chip.

## Layout

- `macos-arm64/`: vendor reference executable, version
  `4.0.2+260129055` (embedded Python backend `v1.1.0.5`).
- `src/`: runnable Python source. The base is Beken's publicly released
  `v1.1.0.2` source, with locally maintained fixes and recovered
  `v1.1.0.5` protocol/UI compatibility modules.
- `tests/`: tests for the recovered protocol code.

The Python backend supports a vendor Flutter desktop frontend through a small
stdin/stdout JSON bridge. Flutter is not part of the UART protocol, is not
needed by the CLI, and no Flutter runtime is required for `download`, `erase`,
or `read`. The `pubspec.lock` found in the packaged executable is frontend
packaging metadata, so it is intentionally not copied into the source tree.

## Run from source

```sh
make -C tools/bk_loader setup
make -C tools/bk_loader help
make -C tools/bk_loader run ARGS='tools list_ports'
```

The Firmwares integration currently uses these operations:

```sh
make -C tools/bk_loader run ARGS='download -p PORT -b 500000 --reset_type 0 --link_type 0 -r -i all-app.bin -s 0x0'
make -C tools/bk_loader run ARGS='erase -p PORT -b 500000 --reset_type 0 --link_type 0 -c -r'
```

`erase` and `download` modify a connected device. Tests in this repository do
not invoke either operation.

## Recovery status

The packaged executable is a PyInstaller Python 3.9 bundle. Comparing its
embedded code objects with the public/local source found 98 common modules;
58 are bytecode-identical and 79 retain identical top-level code/name tables.
This is strong evidence that the public tree is the correct source lineage,
but it does not make the whole tree an exact reconstruction of `v1.1.0.5`.

Recovered and tested here:

- the complete public `v1.1.0.2` CLI/protocol/chip-controller tree;
- the packaged flash database and runtime tuning configuration;
- long application command framing;
- key-injection start, handshake, AES/random-key and secure-boot protocols;
- the optional Flutter JSON data and stdin/stdout bridge;
- global initiator/log configuration state.

The packaged `v1.1.0.5` bytecode reads both the long-response command and
status from byte 8. Its own documented frame places status at byte 9; the
source version fixes that off-by-one and covers it with an echo-response test.

Still reference-binary-only:

- the `v1.1.0.5` secure-debug and key-injection action orchestration;
- BK5886, BK7236N/BK7236N-security and BK7311 controller deltas;
- some newer retry, logging and download-flow changes.

Those modules have complex Python 3.9 control flow. Automated decompilers
mis-reconstruct branches and local variables, so they are deliberately not
presented as trustworthy source. The checked-in vendor executable remains the
compatibility reference for those functions. The ordinary BK7258 CLI path used
by Firmwares does not require Flutter or the new key-injection commands.

The public source contains a Beken copyright header allowing BSD-style
distribution, while its historical `setup.py` declares MIT. Both upstream
notices are preserved; no broader relicensing claim is made here.
