# Set up the shared `edyxenv` environment for the lab. Safe to re-run (it also
# updates). Basic users only: packages installed in editable mode are skipped.
#
#   irm https://raw.githubusercontent.com/spalato/edyxlib/main/scripts/install.ps1 | iex
#
# Test without touching your setup:
#   $env:EDYX_ENV_DIR = "C:\tmp\envtest"; $env:EDYX_PROFILE_PATHS = "C:\tmp\p1.ps1"
#
# Runs inside the caller's session (iex): never `exit`, leak no variables.
& {
    $ErrorActionPreference = 'Stop'
    $index    = 'https://spalato.github.io/edyxlib/simple/'
    $packages = 'edyx', 'pyspan'
    $envDir   = if ($env:EDYX_ENV_DIR) { $env:EDYX_ENV_DIR } else { Join-Path $HOME '.venvs\edyxenv' }
    $python   = '3.14'
    $begin = '# >>> edyxenv >>>'
    $end   = '# <<< edyxenv <<<'

    function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
    function Warn($msg) { Write-Host "!!  $msg" -ForegroundColor Yellow }

    try {
        # 1. Execution policy (needed to load the profile and activate the env).
        Step 'Execution policy'
        try {
            $effective = Get-ExecutionPolicy
            if ($effective -in 'Unrestricted', 'Bypass', 'RemoteSigned') {
                Write-Host "    already $effective, unchanged"
            } else {
                Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
                Write-Host '    set to RemoteSigned (current user)'
            }
        } catch {
            Warn "Could not set the execution policy: $($_.Exception.Message)"
            Warn 'It is probably managed by your institution. Ask IT, or continue:'
            Warn 'the environment is installed but may not activate automatically.'
        }

        # 2. uv
        Step 'uv'
        if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
            Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
            $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' +
                        [Environment]::GetEnvironmentVariable('Path', 'Machine')
            if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
                throw 'uv was installed but is not found. Open a new terminal and run this again.'
            }
        } else { Write-Host '    found' }

        # 3. Environment (never recreated: no --clear)
        Step "Environment $envDir"
        if (-not (Test-Path (Join-Path $envDir 'Scripts\python.exe'))) {
            uv venv $envDir --python $python --seed
            if ($LASTEXITCODE) { throw 'Creating the environment failed (antivirus / Defender blocking uv or python?).' }
        } else { Write-Host '    exists' }

        # 4. Packages (skip editable installs)
        Step 'Packages'
        $sp = Join-Path $envDir 'Lib\site-packages'
        $todo = @()
        foreach ($p in $packages) {
            $editable = $false
            $du = Get-ChildItem $sp -Directory -Filter "$p-*.dist-info" -ErrorAction SilentlyContinue |
                  ForEach-Object { Join-Path $_.FullName 'direct_url.json' } |
                  Where-Object { Test-Path $_ } | Select-Object -First 1
            if ($du -and ((Get-Content $du -Raw) -match '"editable"\s*:\s*true')) { $editable = $true }
            if ($editable) { Warn "$p is installed in editable mode: skipped" } else { $todo += $p }
        }
        if ($todo) {
            uv pip install --python $envDir --upgrade --index $index @todo
            if ($LASTEXITCODE) { throw 'Installing packages failed.' }
        }

        # 5. Profile(s): Windows PowerShell 5.1 and PowerShell 7 use different files.
        Step 'PowerShell profile'
        $paths = if ($env:EDYX_PROFILE_PATHS) { $env:EDYX_PROFILE_PATHS -split ';' } else {
            $docs = [Environment]::GetFolderPath('MyDocuments')
            (Join-Path $docs 'WindowsPowerShell\Microsoft.PowerShell_profile.ps1'),
            (Join-Path $docs 'PowerShell\Microsoft.PowerShell_profile.ps1')
        }
        $block = @(
            $begin
            "function edyxenv { & '$(Join-Path $envDir 'Scripts\activate.ps1')' }"
            'edyxenv'
            $end
        ) -join "`r`n"
        foreach ($f in $paths) {
            $dir = Split-Path $f
            if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            $text = if (Test-Path $f) { Get-Content $f -Raw } else { '' }
            if ($null -eq $text) { $text = '' }
            $pat = '(?s)' + [regex]::Escape($begin) + '.*?' + [regex]::Escape($end)
            if ($text -match $pat) { $text = [regex]::Replace($text, $pat, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $block }) }
            else { $text = $text.TrimEnd() + "`r`n`r`n" + $block + "`r`n" }
            Set-Content -Path $f -Value $text -Encoding utf8
            Write-Host "    $f"
        }

        # 6. VSCode default interpreter (user settings; JSONC, so edited as text).
        # Never overwrites a different value. Only a fallback: an interpreter
        # selected in a workspace takes precedence.
        Step 'VSCode default interpreter'
        $settings = if ($env:EDYX_VSCODE_SETTINGS) { $env:EDYX_VSCODE_SETTINGS } else { Join-Path $env:APPDATA 'Code\User\settings.json' }
        $py = Join-Path $envDir 'Scripts\python.exe'
        $key = 'python.defaultInterpreterPath'
        $line = '    "' + $key + '": "' + $py.Replace('\', '\\') + '",'
        $text = if (Test-Path $settings) { Get-Content $settings -Raw } else { '' }
        if ($null -eq $text) { $text = '' }
        if ($text -match '"python\.defaultInterpreterPath"\s*:\s*"([^"]*)"') {
            $current = $Matches[1].Replace('\\', '\')
            if ($current -ieq $py) { Write-Host '    already configured' }
            else { Warn "already set to $current (left unchanged). Change it in VSCode settings if you want edyxenv." }
        } elseif ($text -match '"python\.defaultInterpreterPath"') {
            Warn 'python.defaultInterpreterPath is present in an unexpected form: left unchanged.'
        } else {
            $dir = Split-Path $settings
            if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
            if ($text.Trim() -eq '') { $new = "{`r`n$($line.TrimEnd(','))`r`n}`r`n" }
            elseif ($text -match '^\s*\{') {
                Copy-Item $settings "$settings.bak" -Force
                $new = [regex]::Replace($text, '\{', [System.Text.RegularExpressions.MatchEvaluator]{ param($m) "{`r`n$line" }, 1)
            } else { $new = $null; Warn "Unrecognised settings.json format: set the interpreter manually." }
            if ($new) { Set-Content -Path $settings -Value $new -Encoding utf8; Write-Host "    set in $settings (an existing file was backed up as settings.json.bak)" }
        }

        # 7. VSCode extensions
        Step 'VSCode extensions'
        if (Get-Command code -ErrorAction SilentlyContinue) {
            foreach ($x in 'ms-python.python', 'ms-toolsai.jupyter') { code --install-extension $x --force | Out-Null }
            Write-Host '    python, jupyter'
        } else { Warn 'VSCode (`code`) not found: install it, then add the Python and Jupyter extensions.' }

        Write-Host ''
        Write-Host 'Done. Open a NEW terminal: `(edyxenv)` should appear in the prompt.' -ForegroundColor Green
        Write-Host 'In VSCode, if a notebook asks for a kernel, pick the one with `edyxenv` in its path.'
    } catch {
        Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
}
