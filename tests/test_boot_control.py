import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "linux", "Boot controller targets Linux.")
class BootControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "home/root/remarkable-infinite-horizontal"
        (self.base / "state").mkdir(parents=True)
        (self.base / ".managed").write_text("managed")
        (self.base / "state/backup-complete").write_text("")
        (self.base / "remarkable-infinite-horizontal.service").write_text("[Service]\nType=oneshot\n")
        etc = self.root / "etc/systemd/system/multi-user.target.wants"
        etc.mkdir(parents=True)
        (self.root / "proc").mkdir()
        (self.root / "proc/mounts").write_text(
            "/dev/root / ext4 ro,relatime 0 0\n"
            "overlay /etc overlay rw,relatime,lowerdir=/etc,upperdir=/var/volatile/etc,workdir=/var/volatile/.etc-work 0 0\n")
        (self.root / "etc-os-release").write_text(
            'IMG_VERSION="3.28.0.172"\nVERSION_ID=5.8.203\n')
        (self.root / "model").write_bytes(b"reMarkable Tatsu\0")
        (self.root / "bin").mkdir()
        self.write_program("uname", "#!/bin/sh\nprintf 'aarch64\\n'\n")
        self.write_program("mount", "#!/bin/sh\nexit 0\n")
        self.write_program("umount", "#!/bin/sh\ntest \"$1\" = -R && exit 0\nexit 1\n")
        self.write_program("systemctl", "#!/bin/sh\nif test \"$1\" = is-enabled; then exit 0; fi\nexit 0\n")
        source = (Path(__file__).resolve().parents[1] / "packaging/boot-control.sh").read_text()
        source = source.replace("/home/root/remarkable-infinite-horizontal", str(self.base))
        source = source.replace("/etc/systemd/system", str(self.root / "etc/systemd/system"))
        source = source.replace("/etc/os-release", str(self.root / "etc-os-release"))
        source = source.replace("/sys/firmware/devicetree/base/model", str(self.root / "model"))
        source = source.replace("/proc/mounts", str(self.root / "proc/mounts"))
        self.script = self.root / "boot-control.sh"
        self.script.write_text(source)
        self.environment = dict(os.environ, PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"])

    def write_program(self, name, source):
        path = self.root / "bin" / name
        path.write_text(source)
        path.chmod(0o700)

    def run_action(self, action):
        return subprocess.run(["/bin/sh", self.script, action], capture_output=True,
                              text=True, env=self.environment, timeout=10)

    def test_enable_and_disable_manage_only_owned_service(self):
        result = self.run_action("enable")
        self.assertEqual(result.returncode, 0, result.stderr)
        unit = self.root / "etc/systemd/system/remarkable-infinite-horizontal.service"
        link = self.root / "etc/systemd/system/multi-user.target.wants/remarkable-infinite-horizontal.service"
        self.assertTrue(unit.is_file())
        self.assertTrue(link.is_symlink())
        result = self.run_action("disable")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(unit.exists())
        self.assertFalse(link.exists())

    def test_unowned_service_is_not_overwritten(self):
        unit = self.root / "etc/systemd/system/remarkable-infinite-horizontal.service"
        unit.write_text("another project\n")
        result = self.run_action("enable")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(unit.read_text(), "another project\n")

    def test_missing_backup_receipt_refuses_root_change(self):
        (self.base / "state/backup-complete").unlink()
        result = self.run_action("enable")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
