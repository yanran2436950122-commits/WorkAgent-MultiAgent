$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
Set-Location -Path $ProjectRoot

# Dependency location:
# - Default: project-local .venv for simple local development.
# - Optional: set WORKAGENT_VENV to keep dependencies outside the project,
#   for example D:\pyProject\.venvs\workagent-multiagent.
# Keeping dependencies outside the repository makes cleanup, migration, and
# GitHub publishing safer because no running Python process locks project files.
$VenvPath = if ($env:WORKAGENT_VENV) {
    $env:WORKAGENT_VENV
} elseif ($env:WORKPLACE_TASK_VENV) {
    $env:WORKPLACE_TASK_VENV
} else {
    Join-Path $ProjectRoot ".venv"
}
$PythonPath = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $PythonPath)) {
    Write-Host "Creating virtual environment..."
    New-Item -ItemType Directory -Path (Split-Path -Parent $VenvPath) -Force | Out-Null
    python -m venv $VenvPath
}

& $PythonPath -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('streamlit') else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..."
    & $PythonPath -m pip install -r requirements.txt
}

Write-Host "Starting WorkAgent-MultiAgent at http://localhost:8501"
& $PythonPath -m streamlit run app.py --server.port 8501
