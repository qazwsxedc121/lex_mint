@echo off
setlocal
REM ============================================================================
REM Start frontend dev server only
REM Port source: FRONTEND_PORT in .env
REM ============================================================================

echo.
echo ============================================================================
echo Start frontend dev server
echo ============================================================================
echo.

set "FRONTEND_PORT="
if exist ".env" (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^FRONTEND_PORT=" ".env" 2^>nul') do (
        if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
    )
)

if not defined FRONTEND_PORT (
    echo [ERROR] FRONTEND_PORT not set in .env
    endlocal
    exit /b 1
)

if not exist "frontend\package.json" (
    echo [ERROR] frontend\package.json not found
    endlocal
    exit /b 1
)

pushd "frontend"
echo Frontend URL: http://localhost:%FRONTEND_PORT%
npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT% --strictPort
set "EXIT_CODE=%ERRORLEVEL%"
popd

endlocal & exit /b %EXIT_CODE%
