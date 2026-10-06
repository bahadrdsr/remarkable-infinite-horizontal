"""Run the production controller against an isolated synthetic device."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MOCK = r"""
import json, os, re, sys
from pathlib import Path
root=Path(os.environ['FAKE_DEVICE'])
data_path=root/'state.json'
s=json.loads(data_path.read_text())
a=sys.argv[1:]
s['commands'].append(' '.join(a))
unit=root/'run/systemd/system/xochitl.service'
drop=root/'run/systemd/system/xochitl.service.d/xochitl-service-override.conf'
source=root/'usr/lib/systemd/system/xochitl.service'
drop_source=root/'usr/lib/systemd/system/xochitl.service.d/xochitl-service-override.conf'
text=unit.read_text() if unit.exists() else source.read_text()
mod='LD_PRELOAD=' in text
handlers=re.findall(r'^OnFailure=(.*)$',text,re.M)
if not drop.exists(): handlers.append('emergency.target')
code=0
if a[0]=='show':
    values={'ActiveState':'active' if s['active'] else 'inactive',
            'MainPID':42 if s['active'] else 0,'ControlPID':0,
            'FragmentPath':str(unit if unit.exists() else source),
            'DropInPaths':str(drop if drop.exists() else drop_source),
            'OnFailure':' '.join(handlers),'Result':s.get('result','success'),
            'ExecMainStatus':11 if s.get('result')=='core-dump' else 0}
    print(values[a[a.index('-p')+1]])
elif a[0]=='is-active':
    code=0 if (a[-1].endswith('.timer') or (s['sync'] if a[-1]=='rm-sync.service' else s['active'])) else 3
elif a[0]=='stop':
    if a[-1]=='xochitl.service':
        if handlers: s['unsafe_stop']=True; code=1
        else: s['active']=False; s['sync']=False; s['result']='core-dump'
elif a[0]=='start':
    if mod and s.get('fail_modified_start'):
        s['active']=False
        code=1
    else:
        s['active']=True; s['sync']=True; s['result']='success'
        if mod:
            directory=Path(re.search(r'INFINITE_HORIZONTAL_INSPECTION=([^"]+)',text).group(1))
            directory.mkdir(parents=True,exist_ok=True)
            (directory/'index.json').write_text('[{}]')
elif a[0]=='reset-failed': s['result']='success'
elif a[0]!='daemon-reload': code=2
data_path.write_text(json.dumps(s))
sys.exit(code)
"""


@unittest.skipUnless(sys.platform == "linux", "Controller targets Linux.")
class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base = self.root / "home/root/remarkable-infinite-horizontal"
        self.base.mkdir(parents=True)
        self.runtime = self.root / "run/systemd/system"
        self.runtime.mkdir(parents=True)
        (self.root / "bin").mkdir()
        model = self.root / "sys/firmware/devicetree/base/model"
        model.parent.mkdir(parents=True)
        model.write_bytes(b"reMarkable Tatsu\0")
        (self.root / "etc").mkdir()
        (self.root / "etc/os-release").write_text('IMG_VERSION="3.28.0.172"\nVERSION_ID=5.8.203\n')
        vendor = self.root / "usr/lib/systemd/system"
        (vendor / "xochitl.service.d").mkdir(parents=True)
        (vendor / "xochitl.service").write_text("[Unit]\nOnFailure=remarkable-fail.service\n[Service]\nExecStart=/usr/bin/xochitl --system\n")
        (vendor / "xochitl.service.d/xochitl-service-override.conf").write_text("[Unit]\nOnFailure=emergency.target\n")
        self.release = self.base / "releases" / ("0" * 16)
        (self.release / "bin").mkdir(parents=True)
        (self.base / "selected-release").write_text("0" * 16 + "\n")
        self.write_program(self.release / "bin/infinite-idle", "#!/bin/sh\nexit 0\n")
        self.write_program(self.release / "bin/infinite-verify", "#!/bin/sh\nexit 0\n")
        self.write_program(self.release / "bin/native-document-snapshot", '#!/bin/sh\nmkdir -p "$2"\n')
        (self.release / "kind").write_text("patch\n")
        checksums = "".join(hashlib.sha256((self.release / f).read_bytes()).hexdigest() + "  " + f + "\n"
                            for f in ["bin/infinite-idle", "bin/infinite-verify", "bin/native-document-snapshot", "kind"])
        (self.release / "SHA256SUMS").write_text(checksums)
        (self.release / "vendor.sha256").write_text(
            hashlib.sha256((vendor / "xochitl.service").read_bytes()).hexdigest()
            + "  " + str(vendor / "xochitl.service") + "\n")
        uuid = self.root / "proc/sys/kernel/random/uuid"
        uuid.parent.mkdir(parents=True)
        uuid.write_text("00000000-1111-2222-3333-444444444444\n")
        (uuid.parent / "boot_id").write_text("current-boot\n")
        maps = self.root / "proc/42/maps"
        maps.parent.mkdir()
        maps.write_text(str(self.release / "runtime/xovi.so") + "\n"
                        + str(self.release / "bin/libinfinite-settings.so") + "\n")
        self.write_program(self.root / "bin/systemctl", "#!" + sys.executable + "\n" + MOCK)
        self.write_program(self.root / "bin/systemd-run", "#!/bin/sh\nexit 0\n")
        self.write_program(self.root / "bin/uname", "#!/bin/sh\nprintf 'aarch64\\n'\n")
        source = (Path(__file__).resolve().parents[1] / "packaging/manager.sh").read_text()
        for prefix in ["/home/root/remarkable-infinite-horizontal", "/run/systemd/system",
                       "/run/infinite-horizontal-transition", "/usr/lib/systemd/system",
                       "/sys/firmware/devicetree/base/model", "/etc/os-release", "/proc/"]:
            source = source.replace(prefix, str(self.root) + prefix)
        self.script = self.root / "manager.sh"
        self.script.write_text(source)
        self.environment = dict(os.environ, FAKE_DEVICE=str(self.root),
                                PATH=str(self.root / "bin") + os.pathsep + os.environ["PATH"])
        self.write_state({"active": True, "sync": True, "commands": []})

    def write_program(self, path, text):
        path.write_text(text)
        path.chmod(0o700)

    def write_state(self, state):
        (self.root / "state.json").write_text(json.dumps(state))

    def state(self):
        return json.loads((self.root / "state.json").read_text())

    def run_action(self, action, approved=True):
        command = ["/bin/sh", str(self.script), action]
        if approved: command.append("guard-approved")
        return subprocess.run(command, capture_output=True, text=True,
                              env=self.environment, timeout=15)

    def test_activate_preserves_stock_service_and_sync(self):
        result = self.run_action("activate")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.state()["active"])
        self.assertTrue(self.state()["sync"])
        self.assertFalse(self.state().get("unsafe_stop"))
        self.assertTrue((self.base / "state/active").exists())
        text = (self.runtime / "xochitl.service").read_text()
        self.assertIn("OnFailure=infinite-horizontal-recovery.service", text)
        self.assertIn("ExecStart=/usr/bin/xochitl --system", text)
        result = self.run_action("stock")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.runtime / "xochitl.service").exists())
        self.assertTrue(self.state()["active"])

    def test_failed_start_disables_boot_and_restores_original(self):
        state = self.state()
        state["fail_modified_start"] = True
        self.write_state(state)
        result = self.run_action("activate")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.base / "disabled").exists())
        self.assertTrue(self.state()["active"])
        self.assertFalse((self.runtime / "xochitl.service").exists())
        self.assertFalse(self.state().get("unsafe_stop"))
        self.assertTrue(any("stop infinite-horizontal-deadline-" in command
                            for command in self.state()["commands"]))

    def test_unguarded_manual_activation_is_refused(self):
        result = self.run_action("activate", approved=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["commands"], [])

    def test_boot_with_stale_receipt_leaves_stock(self):
        (self.base / "state").mkdir()
        (self.base / "state/incomplete").write_text("interrupted")
        result = self.run_action("boot")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.base / "disabled").exists())
        self.assertEqual(self.state()["commands"], [])

    def test_boot_on_new_firmware_does_not_touch_stock(self):
        (self.root / "etc/os-release").write_text('IMG_VERSION="3.29.0.1"\nVERSION_ID=6.0.0\n')
        result = self.run_action("boot")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.state()["commands"], [])

    def test_boot_ignores_transition_time_from_an_older_boot(self):
        state = self.base / "state"
        state.mkdir()
        (state / "backup-complete").write_text("")
        (state / "last-transition").write_text("9999999999 old-boot\n")
        result = self.run_action("boot")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((state / "active").exists())

    def test_unowned_override_is_never_replaced(self):
        existing = self.runtime / "xochitl.service"
        existing.write_text("someone else's configuration\n")
        result = self.run_action("activate")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(existing.read_text(), "someone else's configuration\n")


if __name__ == "__main__":
    unittest.main()
