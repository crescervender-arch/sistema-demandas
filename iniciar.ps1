# Inicia o Sistema de Controle de Demandas (Windows / PowerShell)
# Uso:  clique direito > "Executar com PowerShell"  OU  .\iniciar.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Criando ambiente virtual..." -ForegroundColor Cyan
    py -m venv .venv
}

Write-Host "Instalando dependencias..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --quiet --upgrade pip
# Localmente usamos SQLite (nao precisa de psycopg). Em producao, instale requirements.txt.
& .\.venv\Scripts\python.exe -m pip install --quiet "fastapi==0.115.6" "uvicorn[standard]==0.34.0" "SQLAlchemy==2.0.36"

Write-Host ""
Write-Host "Servidor rodando em:  http://localhost:8000" -ForegroundColor Green
Write-Host "Login master:  master@bbz.adv.br  /  master123" -ForegroundColor Yellow
Write-Host "(Ctrl+C para parar)" -ForegroundColor DarkGray
Write-Host ""

& .\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
