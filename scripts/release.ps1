# Usage: scripts\release.ps1 <package> <version>   e.g. scripts\release.ps1 edyx 0.2.0
# Bumps the version, runs tests, commits, tags `<package>-v<version>` and pushes.
# The tag triggers .github/workflows/release.yml, which publishes the wheel.
param(
    [Parameter(Mandatory)][string]$Package,
    [Parameter(Mandatory)][string]$Version
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if (git -C $root status --porcelain) { throw "Working tree not clean." }

Push-Location (Join-Path $root $Package)
try {
    uv version $Version
    uv run pytest
    if ($LASTEXITCODE) { throw "Tests failed." }
}
finally { Pop-Location }

git -C $root add "$Package/pyproject.toml" "$Package/uv.lock"
git -C $root commit -m "Release $Package $Version"
git -C $root tag "$Package-v$Version"
git -C $root push origin HEAD "$Package-v$Version"
