$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $root ".env"
$outputPath = Join-Path $root "config\env.local.dpapi"

if (-not (Test-Path $envPath)) {
    throw "No .env file found at $envPath"
}

New-Item -ItemType Directory -Path (Split-Path -Parent $outputPath) -Force | Out-Null
$plain = Get-Content -LiteralPath $envPath -Raw
$secure = ConvertTo-SecureString -String $plain -AsPlainText -Force
ConvertFrom-SecureString -SecureString $secure | Set-Content -LiteralPath $outputPath -Encoding UTF8

Write-Host "Encrypted .env to config\env.local.dpapi using Windows DPAPI for the current user."
