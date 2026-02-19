@echo off
setlocal enabledelayedexpansion

echo ========================================
echo    Stop All Services
echo ========================================
echo.

set "API_PORT="
set "FRONTEND_PORT="
if exist .env (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_PORT= ^FRONTEND_PORT=" .env 2^>nul') do (
        if /I "%%a"=="API_PORT" set "API_PORT=%%b"
        if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
    )
)

echo [1/3] Stopping backend by port...
if defined API_PORT (
    call :kill_by_port %API_PORT% backend
) else (
    echo     API_PORT not set in .env, skip port stop
)

echo.
echo [2/3] Stopping frontend by port...
if defined FRONTEND_PORT (
    call :kill_by_port %FRONTEND_PORT% frontend
) else (
    echo     FRONTEND_PORT not set in .env, skip frontend port stop
)

echo.
echo [3/3] Stopping legacy titled windows...
taskkill /F /FI "WINDOWTITLE eq LangGraph Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq LangGraph Frontend*" >nul 2>&1
echo     Done

echo.
echo ========================================
echo    All Services Stopped
echo ========================================
echo.
pause
endlocal
exit /b 0

:kill_by_port
set "TARGET_PORT=%~1"
set "TARGET_NAME=%~2"
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":%TARGET_PORT% " ^| findstr LISTENING') do (
    set "FOUND=1"
    taskkill /F /PID %%p >nul 2>&1
    if !errorlevel! equ 0 (
        echo     Stopped !TARGET_NAME! pid %%p (port !TARGET_PORT!)
    ) else (
        echo     Failed to stop pid %%p (port !TARGET_PORT!)
    )
)
if "!FOUND!"=="0" (
    echo     No process found on port !TARGET_PORT!
)
exit /b 0
