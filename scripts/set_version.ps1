param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+(?:-(?:alpha|beta|rc)\.\d+)?$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
$Sources = @(
    @{ Path = "src\auditor_support_tool\core\constants.py"; Key = "APP_VERSION" },
    @{ Path = "pyproject.toml"; Key = "version" },
    @{ Path = "src\auditor_support_tool\__init__.py"; Key = "__version__" }
)

# Validate every source before writing any; an already matching value is valid.
$Updates = foreach ($Source in $Sources) {
    $SourcePath = Join-Path $ProjectRoot $Source.Path
    $Original = [System.IO.File]::ReadAllText($SourcePath, [System.Text.Encoding]::UTF8)
    $Pattern = '(?m)^' + [regex]::Escape($Source.Key) + ' = "[^"\r\n]+"'
    if ([regex]::Matches($Original, $Pattern).Count -ne 1) {
        throw "Expected exactly one $($Source.Key) assignment in $($Source.Path)."
    }
    $Replacement = $Source.Key + ' = "' + $Version + '"'
    @{
        Path = $SourcePath
        Original = $Original
        Updated = [regex]::Replace($Original, $Pattern, $Replacement)
    }
}

$Written = [System.Collections.Generic.List[object]]::new()
try {
    foreach ($Update in $Updates) {
        $Written.Add($Update)
        [System.IO.File]::WriteAllText($Update.Path, $Update.Updated, $Utf8WithoutBom)
    }
}
catch {
    foreach ($Update in $Written) {
        [System.IO.File]::WriteAllText($Update.Path, $Update.Original, $Utf8WithoutBom)
    }
    throw
}
Write-Host "Updated APP_VERSION, pyproject.toml and __version__ to $Version"
