param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,

    [string]$Title = "Auditor Support Tool Testing Release",

    [string]$Notes = "Testing release for continuous user evaluation."
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

& .\scripts\build_release.ps1

$Package = ".\release\Auditor-Support-Tool-Windows-x64.zip"
$Checksum = "$Package.sha256"

gh release create $Tag `
    $Package `
    $Checksum `
    --repo Tumisang-Liphoto/Auditor_Support_Tool `
    --title $Title `
    --notes $Notes `
    --prerelease `
    --target main
