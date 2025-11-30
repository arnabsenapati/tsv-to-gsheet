# PowerShell helper to run the TSV to Excel Watcher app
param(
    [string]$PythonPath = ".\\venv\\Scripts\\python.exe",
    [string]$Entry = "main.py"
)

Set-Location -Path "$PSScriptRoot"

if (-Not (Test-Path $PythonPath)) {
    Write-Host "Python not found at $PythonPath"
    exit 1
}

& $PythonPath $Entry
