# Installs the FleetIQ observer plugin for Hermes (native Windows PowerShell).
#
# Usage:
#   $env:FLEETIQ_URL="https://your-fleetiq-host"; $env:FLEETIQ_API_KEY="fliq_sk_..."; .\install.ps1
#
# Or answer the prompts interactively if the env vars aren't set.

$ErrorActionPreference = "Stop"

$RepoRaw = "https://raw.githubusercontent.com/david043/fleetiq-hermes-plugin/main"

$FleetiqUrl = $env:FLEETIQ_URL
if (-not $FleetiqUrl) {
    $FleetiqUrl = Read-Host "FleetIQ URL (e.g. https://fleetiq.example.com)"
}
$FleetiqApiKey = $env:FLEETIQ_API_KEY
if (-not $FleetiqApiKey) {
    $FleetiqApiKey = Read-Host "FleetIQ API key"
}
if (-not $FleetiqUrl -or -not $FleetiqApiKey) {
    Write-Error "FLEETIQ_URL and FLEETIQ_API_KEY are both required."
    exit 1
}
$FleetiqProjectId = $env:FLEETIQ_PROJECT_ID
if (-not $FleetiqProjectId) { $FleetiqProjectId = "hermes" }

Write-Host "Installing FleetIQ Hermes plugin..."

# Matches Hermes' own default (hermes_constants.get_hermes_home): HERMES_HOME,
# else %LOCALAPPDATA%\hermes on Windows.
$HermesHome = $env:HERMES_HOME
if (-not $HermesHome) { $HermesHome = Join-Path $env:LOCALAPPDATA "hermes" }

$PluginDir = Join-Path $HermesHome "plugins\fleetiq"
New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null

Invoke-WebRequest -Uri "$RepoRaw/plugin.yaml" -OutFile (Join-Path $PluginDir "plugin.yaml")
Invoke-WebRequest -Uri "$RepoRaw/__init__.py" -OutFile (Join-Path $PluginDir "__init__.py")

# ── Wire credentials into $HermesHome\.env (idempotent upsert) ──────────────
$EnvFile = Join-Path $HermesHome ".env"
$lines = @()
if (Test-Path $EnvFile) { $lines = Get-Content $EnvFile }

function Set-EnvLine([string[]]$lines, [string]$name, [string]$value) {
    $prefix = "$name="
    $found = $false
    $result = $lines | ForEach-Object {
        if ($_ -like "$prefix*") { $found = $true; "$name=$value" } else { $_ }
    }
    if (-not $found) { $result += "$name=$value" }
    return $result
}

$lines = Set-EnvLine $lines "FLEETIQ_URL" $FleetiqUrl
$lines = Set-EnvLine $lines "FLEETIQ_API_KEY" $FleetiqApiKey
$lines = Set-EnvLine $lines "FLEETIQ_PROJECT_ID" $FleetiqProjectId
Set-Content -Path $EnvFile -Value $lines
Write-Host "wrote $EnvFile"

# ── Enable the plugin (Hermes plugins are opt-in) ────────────────────────────
if (Get-Command hermes -ErrorAction SilentlyContinue) {
    hermes plugins enable fleetiq
} else {
    Write-Host "hermes CLI not found on PATH — enable manually: hermes plugins enable fleetiq"
}

Write-Host ""
Write-Host "FleetIQ installed. Start a new Hermes session and it will appear on your dashboard."
Write-Host "  Events -> $FleetiqUrl"
