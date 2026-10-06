"""Verified SSH transport. No passwords are stored or accepted on the command line."""

from pathlib import Path
import re
import time
import paramiko

ROOT = Path(__file__).resolve().parent.parent


class Device:
    def __init__(self, host="10.11.99.1", password=None):
        self.client = paramiko.SSHClient()
        self.client.load_host_keys(str(Path.home() / ".ssh" / "known_hosts"))
        self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
        try:
            self.client.connect(
                host, username="root", password=password,
                allow_agent=password is None, look_for_keys=password is None,
                timeout=10, banner_timeout=10, auth_timeout=10,
            )
        except (OSError, paramiko.SSHException):
            self.client.close()
            raise

    def close(self):
        self.client.close()

    def run(self, command, timeout=60):
        _, stdout, _ = self.client.exec_command(command, timeout=timeout)
        channel = stdout.channel
        output, error = bytearray(), bytearray()
        deadline = time.monotonic() + timeout
        try:
            while True:
                if channel.recv_ready():
                    output.extend(channel.recv(65536))
                if channel.recv_stderr_ready():
                    error.extend(channel.recv_stderr(65536))
                if len(output) + len(error) > 16 * 1024 * 1024:
                    raise RuntimeError("Device command exceeded the bounded output limit.")
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                if time.monotonic() > deadline:
                    raise TimeoutError("Device command timed out; inspect device status before retrying.")
                time.sleep(0.01)
            code = channel.recv_exit_status()
        finally:
            channel.close()
        result = (output + error).decode("utf-8", errors="replace")
        if code:
            raise RuntimeError(f"Device command failed ({code}): {result.strip()}")
        return result

    def identify(self):
        output = self.run(
            "set -eu; uname -m; "
            "tr '\\000' '\\n' < /sys/firmware/devicetree/base/model; cat /etc/os-release")
        if not (
            re.search(r"^aarch64$", output, re.M)
            and re.search(r"^reMarkable Tatsu$", output, re.M)
            and re.search(r'^IMG_VERSION="3\.28\.0\.172"$', output, re.M)
            and re.search(r"^VERSION_ID=5\.8\.203$", output, re.M)
        ):
            raise RuntimeError("Unverified hardware/software; leave the tablet on stock.")
        return output
