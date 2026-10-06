[CmdletBinding()]
param(
    [string]$DeviceHost = '10.11.99.1'
)

$ErrorActionPreference = 'Stop'
if ($DeviceHost -notmatch '^[A-Za-z0-9][A-Za-z0-9.-]*$') {
    throw 'Use a hostname or IPv4 address, not SSH options or a shell command.'
}
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    throw 'OpenSSH is required.'
}

Write-Host 'Read-only device probe. No installation, key changes, or stock-UI restart.'
Write-Host 'Use only a tablet you own and have connected over USB.'
Write-Host 'SSH will ask you to verify an unknown host key. Stop if you cannot verify the device.'
Write-Host 'Enter the tablet password only in the SSH prompt, never in chat or a script.'

$probe = @'
set -eu
printf 'Architecture:\n'
uname -m
printf '\nOS and build:\n'
cat /etc/os-release
printf '\nHardware model:\n'
if test -r /sys/firmware/devicetree/base/model; then
    tr '\000' '\n' < /sys/firmware/devicetree/base/model
else
    printf 'Hardware model unavailable\n'
    exit 1
fi
printf '\nInput devices:\n'
cat /proc/bus/input/devices
printf '\nMemory:\n'
head -n 5 /proc/meminfo
printf '\nStock UI state:\n'
systemctl is-active xochitl
'@

& ssh -o StrictHostKeyChecking=ask -o ConnectTimeout=10 "root@$DeviceHost" $probe
if ($LASTEXITCODE -ne 0) {
    throw "Read-only SSH probe failed with exit code $LASTEXITCODE."
}
