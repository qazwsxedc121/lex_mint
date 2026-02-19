@echo off
setlocal

set "API_PORT="
set "FRONTEND_PORT="
if exist .env (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_PORT= ^FRONTEND_PORT=" .env 2^>nul') do (
        if /I "%%a"=="API_PORT" set "API_PORT=%%b"
        if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
    )
)
if not defined FRONTEND_PORT (
    echo [ERROR] FRONTEND_PORT not set in .env
    endlocal
    exit /b 1
)
if not defined API_PORT (
    echo [ERROR] API_PORT not set in .env
    endlocal
    exit /b 1
)
for %%I in ("%CD%") do set "PROJECT_NAME=%%~nxI"
title %PROJECT_NAME% FE:%FRONTEND_PORT% ^| BE:%API_PORT%

powershell -NoProfile -ExecutionPolicy Bypass -File ".\scripts\start_single_window.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

endlocal & exit /b %EXIT_CODE%
