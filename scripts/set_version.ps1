param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConstantsPath = Join-Path $ProjectRoot "src\auditor_support_tool\core\constants.py"
$PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"

$Constants = Get-Content $ConstantsPath -Raw
$Constants = $Constants -replace 'APP_VERSION = "[^"]+"', "APP_VERSION = `"$Version`""
Set-Content $ConstantsPath $Constants -Encoding UTF8

$Pyproject = Get-Content $PyprojectPath -Raw
$Pyproject = $Pyproject -replace '(?m)^version = "[^"]+"', "version = `"$Version`""
Set-Content $PyprojectPath $Pyproject -Encoding UTF8

Write-Host "Updated APP_VERSION and pyproject.toml to $Version"
