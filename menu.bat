@echo off
setlocal enabledelayedexpansion
cls
echo.
echo     ======================================
echo       LangGraph Agent Web Interface
echo     ======================================
echo       AI Chat System powered by DeepSeek
echo     ======================================
echo.
echo     Please select an option:
echo.
echo     [1] First-time Installation (install.bat)
echo     [2] Start Services (start.bat)
echo     [3] Stop Services (stop.bat)
echo     [4] Check Status (status.bat)
echo     [5] Open Conversations Folder
echo     [6] Open Browser
echo     [0] Exit
echo.
set /p choice=Enter your choice (0-6):

if "%choice%"=="1" call install.bat
if "%choice%"=="2" call start.bat
if "%choice%"=="3" call stop.bat
if "%choice%"=="4" call status.bat
if "%choice%"=="5" explorer conversations
if "%choice%"=="6" (
    set "FRONTEND_PORT="
    if exist .env (
        for /f "tokens=1,* delims==" %%a in ('findstr /r "^FRONTEND_PORT=" .env 2^>nul') do (
            if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
        )
    )
    if not defined FRONTEND_PORT set "FRONTEND_PORT=5173"
    start http://localhost:!FRONTEND_PORT!
    echo Browser opened
    pause
)
if "%choice%"=="0" exit

if not "%choice%"=="0" (
    echo.
    pause
    cls
    goto :eof
)
