@echo off
setlocal

cd /d "%~dp0"

set "API_PORT="
set "FRONTEND_PORT="
if exist ".env" (
  for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_PORT= ^FRONTEND_PORT=" ".env" 2^>nul') do (
    if /I "%%a"=="API_PORT" set "API_PORT=%%b"
    if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
  )
)

if not defined API_PORT set "API_PORT=18000"
if not defined FRONTEND_PORT set "FRONTEND_PORT=18001"

echo Stopping processes on ports %API_PORT% and %FRONTEND_PORT%...

for %%P in (%API_PORT% %FRONTEND_PORT%) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr :%%P ^| findstr LISTENING') do (
    taskkill /F /PID %%I >nul 2>&1
  )
)

echo Done.
endlocal
