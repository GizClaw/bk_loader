"""Distribution entry point; keep the imported Beken CLI source intact."""

import json
import sys
from importlib.metadata import version
from pathlib import Path

import click
import yaml
from Crypto.Cipher import AES

from bk_loader import cli, tools_group
from bkutils.common.bk_out_config import BkOutConfig
from bkutils.common.version import get_tool_version
from bkutils.flash_adapter.flash_config import FlashConfig


@tools_group.command("selftest")
def selftest():
    """Check bundled configuration and crypto without accessing a device."""
    flash = FlashConfig()
    if not flash.cfg_info:
        raise click.ClickException("Flash database is empty")
    config = yaml.safe_load(Path(BkOutConfig.get_config_file_path()).read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "download_flow" not in config:
        raise click.ClickException("Runtime configuration is incomplete")
    # NIST AES-128 ECB known-answer test exercises PyCryptodome's native code.
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    plaintext = bytes.fromhex("00112233445566778899aabbccddeeff")
    expected = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")
    if AES.new(key, AES.MODE_ECB).encrypt(plaintext) != expected:
        raise click.ClickException("AES self-test failed")
    click.echo(json.dumps({
        "schema": 1,
        "packageVersion": version("gizclaw-bk-loader"),
        "upstreamVersion": get_tool_version(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "flashEntries": len(flash.cfg_info),
        "crypto": "ok",
    }, sort_keys=True))


if __name__ == "__main__":
    cli(prog_name="bk_loader")
