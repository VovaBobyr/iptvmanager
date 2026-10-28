param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Run: python -m venv .venv; .venv\Scripts\pip install -e '.[dev]'"
}

Set-Location -LiteralPath $ProjectRoot
& $Python -m uvicorn iptv_manager.app:app --host 0.0.0.0 --port $Port
