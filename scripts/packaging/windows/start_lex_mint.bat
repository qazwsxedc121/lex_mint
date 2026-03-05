@echo off
setlocal

cd /d "%~dp0"
set "LEX_MINT_RUNTIME_ROOT=%CD%"

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
  )
)

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

if not exist "backend\lex_mint_backend.exe" (
  echo [ERROR] backend\lex_mint_backend.exe not found
  exit /b 1
)
if not exist "frontend\lex_mint_frontend.exe" (
  echo [ERROR] frontend\lex_mint_frontend.exe not found
  exit /b 1
)

echo Starting Lex Mint backend on %API_PORT%...
start "LexMint Backend" /min "%CD%\backend\lex_mint_backend.exe"

echo Starting Lex Mint frontend static server on %FRONTEND_PORT%...
start "LexMint Frontend" /min "%CD%\frontend\lex_mint_frontend.exe"

set "WAIT_SCRIPT=$url='http://127.0.0.1:%API_PORT%/api/health';$ok=$false;for($i=0;$i -lt 40;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2;if($r.StatusCode -eq 200){$ok=$true;break}}catch{};Start-Sleep -Milliseconds 250};if(-not $ok){exit 1}"
powershell -NoProfile -ExecutionPolicy Bypass -Command "%WAIT_SCRIPT%"
if errorlevel 1 (
  echo [WARN] Backend health check did not pass in time.
)

start "" "http://127.0.0.1:%FRONTEND_PORT%"

echo.
echo Lex Mint is starting.
echo - Backend:  http://127.0.0.1:%API_PORT%
echo - Frontend: http://127.0.0.1:%FRONTEND_PORT%
echo.
echo To stop both services, run stop_lex_mint.bat

endlocal
