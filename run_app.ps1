# PowerShell helper to run the TSV to Excel Watcher app
param(
    [string]$PythonPath = ".\.venv\Scripts\python.exe",
    [string]$Entry = "main.py"
)

Set-Location -Path "$PSScriptRoot"

# Fallback to system python if venv not found
if (-Not (Test-Path $PythonPath)) {
    Write-Host "Python not found at $PythonPath, falling back to system python"
    $PythonPath = "python"
}

& $PythonPath $Entry
