[CmdletBinding()]
param([string]$Distribution = 'Ubuntu')

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
& wsl -d $Distribution --cd $root --exec cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
if ($LASTEXITCODE -ne 0) { throw 'CMake configuration failed.' }
& wsl -d $Distribution --cd $root --exec cmake --build build --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'Compilation failed.' }
& wsl -d $Distribution --cd $root --exec ctest --test-dir build --output-on-failure
if ($LASTEXITCODE -ne 0) { throw 'Native helper tests failed.' }
& python -m unittest discover -s (Join-Path $root 'tests') -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
