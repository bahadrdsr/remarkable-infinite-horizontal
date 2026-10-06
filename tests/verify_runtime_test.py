import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    executable = Path(sys.argv[1])
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        resources = {f"/resource/{number}.qml": f"{number:064x}" for number in range(6)}
        (root / "manifest.json").write_text(json.dumps({"resources": resources}))
        index = [{"path": path, "sha256": checksum} for path, checksum in resources.items()]
        (root / "index.json").write_text(json.dumps(index))
        valid = subprocess.run([executable, root / "manifest.json", root / "index.json"])
        if valid.returncode != 0:
            return 1
        index[-1]["sha256"] = "0" * 64
        (root / "index.json").write_text(json.dumps(index))
        invalid = subprocess.run([executable, root / "manifest.json", root / "index.json"])
        return 0 if invalid.returncode != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
