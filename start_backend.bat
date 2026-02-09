@echo off
REM ================================================================================
REM 仅启动后端 API 服务器（调试模式 - 超详细日志）
REM 端口配置：在 .env 文件中设置 API_PORT
REM ================================================================================

echo.
echo ================================================================================
echo 启动后端 API 服务器 (调试模式)
echo ================================================================================
echo.

REM 读取 .env 中的端口配置
if exist .env (
    for /f "tokens=1,2 delims==" %%a in ('findstr /r "^API_PORT=" .env 2^>nul') do set API_PORT=%%b
)
if not defined API_PORT (
    echo [ERROR] API_PORT not set in .env
    pause
    exit /b 1
)

REM 清理端口
echo [1/2] 清理端口 %API_PORT%...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%API_PORT% ^| findstr LISTENING') do (
    echo       杀死进程 %%a
    taskkill /F /PID %%a 2>nul
)
echo      完成
echo.

REM 激活虚拟环境并启动
echo [2/2] 启动服务器...
echo.
echo ================================================================================
echo 服务器地址: http://0.0.0.0:%API_PORT%
echo 前端连接: http://localhost:%API_PORT%
echo API 文档: http://localhost:%API_PORT%/docs
echo.
echo 提示: 可在 .env 文件中修改 API_PORT 更改端口
echo ================================================================================
echo.

call venv\Scripts\activate.bat
python run_server_debug.py
