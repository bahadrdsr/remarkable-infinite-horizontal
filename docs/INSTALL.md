# Installation

Last verified: October 6, 2026

## Before you start

You need:

- reMarkable Paper Pure
- Software `3.28.0.172`
- Developer mode already enabled
- A current, independently verified notebook backup
- The official recovery procedure ready on a Windows, macOS, or Linux computer
- A data-capable USB-C cable
- An x86_64 Linux environment, or Windows with Ubuntu WSL
- CMake, Ninja, a C++ compiler, Python 3, and Git

Enabling developer mode factory-resets the tablet. Follow the official developer-mode and recovery documentation before proceeding.

## 1. Clone and install host dependencies

```powershell
git clone https://github.com/bahadrdsr/remarkable-infinite-horizontal.git
cd remarkable-infinite-horizontal
python -m pip install -r .\tools\requirements.txt
```

For Ubuntu:

```powershell
wsl -d Ubuntu -u root --exec apt-get update
wsl -d Ubuntu -u root --exec apt-get install -y cmake ninja-build g++ qt6-base-dev qt6-declarative-dev
```

## 2. Install the matching official SDK

The SDK URL and the checksum observed during accepted development are recorded in `packaging/sdk.json`. Download it directly from the manufacturer's SDK index.

Inside Ubuntu:

```sh
mkdir -p "$HOME/.local/share/remarkable-infinite-horizontal/sdk"
chmod +x remarkable-production-image-5.8.203-tatsu-public-x86_64-toolchain.sh
./remarkable-production-image-5.8.203-tatsu-public-x86_64-toolchain.sh \
  -y -d "$HOME/.local/share/remarkable-infinite-horizontal/sdk/tatsu-5.8.203"
```

An SDK digest is a download-integrity check, not a replacement for verifying the manufacturer source.

## 3. Verify USB access

Wake and unlock the tablet, connect USB, then run:

```powershell
.\tools\Read-Device.ps1
```

Use the generated SSH password shown under the tablet's copyrights/licenses information, not the screen-lock PIN.

Do not put the password in source code, shell history, issue reports, or screenshots.

## 4. Build and test

```powershell
.\tools\Build-Local.ps1
.\tools\Build-Device.ps1
```

The device build fails if the compiler target, Paper Pure sysroot, or Qt version does not match the accepted baseline. It validates the `aarch64-remarkable-linux` compiler and `cortexa55-remarkable-linux` sysroot directly rather than relying on CMake's host processor value.

The project disables Qt's automatic CMake plugin and QML-plugin inclusion for device builds. The public SDK includes target plugins on the tablet sysroot but omits some host-side copies referenced by its package metadata. The extension is dynamically loaded into the tablet's existing Qt runtime and does not statically import those plugins.

The device build also pins `Qt6_DIR` to the target sysroot. Without that pin, a fresh SDK can resolve the host-side Qt libraries, which cannot be linked into an AArch64 tablet binary.

## 5. Collect exact stock resources

```powershell
python .\tools\infinite_horizontal.py capture --approve-shutdown-guard
```

This operation:

1. verifies hardware and firmware;
2. starts an independently timed recovery action;
3. waits for the stock editor to become idle;
4. contains the known stock shutdown crash without changing vendor files;
5. runs the unmodified editor with resource inspection enabled;
6. copies only six selected resources to `.local`;
7. returns to the original stock editor.

It does not install automatic startup.

## 6. Generate the local patch

Use the inspection directory printed above:

```powershell
python .\tools\build_native_patch.py `
  .\.local\inspection\<inspection-id> `
  .\.local\patches\current
```

The generator refuses resources whose SHA-256 values differ from the reviewed firmware.

The generated directory includes proprietary stock QML and must remain local. It is ignored by Git.

## 7. Install and test manually

```powershell
python .\tools\infinite_horizontal.py install --patch .\.local\patches\current
python .\tools\infinite_horizontal.py start --approve-shutdown-guard
python .\tools\infinite_horizontal.py status
```

Check:

- stock notebook tools and writing work;
- horizontal panning works in notebooks;
- global Display setting works;
- per-notebook override works both ways;
- PDFs and ebooks are unchanged;
- document sync remains active;
- root filesystem remains read-only.

Return to stock:

```powershell
python .\tools\infinite_horizontal.py stop
```

Wait at least three minutes between editor transitions.

## 8. Enable guarded automatic startup

Only after the manual checks pass:

```powershell
python .\tools\infinite_horizontal.py enable-autostart --approve-root-change
```

This installs one persistent systemd unit after backing up notebooks during manual activation. The installer restores the root filesystem to read-only and verifies the `/etc` overlay before returning success.

Perform a supervised reboot and unlock the tablet normally:

```powershell
ssh root@10.11.99.1 systemctl reboot
```

After unlock:

```powershell
python .\tools\infinite_horizontal.py status
```

If activation fails during boot, the service returns to stock and writes a disabled marker so it will not retry on every boot.
