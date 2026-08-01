param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

if (-not $SkipTests) {
    Invoke-CheckedCommand `
        -Description "Ruff checks" `
        -Command {
            python -m ruff check `
                .\main.py `
                .\updater_main.py `
                .\src `
                .\tests
        }

    Invoke-CheckedCommand `
        -Description "Pytest" `
        -Command {
            python -m pytest -q
        }
}

$Version = (
    python -c "from auditor_support_tool.core.constants import APP_VERSION; print(APP_VERSION)"
).Trim()

$NormalizedVersion = (
    python -c "from packaging.version import Version; print(Version('$Version'))"
).Trim()

if (
    $LASTEXITCODE -ne 0 -or
    [string]::IsNullOrWhiteSpace($NormalizedVersion)
) {
    throw "Could not normalise the application version."
}

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($Version)) {
    throw "Could not determine the application version."
}

# Windows executable version fields must contain four numeric components.
# Examples:
#   0.1.0          -> 0.1.0.0
#   0.1.1-beta.1   -> 0.1.1.1
$VersionPattern = '^(?<major>\d+)\.(?<minor>\d+)\.(?<patch>\d+)(?:-(?:alpha|beta|rc)\.(?<pre>\d+))?$'

if ($Version -notmatch $VersionPattern) {
    throw "Unsupported version format: $Version"
}

$PreReleaseNumber = if ($Matches.pre) {
    [int]$Matches.pre
}
else {
    0
}

$WindowsVersion = (
    "{0}.{1}.{2}.{3}" -f `
        $Matches.major, `
        $Matches.minor, `
        $Matches.patch, `
        $PreReleaseNumber
)

$PackageName = "Auditor-Support-Tool-Windows-x64.zip"
$InstallerName = "Auditor-Support-Tool-Setup.exe"
$ReleaseDirectory = Join-Path $ProjectRoot "release"
$ApplicationDirectory = Join-Path $ProjectRoot "dist\Auditor Support Tool"
$UpdaterExecutable = Join-Path $ProjectRoot "dist\Auditor Support Tool Updater.exe"
$InstallerScript = Join-Path $ProjectRoot "installer\AuditorSupportTool.iss"

$InnoSetupCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
)

$InnoCompiler = $InnoSetupCandidates |
    Where-Object { $_ -and (Test-Path $_) } |
    Select-Object -First 1

if (-not $InnoCompiler) {
    throw (
        "Inno Setup compiler was not found. Install Inno Setup 7 " +
        "and confirm that ISCC.exe is available."
    )
}

if (-not (Test-Path $InstallerScript)) {
    throw "Installer definition not found: $InstallerScript"
}

Remove-Item `
    .\build, `
    .\dist, `
    $ReleaseDirectory `
    -Recurse `
    -Force `
    -ErrorAction SilentlyContinue

New-Item `
    -ItemType Directory `
    -Force `
    -Path $ReleaseDirectory |
    Out-Null

Invoke-CheckedCommand `
    -Description "Main application build" `
    -Command {
        python -m PyInstaller `
            --noconfirm `
            --clean `
            --windowed `
            --onedir `
            --name "Auditor Support Tool" `
            --paths .\src `
            --add-data ".\src\auditor_support_tool\resources;auditor_support_tool\resources" `
            --collect-data certifi `
            .\main.py
    }

Invoke-CheckedCommand `
    -Description "Updater build" `
    -Command {
        python -m PyInstaller `
            --noconfirm `
            --clean `
            --console `
            --onefile `
            --name "Auditor Support Tool Updater" `
            --paths .\src `
            .\updater_main.py
    }

Copy-Item `
    $UpdaterExecutable `
    $ApplicationDirectory `
    -Force

$Manifest = @{
    format_version = 1
    version = $NormalizedVersion
    application_executable = "Auditor Support Tool.exe"
    updater_executable = "Auditor Support Tool Updater.exe"
} | ConvertTo-Json

$ManifestPath = Join-Path `
    $ApplicationDirectory `
    "update-manifest.json"

[System.IO.File]::WriteAllText(
    $ManifestPath,
    $Manifest,
    [System.Text.UTF8Encoding]::new($false)
)

$PackagePath = Join-Path `
    $ReleaseDirectory `
    $PackageName

Compress-Archive `
    -Path "$ApplicationDirectory\*" `
    -DestinationPath $PackagePath `
    -Force

$Hash = (
    Get-FileHash `
        -Path $PackagePath `
        -Algorithm SHA256
).Hash.ToLowerInvariant()

$ChecksumPath = "$PackagePath.sha256"

Set-Content `
    -Path $ChecksumPath `
    -Value "$Hash  $PackageName" `
    -Encoding ASCII

& $InnoCompiler `
    "/DMyAppVersion=$Version" `
    "/DMyWindowsVersion=$WindowsVersion" `
    "/DSourceDirectory=$ApplicationDirectory" `
    "/DOutputDirectory=$ReleaseDirectory" `
    $InstallerScript

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

$InstallerPath = Join-Path `
    $ReleaseDirectory `
    $InstallerName

if (-not (Test-Path $InstallerPath)) {
    throw "Installer was not created: $InstallerPath"
}

Write-Host ""
Write-Host "Release files created successfully:"
Write-Host "  Installer: $InstallerPath"
Write-Host "  Update package: $PackagePath"
Write-Host "  Update checksum: $ChecksumPath"
Write-Host "  Version: $Version"
Write-Host "  Windows version: $WindowsVersion"
Write-Host "  Manifest version: $NormalizedVersion"
