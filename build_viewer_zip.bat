@echo off
setlocal
cd /d "%~dp0"

set "SEVEN_ZIP=C:\Program Files\7-Zip\7z.exe"
if not exist "%SEVEN_ZIP%" (
  echo [Error] 7-Zip not found at "%SEVEN_ZIP%".
  exit /b 1
)

set "OUT_DIR=%~dp0dist_viewer"
if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%i"
set "ZIP_FILE=%OUT_DIR%\viewer_app_portable_%TS%.zip"
"%SEVEN_ZIP%" a -tzip -mx0 -aoa "%ZIP_FILE%" "%~dp0.venv_viewer" "%~dp0viewer_app.py" "%~dp0src" "%~dp0icons" "%~dp0run_viewer_app.bat" "%~dp0requirements_viewer.txt"
