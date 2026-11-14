@echo off
REM ---------------------------------------------------------------------------
REM GeoSAR Drishti - one-command "bring your own data" analyser (Windows).
REM   1. Put your NISAR L2 GCOV .h5 granules in the DATA folder (see DATA\README.md).
REM   2. Run analyze.bat
REM It auto-detects the area, builds the analysis pack, and starts the app.
REM ---------------------------------------------------------------------------
setlocal enabledelayedexpansion
set "ROOT=%~dp0"
set "DATA_DIR=%ROOT%DATA"
REM .env (GEOSAR_DATA_DIR) can point at a folder on another drive, e.g. D:/Hackathon Files
for /f "usebackq delims=" %%D in (`python "%ROOT%scripts\print_data_dir.py" 2^>nul`) do set "DATA_DIR=%%D"
set "PVENV=%ROOT%scripts\.venv"

REM --- 1. check for granules -------------------------------------------------
set "FOUND="
for %%F in ("%DATA_DIR%\*.h5") do set "FOUND=1"
if not defined FOUND (
  echo [analyze] No NISAR .h5 granules found in %DATA_DIR%
  echo [analyze] Download NISAR L2 GCOV .h5 files for your area ^(NASA Earthdata/ASF or ISRO Bhoonidhi^),
  echo [analyze] copy them into the DATA folder, then run analyze.bat again. See DATA\README.md.
  exit /b 1
)
echo [analyze] Found NISAR granule(s) in %DATA_DIR%

REM --- 2. processing environment ---------------------------------------------
where python >nul 2>nul || ( echo [analyze] python not found. Install Python 3.11+. & exit /b 1 )
if not exist "%PVENV%" (
  echo [analyze] Creating processing environment ^(first run only^)...
  python -m venv "%PVENV%"
)
call "%PVENV%\Scripts\activate.bat"
echo [analyze] Installing processing dependencies...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet numpy h5py pyproj || ( echo [analyze] Could not install core deps. Install Python 3.11, delete scripts\.venv, retry. & exit /b 1 )
python -m pip install --quiet scikit-learn || echo [analyze] scikit-learn unavailable - GMM regimes will be skipped.

REM --- 3. build the pack -----------------------------------------------------
REM No AOI_ID/AOI_NAME needed: each track/frame stack in the folder becomes its own area automatically.
set "AOI_ARGS="
if defined AOI_ID set "AOI_ARGS=--aoi-id %AOI_ID%"
if defined AOI_NAME set "AOI_ARGS=%AOI_ARGS% --name "%AOI_NAME%""
echo [analyze] Building the analysis pack (area auto-detected from the granules)...
python "%ROOT%scripts\byod_build_aoi.py" %AOI_ARGS% --with-regimes --with-osm
call deactivate

REM --- 4. start the app ------------------------------------------------------
echo [analyze] Pack built. Starting the app...
call "%ROOT%run.bat"
endlocal
