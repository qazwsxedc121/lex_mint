@echo off
setlocal

set "ROOT_DIR=%~dp0"
:: Remove trailing backslash
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"

echo.
echo ===============================================================================
echo Update Python and Node Dependencies
echo ===============================================================================
echo.

if not exist "%ROOT_DIR%\venv" (
    echo venv not found at %ROOT_DIR%\venv
    echo Create it first: python -m venv venv
    exit /b 1
)

echo [1/3] Upgrading pip...
"%ROOT_DIR%\venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
echo       done
echo.

echo [2/3] Updating Python dependencies...
"%ROOT_DIR%\venv\Scripts\pip.exe" install --upgrade -r "%ROOT_DIR%\requirements.txt"
if errorlevel 1 exit /b 1
echo       done
echo.

if not exist "%ROOT_DIR%\frontend" (
    echo frontend directory not found at %ROOT_DIR%\frontend
    exit /b 1
)

echo [3/3] Updating Node dependencies...
cd /d "%ROOT_DIR%\frontend"
call npm install
if errorlevel 1 exit /b 1
call npm update
if errorlevel 1 exit /b 1
echo       done
echo.

endlocal
