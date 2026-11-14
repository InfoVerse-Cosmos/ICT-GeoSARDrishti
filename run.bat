@echo off
REM ============================================================
REM  GeoSAR Drishti - one-command local dev runner for Windows.
REM  Starts the FastAPI backend (:8000) and the Vite frontend
REM  (:5173) in two new windows. Close those windows to stop.
REM
REM    run.bat               install deps if needed, then run both
REM    run.bat --no-install  skip dependency install (fast restart)
REM ============================================================
setlocal

set "ROOT=%~dp0"
set "API_DIR=%ROOT%services\api"
set "WEB_DIR=%ROOT%apps\web"
set "API_PORT=8000"
set "WEB_PORT=5173"
set "DO_INSTALL=1"
if /I "%~1"=="--no-install" set "DO_INSTALL=0"

REM --- pick a Python (prefer 3.11, the SRS target) ---
set "PYLAUNCH="
py -3.11 -c "import sys" >nul 2>&1 && set "PYLAUNCH=py -3.11"
if not defined PYLAUNCH ( py -3 -c "import sys" >nul 2>&1 && set "PYLAUNCH=py -3" )
if not defined PYLAUNCH ( python -c "import sys" >nul 2>&1 && set "PYLAUNCH=python" )
if not defined PYLAUNCH (
  echo [geosar] Python not found. Install Python 3.11 from https://www.python.org/downloads/
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [geosar] npm not found. Install Node 18+ from https://nodejs.org/
  exit /b 1
)

REM --- backend: virtualenv ---
if not exist "%API_DIR%\.venv" (
  echo [geosar] Creating backend virtualenv...
  %PYLAUNCH% -m venv "%API_DIR%\.venv"
)

if "%DO_INSTALL%"=="1" (
  echo [geosar] Installing backend deps...
  "%API_DIR%\.venv\Scripts\python.exe" -m pip install --upgrade pip
  "%API_DIR%\.venv\Scripts\python.exe" -m pip install -r "%API_DIR%\requirements.txt"
  if errorlevel 1 (
    echo [geosar] Backend dependency install failed.
    echo [geosar] If your Python is very new, install Python 3.11, delete services\api\.venv, then re-run.
    exit /b 1
  )
)

if not exist "%API_DIR%\.env" if exist "%ROOT%.env.example" copy /Y "%ROOT%.env.example" "%API_DIR%\.env" >nul

REM --- frontend: deps + API url ---
if "%DO_INSTALL%"=="1" if not exist "%WEB_DIR%\node_modules" (
  echo [geosar] Installing frontend deps, first run may take a minute...
  pushd "%WEB_DIR%"
  call npm install --no-fund --no-audit
  popd
)
> "%WEB_DIR%\.env" echo VITE_API_BASE_URL=http://localhost:%API_PORT%

REM --- start both in their own windows ---
echo [geosar] Starting FastAPI on http://localhost:%API_PORT% ...
start "GeoSAR API" /D "%API_DIR%" cmd /k ".venv\Scripts\activate.bat && uvicorn app.main:app --host 0.0.0.0 --port %API_PORT%"

echo [geosar] Waiting a few seconds for the backend to warm up...
timeout /t 4 /nobreak >nul

echo [geosar] Starting Vite on http://localhost:%WEB_PORT% ...
start "GeoSAR Web" /D "%WEB_DIR%" cmd /k "npm run dev -- --port %WEB_PORT%"

echo.
echo [geosar] Both starting in separate windows.
echo [geosar]   API docs: http://localhost:%API_PORT%/docs
echo [geosar]   UI:       http://localhost:%WEB_PORT%
echo [geosar] The frontend auto-retries if the backend is still warming up.
echo [geosar] Close those two windows to stop the servers.
endlocal
