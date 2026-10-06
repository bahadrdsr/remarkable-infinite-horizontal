[CmdletBinding()]
param([string]$Distribution = 'Ubuntu')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& wsl -d $Distribution --cd $root --exec bash tools/build-device.sh
if ($LASTEXITCODE -ne 0) {
    throw 'Tablet cross-compilation failed.'
}
