# Construye el instalador NSIS de Mobile Recovery Lab en Windows.
# Requisitos: Node.js 20+, Python 3.11+ (en PATH), Git.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> Entorno virtual de Python" -ForegroundColor Cyan
if (-not (Test-Path "backend\.venv")) { python -m venv backend\.venv }
& backend\.venv\Scripts\python.exe -m pip install --upgrade pip
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Write-Host "==> Pruebas del backend" -ForegroundColor Cyan
Push-Location backend
& .\.venv\Scripts\python.exe -m unittest discover -s tests -t .
Write-Host "==> Congelando backend con PyInstaller" -ForegroundColor Cyan
& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean mrlab-backend.spec
Pop-Location

Write-Host "==> Dependencias de Node" -ForegroundColor Cyan
npm ci

Write-Host "==> Compilación y empaquetado NSIS" -ForegroundColor Cyan
npm run dist:win

Write-Host "Instalador generado en .\release\" -ForegroundColor Green
