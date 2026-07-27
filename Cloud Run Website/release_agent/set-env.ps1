# Dot-source this each time you open a new terminal for local dev:
#   . .\release_agent\set-env.ps1
# Reads release_agent/.env and exports each KEY=VALUE as $env:KEY for this session.

$envFile = Join-Path $PSScriptRoot ".env"

if (-not (Test-Path $envFile)) {
    Write-Error "No .env file found at $envFile"
    return
}

Get-Content $envFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }

    $idx = $line.IndexOf("=")
    if ($idx -lt 0) { return }

    $key = $line.Substring(0, $idx).Trim()
    $value = $line.Substring($idx + 1).Trim()

    if ($value -eq "") { return }

    Set-Item -Path "env:$key" -Value $value
    Write-Host "Set env:$key"
}
