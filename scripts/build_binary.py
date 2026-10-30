"""Build and smoke-test one host executable, then archive it for Release."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from importlib.metadata import version
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "release")
    parser.add_argument("--host", help="Fail if the runner's actual platform differs")
    args = parser.parse_args()
    system = {"Darwin": "darwin", "Linux": "linux", "Windows": "win32"}[platform.system()]
    arch = {"AMD64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}[platform.machine()]
    host = f"{system}-{arch}"
    if args.host and args.host != host:
        raise ValueError(f"Expected {args.host}, running on {host}")
    package_version = version("gizclaw-bk-loader")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    entry = "bk_loader.exe" if system == "win32" else "bk_loader"
    with tempfile.TemporaryDirectory(prefix="bk-loader-build-") as directory:
        staging = Path(directory)
        subprocess.run([
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
            "--name", "bk_loader", "--distpath", str(staging / "bin"),
            "--workpath", str(staging / "build"), "--specpath", str(staging),
            "--collect-data", "bkutils.config", "--collect-all", "Crypto",
            "--copy-metadata", "gizclaw-bk-loader",
            str(ROOT / "src" / "gizclaw_bk_loader.py"),
        ], cwd=ROOT, check=True)
        binary = staging / "bin" / entry
        # Run away from the checkout and without host Python/module lookup.
        clean = {key: value for key, value in os.environ.items()
                 if key not in {"PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"}}
        clean["PATH"] = os.environ.get("SystemRoot", "C:\\Windows") + "\\System32" if system == "win32" else "/usr/bin:/bin"
        for arguments in (["--help"], ["--version"], ["download", "--help"], ["erase", "--help"]):
            subprocess.run([str(binary), *arguments], cwd=staging, env=clean, check=True, timeout=90)
        result = subprocess.run(
            [str(binary), "tools", "selftest"], cwd=staging, env=clean,
            capture_output=True, text=True, check=True, timeout=90,
        )
        tested = json.loads(result.stdout)
        if tested["packageVersion"] != package_version or not tested["frozen"] or tested["crypto"] != "ok":
            raise RuntimeError(f"Frozen executable failed self-test: {tested}")
        suffix = "zip" if system == "win32" else "tar.gz"
        filename = f"bk-loader-{package_version}-{host}.{suffix}"
        archive = output / filename
        files = [(binary, f"bin/{entry}"), *[(ROOT / name, name) for name in ("LICENSE", "NOTICE.md", "SOURCE.json")]]
        if suffix == "zip":
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path, name in files:
                    bundle.write(path, name)
        else:
            with tarfile.open(archive, "w:gz") as bundle:
                for path, name in files:
                    bundle.add(path, arcname=name)
        metadata = {
            "schema": 1, "version": package_version, "commit": commit, "host": host,
            "filename": filename, "sha256": digest(archive), "size": archive.stat().st_size,
            "executable": f"bin/{entry}", "executableSha256": digest(binary),
            "selftest": tested,
        }
        (output / f"{host}.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
