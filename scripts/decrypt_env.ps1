$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$inputPath = Join-Path $root "config\env.local.dpapi"
$envPath = Join-Path $root ".env"

if (-not (Test-Path $inputPath)) {
    throw "No encrypted env file found at $inputPath"
}

$encrypted = Get-Content -LiteralPath $inputPath -Raw
$secure = ConvertTo-SecureString -String $encrypted
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

Set-Content -LiteralPath $envPath -Value $plain -Encoding UTF8
Write-Host "Restored .env from config\env.local.dpapi."
