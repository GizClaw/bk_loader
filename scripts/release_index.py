"""Require the complete native matrix before publishing a Release."""

import argparse
import hashlib
import json
import re
from pathlib import Path


HOSTS = {"darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64", "win32-x64"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    files = []
    checksums = {}
    for host in sorted(HOSTS):
        item = json.loads((args.directory / f"{host}.json").read_text(encoding="utf-8"))
        if (item["schema"] != 1 or item["version"] != args.version or
                item["commit"] != args.commit or item["host"] != host or
                not item["selftest"]["frozen"] or item["selftest"]["packageVersion"] != args.version):
            raise ValueError(f"Invalid platform metadata: {host}")
        name = item["filename"]
        if Path(name).name != name or not re.fullmatch(r"bk-loader-[A-Za-z0-9.+-]+\.(?:tar\.gz|zip)", name):
            raise ValueError(f"Invalid archive name: {name}")
        archive = args.directory / name
        with archive.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        if checksum != item["sha256"] or archive.stat().st_size != item["size"]:
            raise ValueError(f"Archive integrity failed: {name}")
        checksums[name] = checksum
        files.append(item)
    index = args.directory / "index.json"
    index.write_text(json.dumps({
        "schema": 1, "version": args.version, "commit": args.commit,
        "repository": "GizClaw/bk_loader", "files": files,
    }, indent=2) + "\n", encoding="utf-8")
    with index.open("rb") as stream:
        checksums[index.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    (args.directory / "SHA256SUMS").write_text(
        "".join(f"{checksum}  {name}\n" for name, checksum in sorted(checksums.items())), encoding="utf-8",
    )


if __name__ == "__main__":
    main()
