# Starts the AgentPay backend (8000) and frontend dev server (5173) in new windows.
# Backend runs from the project's Python virtual environment (backend/.venv).
# Usage:  ./dev.ps1
$root = $PSScriptRoot
$venvPy = "$root\backend\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
  Write-Host "No venv found - creating backend/.venv ..." -ForegroundColor Yellow
  python -m venv "$root\backend\.venv"
  & $venvPy -m pip install -q -r "$root\backend\requirements.txt"
}

Write-Host "Starting backend (venv) on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "`$env:PYTHONPATH='$root\backend'; cd '$root\backend'; & '$venvPy' run.py"
)

Write-Host "Starting frontend on http://127.0.0.1:5173 ..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit", "-Command",
  "cd '$root\frontend'; npm run dev"
)

Write-Host "`nOpen http://127.0.0.1:5173 and click 'Run agent economy demo'." -ForegroundColor Green
