param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not $SkipTests) {
    python -m ruff check .\main.py .\updater_main.py .\src .\tests
    python -m pytest -q
}

$Version = python -c "from auditor_support_tool.core.constants import APP_VERSION; print(APP_VERSION)"
$PackageName = "Auditor-Support-Tool-Windows-x64.zip"
$ReleaseDirectory = Join-Path $ProjectRoot "release"
$ApplicationDirectory = Join-Path $ProjectRoot "dist\Auditor Support Tool"
$UpdaterExecutable = Join-Path $ProjectRoot "dist\Auditor Support Tool Updater.exe"

Remove-Item .\build, .\dist, $ReleaseDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $ReleaseDirectory | Out-Null

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "Auditor Support Tool" `
    --paths .\src `
    .\main.py

python -m PyInstaller `
    --noconfirm `
    --clean `
    --console `
    --onefile `
    --name "Auditor Support Tool Updater" `
    --paths .\src `
    .\updater_main.py

Copy-Item $UpdaterExecutable $ApplicationDirectory -Force

$Manifest = @{
    format_version = 1
    version = $Version.Trim()
    application_executable = "Auditor Support Tool.exe"
    updater_executable = "Auditor Support Tool Updater.exe"
} | ConvertTo-Json

$ManifestPath = Join-Path $ApplicationDirectory "update-manifest.json"
Set-Content -Path $ManifestPath -Value $Manifest -Encoding UTF8

$PackagePath = Join-Path $ReleaseDirectory $PackageName
Compress-Archive -Path "$ApplicationDirectory\*" -DestinationPath $PackagePath -Force

$Hash = (Get-FileHash -Path $PackagePath -Algorithm SHA256).Hash.ToLowerInvariant()
$ChecksumPath = "$PackagePath.sha256"
Set-Content -Path $ChecksumPath -Value "$Hash  $PackageName" -Encoding ASCII

Write-Host "Release package created: $PackagePath"
Write-Host "Checksum created: $ChecksumPath"
Write-Host "Version: $Version"
