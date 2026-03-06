@echo off
setlocal

cd /d "%~dp0"
set "LEX_MINT_RUNTIME_ROOT=%CD%"

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
  )
)

set "API_HOST="
set "API_PORT="
if exist ".env" (
  for /f "tokens=1,* delims==" %%a in ('findstr /r "^API_HOST= ^API_PORT=" ".env" 2^>nul') do (
    if /I "%%a"=="API_HOST" set "API_HOST=%%b"
    if /I "%%a"=="API_PORT" set "API_PORT=%%b"
  )
)

if not defined API_HOST set "API_HOST=127.0.0.1"
if not defined API_PORT set "API_PORT=18000"

if not exist "backend\lex_mint_backend.exe" (
  echo [ERROR] backend\lex_mint_backend.exe not found
  exit /b 1
)

echo Starting Lex Mint on %API_HOST%:%API_PORT%...
start "LexMint" /min "%CD%\backend\lex_mint_backend.exe"

set "WAIT_SCRIPT=$url='http://%API_HOST%:%API_PORT%/api/health';$ok=$false;for($i=0;$i -lt 40;$i++){try{$r=Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 2;if($r.StatusCode -eq 200){$ok=$true;break}}catch{};Start-Sleep -Milliseconds 250};if(-not $ok){exit 1}"
powershell -NoProfile -ExecutionPolicy Bypass -Command "%WAIT_SCRIPT%"
if errorlevel 1 (
  echo [WARN] Backend health check did not pass in time.
)

start "" "http://%API_HOST%:%API_PORT%"

echo.
echo Lex Mint is starting.
echo - App:    http://%API_HOST%:%API_PORT%
echo - Health: http://%API_HOST%:%API_PORT%/api/health
echo.
echo To stop the service, run stop_lex_mint.bat

endlocal
