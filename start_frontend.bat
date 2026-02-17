@echo off
REM ================================================================================
REM 仅启动前端开发服务器
REM ================================================================================

echo.
echo ================================================================================
echo 启动前端开发服务器
echo ================================================================================
echo.

set "FRONTEND_PORT="
if exist .env (
    for /f "tokens=1,* delims==" %%a in ('findstr /r "^FRONTEND_PORT=" .env 2^>nul') do (
        if /I "%%a"=="FRONTEND_PORT" set "FRONTEND_PORT=%%b"
    )
)
if not defined FRONTEND_PORT (
    echo [WARNING] FRONTEND_PORT not set in .env, fallback to 5173
    set "FRONTEND_PORT=5173"
)

cd frontend
echo 前端地址: http://localhost:%FRONTEND_PORT%
npm run dev -- --host 0.0.0.0 --port %FRONTEND_PORT% --strictPort
