@echo off
setlocal

cd /d "%~dp0"

set "API_PORT="
if exist ".env" (
  for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_PORT=" ".env" 2^>nul') do (
    if /I "%%a"=="API_PORT" set "API_PORT=%%b"
  )
)

if not defined API_PORT set "API_PORT=18000"

echo Stopping process on port %API_PORT%...

for /f "tokens=5" %%I in ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') do (
  taskkill /F /PID %%I >nul 2>&1
)

echo Done.
endlocal
