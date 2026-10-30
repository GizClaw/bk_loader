import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release_index.py"
HOSTS = ("darwin-arm64", "darwin-x64", "linux-arm64", "linux-x64", "win32-x64")
VERSION = "1.1.0.2.post2"
COMMIT = "a" * 40


class ReleaseTest(unittest.TestCase):
    def prepare(self, root):
        for host in HOSTS:
            filename = f"bk-loader-{VERSION}-{host}.tar.gz"
            payload = host.encode()
            (root / filename).write_bytes(payload)
            (root / f"{host}.json").write_text(json.dumps({
                "schema": 1, "version": VERSION, "commit": COMMIT, "host": host,
                "filename": filename, "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload), "selftest": {"frozen": True, "packageVersion": VERSION},
            }), encoding="utf-8")

    def run_index(self, root, commit=COMMIT):
        return subprocess.run([
            sys.executable, str(SCRIPT), "--directory", str(root), "--version", VERSION, "--commit", commit,
        ], capture_output=True, text=True)

    def test_complete_matrix_binds_checksums_and_source_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare(root)
            result = self.run_index(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((root / "index.json").read_text())
            self.assertEqual({item["host"] for item in manifest["files"]}, set(HOSTS))
            self.assertEqual(manifest["commit"], COMMIT)
            self.assertIn("index.json", (root / "SHA256SUMS").read_text())

    def test_missing_platform_wrong_commit_and_corrupt_archives_cannot_publish(self):
        for condition in ("missing", "wrong-commit", "corrupt"):
            with self.subTest(condition=condition), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.prepare(root)
                if condition == "missing":
                    (root / "win32-x64.json").unlink()
                if condition == "corrupt":
                    (root / f"bk-loader-{VERSION}-linux-x64.tar.gz").write_bytes(b"corrupt")
                result = self.run_index(root, commit="b" * 40 if condition == "wrong-commit" else COMMIT)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "index.json").exists())


if __name__ == "__main__":
    unittest.main()
