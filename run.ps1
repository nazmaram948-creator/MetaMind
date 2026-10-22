# SkillShift MY, Windows: one command from the repository root.
#   powershell -ExecutionPolicy Bypass -File run.ps1
# First run: creates .venv, installs Python packages, installs and builds the
# frontend. Then serves the app and the API on http://localhost:8000.
param([int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if ($PSScriptRoot.Length -gt 80) {
  Write-Warning "This folder path is long ($($PSScriptRoot.Length) characters). PyTorch has deep file paths, so pip may fail with a 'Long Path' error. Clone into a short folder such as C:\dev\MetaMind if that happens."
}

$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
  Write-Host "Creating .venv ..."
  if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { py -3 -m venv .venv }
  } else {
    python -m venv .venv
  }
  if (-not (Test-Path $py)) { throw "Could not create .venv. Install Python 3.11 from python.org and retry." }
}
& $py -c "import sys; sys.exit(sys.version_info < (3, 10))"
if ($LASTEXITCODE -ne 0) { throw "Python 3.10+ is needed (3.11 recommended). Delete .venv and retry with a newer Python." }

Write-Host "Installing Python packages (first run downloads ~300 MB) ..."
& $py -m pip install -q --disable-pip-version-check -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

if (Get-Command npm -ErrorAction SilentlyContinue) {
  Push-Location frontend
  try {
    if (-not (Test-Path node_modules)) { npm ci --no-audit --no-fund; if ($LASTEXITCODE -ne 0) { throw "npm ci failed" } }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed" }
  } finally { Pop-Location }
} else {
  Write-Warning "npm not found: install Node.js 20+ to build the frontend. The API still starts."
}

$env:ENGINE_MODE = "true"
Write-Host ""
Write-Host "SkillShift MY: open http://localhost:$Port   (Ctrl+C to stop)"
& $py -m uvicorn backend.app.main:app --host 127.0.0.1 --port $Port
