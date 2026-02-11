@echo off
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0"

echo.
echo ===============================================================================
echo Install/Update Python and Node Dependencies
echo ===============================================================================
echo.

if not exist "%ROOT_DIR%venv\Scripts\python.exe" (
  echo venv not found at "%ROOT_DIR%venv"
  echo Create it first (example): py -3 -m venv venv
  exit /b 1
)

echo [1/3] Upgrading pip...
"%ROOT_DIR%venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
echo       done
echo.

echo [2/3] Updating Python dependencies...
"%ROOT_DIR%venv\Scripts\pip.exe" install --upgrade -r "%ROOT_DIR%requirements.txt"
if errorlevel 1 exit /b 1
echo       done
echo.

if not exist "%ROOT_DIR%frontend\" (
  echo frontend directory not found at "%ROOT_DIR%frontend"
  exit /b 1
)

echo [3/3] Updating Node dependencies...
pushd "%ROOT_DIR%frontend"
call npm install
if errorlevel 1 (
  popd
  exit /b 1
)
call npm update
if errorlevel 1 (
  popd
  exit /b 1
)
popd
echo       done
