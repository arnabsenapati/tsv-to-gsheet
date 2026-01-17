@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv_viewer\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [Error] venv python not found at "%PYTHON%".
  echo Create it with: python -m venv .venv_viewer
  exit /b 1
)

"%PYTHON%" "%~dp0viewer_app.py" %*
