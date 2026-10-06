[CmdletBinding()]
param(
    [string]$Distribution = 'Ubuntu',
    [switch]$NoAutostart
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$confirmation = Read-Host @'
This installer is only for reMarkable Paper Pure software 3.28.0.172.
Developer mode must already be enabled, which factory-resets the tablet.
Your notebooks must be backed up and the official recovery process must be ready.

Type I HAVE A BACKUP to continue
'@
if ($confirmation -cne 'I HAVE A BACKUP') {
    throw 'Installation cancelled. No tablet changes were made.'
}

foreach ($tool in @('wsl', 'python')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "$tool is required. See docs\WINDOWS-QUICKSTART.md."
    }
}
$distributions = wsl --list --quiet | ForEach-Object { $_.Replace([char]0, '').Trim() }
if ($distributions -notcontains $Distribution) {
    throw "WSL distribution '$Distribution' is not installed."
}

Write-Host 'Installing Windows Python dependency...'
& python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

Write-Host 'Installing Linux build dependencies...'
& wsl -d $Distribution -u root --exec bash -lc `
    'export DEBIAN_FRONTEND=noninteractive; apt-get update -qq && apt-get install -y -qq cmake ninja-build g++ curl xz-utils qt6-base-dev qt6-declarative-dev'
if ($LASTEXITCODE -ne 0) { throw 'Linux dependency installation failed.' }

$spec = Get-Content (Join-Path $root 'packaging\sdk.json') -Raw | ConvertFrom-Json
if ($spec.installerUrl -notmatch '^https://storage\.googleapis\.com/remarkable-codex-toolchain/') {
    throw 'The SDK URL is not an approved manufacturer URL.'
}
if ($spec.observedInstallerSha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'The SDK checksum is invalid.'
}
$sdkCommand = @'
set -eu
installer="$HOME/.cache/remarkable-infinite-horizontal/tatsu-5.8.203-toolchain.sh"
target="$HOME/.local/share/remarkable-infinite-horizontal/sdk/tatsu-5.8.203"
mkdir -p "$(dirname "$installer")" "$(dirname "$target")"
if ! test -f "$installer"; then
  curl --fail --location --show-error --silent --retry 2 '__SDK_URL__' -o "$installer"
fi
printf '%s  %s\n' '__SDK_SHA256__' "$installer" | sha256sum -c -
if ! test -r "$target/environment-setup-cortexa55-remarkable-linux"; then
  sh "$installer" -y -d "$target"
fi
'@
$sdkCommand = $sdkCommand.Replace('__SDK_URL__', [string]$spec.installerUrl)
$sdkCommand = $sdkCommand.Replace('__SDK_SHA256__', [string]$spec.observedInstallerSha256)
Write-Host 'Downloading and installing the official matching SDK...'
& wsl -d $Distribution --exec bash -lc $sdkCommand
if ($LASTEXITCODE -ne 0) { throw 'SDK installation failed.' }

Write-Host 'Building and testing...'
& (Join-Path $PSScriptRoot 'Build-Local.ps1') -Distribution $Distribution
& (Join-Path $PSScriptRoot 'Build-Device.ps1') -Distribution $Distribution

Write-Host 'Keep the tablet awake, unlocked, and connected over USB.'
$arguments = @(
    (Join-Path $PSScriptRoot 'infinite_horizontal.py'),
    'setup',
    '--approve-shutdown-guard'
)
if (-not $NoAutostart) {
    $arguments += '--enable-autostart'
    $arguments += '--approve-root-change'
}
& python @arguments
if ($LASTEXITCODE -ne 0) {
    throw 'Tablet setup failed. The installer is designed to return to stock on failure. Run the status command in the recovery guide.'
}

Write-Host 'Installation completed. Open Settings > Display settings to choose the global default.'
