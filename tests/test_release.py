import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from build_native_patch import RESOURCES
from device import Device
from infinite_horizontal import InfiniteHorizontal, checked_manifest


class ReleaseTests(unittest.TestCase):
    def test_identification_requires_exact_tuple(self):
        good = 'aarch64\nreMarkable Tatsu\nIMG_VERSION="3.28.0.172"\nVERSION_ID=5.8.203\n'
        device = object.__new__(Device)
        device.run = lambda command: good
        self.assertEqual(device.identify(), good)
        for output in [good.replace("Tatsu", "Ferrari"), good.replace("3.28.0.172", "3.29.0.1")]:
            device.run = lambda command, text=output: text
            with self.assertRaises(RuntimeError):
                device.identify()

    def test_manifest_requires_complete_hash_checked_resource_set(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = b"synthetic resource\n"
            sha = hashlib.sha256(data).hexdigest()
            manifest = {
                "version": 1, "software": "3.28.0.172",
                "resources": {path: sha for path, _ in RESOURCES.values()},
                "files": {name: sha for name in RESOURCES},
            }
            for name in RESOURCES:
                (root / name).write_bytes(data)
            (root / "manifest.json").write_text(json.dumps(manifest))
            mapping = "".join(f"R {RESOURCES[name][0]} {name}\n" for name in RESOURCES)
            (root / "infinite-horizontal.qrr").write_text(mapping)
            checked_manifest(root)
            (root / "DocumentView.qml").write_text("tampered")
            with self.assertRaises(ValueError):
                checked_manifest(root)

    def test_start_and_boot_changes_require_approval(self):
        device = object.__new__(InfiniteHorizontal)
        device.run = lambda command: self.fail("No device command should run")
        with self.assertRaises(ValueError):
            device.start()
        with self.assertRaises(ValueError):
            device.boot(True)
        with self.assertRaises(ValueError):
            device.uninstall()

    def test_runtime_verifier_accepts_exact_six_resource_index(self):
        if os.name == "nt":
            self.skipTest("The Linux verifier is exercised inside CTest/WSL.")
        executable = Path(__file__).resolve().parents[1] / "build" / "infinite-verify"
        if not executable.exists():
            self.skipTest("Build infinite-verify before running this integration check.")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resources = {f"/resource/{number}.qml": f"{number:064x}" for number in range(6)}
            (root / "manifest.json").write_text(json.dumps({"resources": resources}))
            (root / "index.json").write_text(json.dumps([
                {"path": path, "sha256": checksum} for path, checksum in resources.items()
            ]))
            result = subprocess.run([executable, root / "manifest.json", root / "index.json"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            index = json.loads((root / "index.json").read_text())
            index[-1]["sha256"] = "0" * 64
            (root / "index.json").write_text(json.dumps(index))
            result = subprocess.run([executable, root / "manifest.json", root / "index.json"],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
