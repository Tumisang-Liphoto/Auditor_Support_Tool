param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ConstantsPath = Join-Path `
    $ProjectRoot `
    "src\auditor_support_tool\core\constants.py"
$PyprojectPath = Join-Path `
    $ProjectRoot `
    "pyproject.toml"

$Utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)

$Constants = [System.IO.File]::ReadAllText(
    $ConstantsPath,
    [System.Text.Encoding]::UTF8
)

$UpdatedConstants = $Constants -replace `
    'APP_VERSION = "[^"]+"', `
    "APP_VERSION = `"$Version`""

if ($UpdatedConstants -eq $Constants) {
    throw "APP_VERSION was not found or was already set to $Version."
}

[System.IO.File]::WriteAllText(
    $ConstantsPath,
    $UpdatedConstants,
    $Utf8WithoutBom
)

$Pyproject = [System.IO.File]::ReadAllText(
    $PyprojectPath,
    [System.Text.Encoding]::UTF8
).TrimStart([char]0xFEFF)

$UpdatedPyproject = $Pyproject -replace `
    '(?m)^version = "[^"]+"', `
    "version = `"$Version`""

if ($UpdatedPyproject -eq $Pyproject) {
    throw "The project version was not found or was already set to $Version."
}

[System.IO.File]::WriteAllText(
    $PyprojectPath,
    $UpdatedPyproject,
    $Utf8WithoutBom
)

Write-Host "Updated APP_VERSION and pyproject.toml to $Version"
