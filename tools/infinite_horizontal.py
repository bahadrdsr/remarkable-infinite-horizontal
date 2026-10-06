"""Manage the native notebook extension over verified USB SSH."""

import argparse
import getpass
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tarfile
import time
import urllib.request

import paramiko
from device import Device, ROOT
from build_native_patch import RESOURCES, build

BASE = "/home/root/remarkable-infinite-horizontal"
MARKER = b"remarkable-infinite-horizontal v1\n"
LOCAL = ROOT / ".local"
ASSETS = (
    ("xovi.so", "https://github.com/asivery/xovi/releases/download/v0.3.3/xovi-aarch64.so",
     "d4df820c25c634c511de11067279d8310fa4f656dc52bd4540db6beac4ffd446"),
    ("extensions.tar.gz", "https://github.com/asivery/rm-xovi-extensions/releases/download/v19-23052026/xovi-aarch64.tar.gz",
     "32d64d1262ddc984e3235c7d0340a398fe6d5b3efa6a979865f5977b32630d27"),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def assets():
    directory = LOCAL / "artifacts"
    directory.mkdir(parents=True, exist_ok=True)
    result = {}
    for name, url, expected in ASSETS:
        path = directory / name
        if path.exists():
            data = path.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=45) as response:
                data = response.read()
        if digest(data) != expected:
            raise RuntimeError("Upstream artifact digest mismatch: " + name)
        if not path.exists():
            path.write_bytes(data)
        result[name] = data
    with tarfile.open(fileobj=io.BytesIO(result["extensions.tar.gz"]), mode="r:gz") as archive:
        member = archive.getmember("xovi/extensions.d/qt-resource-rebuilder.so")
        if not member.isfile() or member.size > 16 * 1024 * 1024:
            raise RuntimeError("Unexpected upstream archive entry.")
        result["qt-resource-rebuilder.so"] = archive.extractfile(member).read()
    if digest(result["qt-resource-rebuilder.so"]) != "6726f561557406f36347e43fc2b44a88deef4fb273d2ece88f48f427dad8800f":
        raise RuntimeError("Resource rebuilder digest mismatch.")
    return result


def mkdir(sftp, path):
    try:
        entry = sftp.lstat(path)
    except FileNotFoundError:
        sftp.mkdir(path, mode=0o700)
    else:
        if not stat.S_ISDIR(entry.st_mode):
            raise RuntimeError("Refusing a non-directory installation path.")


def write_file(sftp, path, data, replace=False):
    try:
        existing = sftp.lstat(path)
    except FileNotFoundError:
        existing = None
    if existing is not None:
        if not stat.S_ISREG(existing.st_mode):
            raise RuntimeError("Refusing to replace a non-regular file.")
        with sftp.file(path, "rb") as source:
            previous = source.read()
        if previous == data:
            return
        if not replace:
            raise RuntimeError("Immutable release artifact already exists with different content.")
    partial = path + ".partial"
    with sftp.file(partial, "wb") as output:
        output.write(data)
    sftp.chmod(partial, 0o700)
    if existing is None:
        sftp.rename(partial, path)
    else:
        sftp.posix_rename(partial, path)


def checked_manifest(directory):
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("version") != 1 or manifest.get("software") != "3.28.0.172":
        raise ValueError("Unverified patch manifest.")
    if set(manifest.get("files", {})) != set(RESOURCES):
        raise ValueError("The patch must contain exactly the four reviewed resources.")
    expected_paths = {path for path, _ in RESOURCES.values()}
    if set(manifest.get("resources", {})) != expected_paths:
        raise ValueError("Unexpected native resource paths.")
    contents = {}
    for name, (path, _) in RESOURCES.items():
        data = (directory / name).read_bytes()
        if digest(data) != manifest["files"][name] or digest(data) != manifest["resources"][path]:
            raise ValueError("Generated resource digest mismatch: " + name)
        contents[name] = data
    mapping = "".join(f"R {RESOURCES[name][0]} {name}\n" for name in RESOURCES).encode()
    if (directory / "infinite-horizontal.qrr").read_bytes().replace(b"\r\n", b"\n") != mapping:
        raise ValueError("Unexpected resource replacement mapping.")
    contents["infinite-horizontal.qrr"] = mapping
    return manifest, contents


class InfiniteHorizontal(Device):
    @staticmethod
    def remove_tree(sftp, path, depth=0):
        if depth > 12 or not path.startswith(BASE + "/"):
            raise RuntimeError("Refusing unsafe removal path.")
        try:
            entries = sftp.listdir_attr(path)
        except FileNotFoundError:
            return
        for entry in entries:
            child = path + "/" + entry.filename
            if stat.S_ISDIR(entry.st_mode):
                InfiniteHorizontal.remove_tree(sftp, child, depth + 1)
            elif stat.S_ISREG(entry.st_mode):
                sftp.remove(child)
            else:
                raise RuntimeError("Refusing to remove an unexpected file type.")
        sftp.rmdir(path)

    def install(self, patch_directory=None):
        self.identify()
        self.run("systemctl is-active --quiet xochitl.service; "
                 "test ! -e /run/systemd/system/xochitl.service")
        upstream = assets()
        files = {}
        for name in ("libnative-inspector.so", "libinfinite-settings.so", "native-document-snapshot",
                     "infinite-idle", "infinite-verify"):
            data = (ROOT / "build-device" / name).read_bytes()
            if data[:6] != b"\x7fELF\x02\x01" or data[18:20] != b"\xb7\x00":
                raise RuntimeError("Expected an AArch64 helper: " + name)
            files["bin/" + name] = data
        files["runtime/xovi.so"] = upstream["xovi.so"]
        files["runtime/extensions.d/qt-resource-rebuilder.so"] = upstream["qt-resource-rebuilder.so"]
        if patch_directory is None:
            manifest = {
                "version": 1, "software": "3.28.0.172",
                "resources": {path: expected for path, expected in RESOURCES.values()},
            }
            files["kind"] = b"capture\n"
        else:
            manifest, patches = checked_manifest(Path(patch_directory))
            for name, data in patches.items():
                files["runtime/exthome/qt-resource-rebuilder/" + name] = data
            files["kind"] = b"patch\n"
        files["manifest.json"] = json.dumps(manifest, indent=2).encode()
        files["vendor.sha256"] = self.run(
            "sha256sum /usr/lib/systemd/system/xochitl.service "
            "/usr/lib/systemd/system/xochitl.service.d/xochitl-service-override.conf").encode()
        controller = (ROOT / "packaging" / "manager.sh").read_bytes().replace(b"\r\n", b"\n")
        files["manager.sh"] = controller
        release_hash = hashlib.sha256()
        for name, data in sorted(files.items()):
            release_hash.update(name.encode() + b"\0" + data)
        release = release_hash.hexdigest()[:16]
        files["SHA256SUMS"] = "".join(
            f"{digest(data)}  {name}\n" for name, data in sorted(files.items())).encode()
        destination = f"{BASE}/releases/{release}"
        with self.client.open_sftp() as sftp:
            try:
                existing = sftp.lstat(BASE)
            except FileNotFoundError:
                mkdir(sftp, BASE)
                write_file(sftp, BASE + "/.managed", MARKER)
            else:
                if not stat.S_ISDIR(existing.st_mode):
                    raise RuntimeError("Installation root is not a directory.")
                with sftp.file(BASE + "/.managed", "rb") as source:
                    if source.read() != MARKER:
                        raise RuntimeError("Unrecognized installation root.")
            for folder in ("releases", "state", "backups", "inspection"):
                mkdir(sftp, BASE + "/" + folder)
            mkdir(sftp, destination)
            for folder in ("bin", "runtime", "runtime/extensions.d", "runtime/exthome",
                           "runtime/exthome/qt-resource-rebuilder"):
                mkdir(sftp, destination + "/" + folder)
            for name, data in files.items():
                write_file(sftp, destination + "/" + name, data)
            for name in ("manager.sh", "boot-control.sh", "remarkable-infinite-horizontal.service"):
                data = (ROOT / "packaging" / name).read_bytes().replace(b"\r\n", b"\n")
                write_file(sftp, BASE + "/" + name, data, replace=True)
            write_file(sftp, BASE + "/selected-release", (release + "\n").encode(), replace=True)
        self.run(f"cd {destination} && sha256sum -c SHA256SUMS")
        self.run(f"sh -n {BASE}/manager.sh; sh -n {BASE}/boot-control.sh")
        return release

    def start(self, approved=False):
        if not approved:
            raise ValueError("Explicit shutdown guard approval is required.")
        self.identify()
        token = os.urandom(6).hex()
        command = shlex.join([
            "systemd-run", "--quiet", "--wait", "--collect",
            f"--unit=infinite-horizontal-activate-{token}",
            "--service-type=exec", "--property=RuntimeMaxSec=150s",
            "/bin/sh", BASE + "/manager.sh", "activate", "guard-approved",
        ])
        try:
            self.run(command, timeout=170)
        except (OSError, RuntimeError, paramiko.SSHException):
            print("Activation failed. Inspect status; independent recovery was designed to restore stock.", file=sys.stderr)
            raise
        result = self.run(f"cat {BASE}/state/active").split()
        if len(result) != 2 or not re.fullmatch(r"[0-9a-f]{16}", result[0]) \
                or not re.fullmatch(r"[0-9a-f]{32}", result[1]):
            raise RuntimeError("Invalid activation receipt.")
        self.save_receipt(result[0], result[1])
        return result

    def stop(self):
        token = os.urandom(6).hex()
        self.run(shlex.join([
            "systemd-run", "--quiet", "--wait", "--collect",
            f"--unit=infinite-horizontal-stop-{token}", "--service-type=exec",
            "--property=RuntimeMaxSec=120s", "/bin/sh", BASE + "/manager.sh", "stock",
        ]), timeout=140)
        return self.status()

    def wait_for_transition(self):
        output = self.run(
            f"test -f {BASE}/state/last-transition && cat {BASE}/state/last-transition || echo 0")
        timestamp = int(output.split()[0])
        remaining = max(0, 181 - (int(time.time()) - timestamp))
        while remaining > 0:
            print(f"Waiting for the tablet safety interval: {remaining} seconds", flush=True)
            time.sleep(min(15, remaining))
            self.run("true")
            remaining = max(0, 181 - (int(time.time()) - timestamp))

    def setup(self, approved=False, enable_autostart=False, approve_root_change=False):
        if not approved:
            raise ValueError("Setup requires --approve-shutdown-guard.")
        if enable_autostart and not approve_root_change:
            raise ValueError("Automatic startup requires --approve-root-change.")
        capture_release = self.install()
        _, inspection = self.start(approved=True)
        try:
            inspection_path = self.collect(inspection)
        finally:
            self.stop()
        patch_path = LOCAL / "patches" / inspection
        build(inspection_path, patch_path)
        self.wait_for_transition()
        release = self.install(patch_path)
        self.start(approved=True)
        if enable_autostart:
            self.boot(True, approved=True)
        return {
            "release": release,
            "inspection": inspection,
            "patch": str(patch_path),
            "autostart": enable_autostart,
        }

    def status(self):
        return self.run(f"sh {BASE}/manager.sh status")

    def save_receipt(self, release, token):
        LOCAL.mkdir(exist_ok=True)
        (LOCAL / "last-session.json").write_text(json.dumps({"release": release, "inspection": token}, indent=2))

    def collect(self, token):
        if not re.fullmatch(r"[0-9a-f]{32}", token):
            raise ValueError("Invalid inspection identifier.")
        destination = LOCAL / "inspection" / token
        destination.mkdir(parents=True, exist_ok=True)
        with self.client.open_sftp() as sftp:
            with sftp.file(f"{BASE}/inspection/{token}/index.json", "rb") as source:
                data = source.read()
            index = json.loads(data)
            (destination / "index.json").write_bytes(data)
            for entry in index:
                if entry["path"] not in {path for path, _ in RESOURCES.values()}:
                    continue
                filename = entry["file"]
                if not re.fullmatch(r"[0-9]+\.qml", filename):
                    raise RuntimeError("Unsafe inspected resource filename.")
                with sftp.file(f"{BASE}/inspection/{token}/{filename}", "rb") as source:
                    contents = source.read()
                if digest(contents) != entry["sha256"]:
                    raise RuntimeError("Inspected resource digest mismatch.")
                (destination / filename).write_bytes(contents)
        return destination

    def boot(self, enabled, approved=False):
        if not approved:
            raise ValueError("Persistent startup changes require --approve-root-change.")
        self.identify()
        if enabled:
            self.run(f'test "$(cat {BASE}/releases/$(cat {BASE}/selected-release)/kind)" = patch; '
                     "systemctl is-active --quiet xochitl.service; "
                     f"test -f {BASE}/state/active")
        token = os.urandom(6).hex()
        action = "enable" if enabled else "disable"
        self.run(shlex.join([
            "systemd-run", "--quiet", "--wait", "--collect",
            f"--unit=infinite-horizontal-boot-change-{token}", "--service-type=exec",
            "--property=RuntimeMaxSec=90s", "/bin/sh", BASE + "/boot-control.sh", action,
        ]), timeout=110)
        output = self.run("awk '$2==\"/\" || $2==\"/etc\" {print $2,$3,$4}' /proc/mounts")
        if not re.search(r"^/ ext4 ro,", output, re.M) or not re.search(r"^/etc overlay ", output, re.M):
            raise RuntimeError("Filesystem mount restoration could not be verified.")
        return output

    def uninstall(self, approved=False):
        if not approved:
            raise ValueError("Uninstall requires --approve-root-change.")
        self.identify()
        self.boot(False, approved=True)
        self.stop()
        self.run("systemctl is-active --quiet xochitl.service; "
                 "systemctl is-active --quiet rm-sync.service; "
                 "test \"$(systemctl show xochitl.service -p FragmentPath --value)\" = "
                 "/usr/lib/systemd/system/xochitl.service")
        with self.client.open_sftp() as sftp:
            with sftp.file(BASE + "/.managed", "rb") as marker:
                if marker.read() != MARKER:
                    raise RuntimeError("Refusing to uninstall an unrecognized installation.")
            for directory in ("releases", "state", "inspection"):
                self.remove_tree(sftp, BASE + "/" + directory)
            for name in ("manager.sh", "boot-control.sh",
                         "remarkable-infinite-horizontal.service", "selected-release", "disabled"):
                try:
                    sftp.remove(BASE + "/" + name)
                except FileNotFoundError:
                    pass
        self.run("rm -f /home/root/.config/remarkable-infinite-horizontal/settings.json; "
                 "rmdir /home/root/.config/remarkable-infinite-horizontal 2>/dev/null || true")
        return "Uninstalled application code and settings. Native backups remain under " + BASE + "/backups."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[
        "identify", "capture", "install", "start", "stop", "status", "collect",
        "enable-autostart", "disable-autostart", "uninstall", "setup",
    ])
    parser.add_argument("--host", default="10.11.99.1")
    parser.add_argument("--patch", type=Path)
    parser.add_argument("--inspection")
    parser.add_argument("--approve-shutdown-guard", action="store_true")
    parser.add_argument("--approve-root-change", action="store_true")
    parser.add_argument("--enable-autostart", action="store_true")
    options = parser.parse_args()
    if options.action == "install" and options.patch is None:
        parser.error("install requires --patch")
    if options.action == "collect" and not options.inspection:
        parser.error("collect requires --inspection")
    device = InfiniteHorizontal(options.host, getpass.getpass("Tablet SSH password: "))
    try:
        if options.action == "identify":
            print(device.identify())
        elif options.action == "capture":
            print("Capture release:", device.install(), flush=True)
            _, token = device.start(options.approve_shutdown_guard)
            try:
                print("Local resources:", device.collect(token), flush=True)
            finally:
                device.stop()
        elif options.action == "install":
            print("Installed release:", device.install(options.patch))
        elif options.action == "start":
            print("Active release and inspection:", device.start(options.approve_shutdown_guard))
        elif options.action == "stop":
            print(device.stop())
        elif options.action == "status":
            print(device.status())
        elif options.action == "collect":
            print(device.collect(options.inspection))
        elif options.action == "setup":
            print(json.dumps(device.setup(
                approved=options.approve_shutdown_guard,
                enable_autostart=options.enable_autostart,
                approve_root_change=options.approve_root_change,
            ), indent=2))
        elif options.action == "uninstall":
            print(device.uninstall(options.approve_root_change))
        else:
            print(device.boot(options.action == "enable-autostart", options.approve_root_change))
    finally:
        device.close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, paramiko.SSHException) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
