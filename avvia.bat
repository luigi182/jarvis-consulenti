@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py -3"
) else (
  set "PYTHON=python"
)

%PYTHON% --version >nul 2>nul
if errorlevel 1 (
  echo Python 3 non trovato. Installalo da https://www.python.org/downloads/ e riprova.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  %PYTHON% -m venv .venv
  if errorlevel 1 goto error
)

call ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto error

start "Jarvis Consulenti" http://127.0.0.1:5000
".venv\Scripts\python.exe" server.py
if errorlevel 1 goto error
exit /b 0

:error
echo.
echo Avvio non riuscito. Verifica Python e la connessione internet per installare le dipendenze.
pause
exit /b 1
