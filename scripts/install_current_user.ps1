param(
    [Parameter(Mandatory = $true)]
    [string]$PackagePath
)

$ErrorActionPreference = "Stop"
$ResolvedPackage = (Resolve-Path $PackagePath).Path
$InstallDirectory = Join-Path $env:LOCALAPPDATA "Programs\Auditor Support Tool"
$TemporaryDirectory = Join-Path $env:TEMP "AuditorSupportToolInstall"

Remove-Item $TemporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $TemporaryDirectory | Out-Null
Expand-Archive -Path $ResolvedPackage -DestinationPath $TemporaryDirectory -Force

$RequiredExecutable = Join-Path $TemporaryDirectory "Auditor Support Tool.exe"
if (-not (Test-Path $RequiredExecutable)) {
    throw "The selected package is not a valid Auditor Support Tool release."
}

New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
Get-ChildItem $InstallDirectory -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force
Copy-Item "$TemporaryDirectory\*" $InstallDirectory -Recurse -Force

$Shell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Auditor Support Tool.lnk"
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = Join-Path $InstallDirectory "Auditor Support Tool.exe"
$Shortcut.WorkingDirectory = $InstallDirectory
$Shortcut.Description = "Auditor Support Tool"
$Shortcut.Save()

Remove-Item $TemporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
Start-Process (Join-Path $InstallDirectory "Auditor Support Tool.exe")

Write-Host "Installed for the current user at: $InstallDirectory"
Write-Host "Desktop shortcut created: $ShortcutPath"
