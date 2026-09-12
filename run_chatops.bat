@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   AZURE CLOUD CHATOPS & LIVE SRE AI (TELEGRAM / CLI)
echo ========================================================

set "AGENT_PYTHON=C:\Users\s3cr3t\My Drive (baongdqu@gmail.com)\zzz kỹ năng tech - ai (separator)\( ) project my agent\.venv\Scripts\python.exe"

if "%1"=="mcp" (
    echo [Kiem tra MCP Server qua CLI...]
    "%AGENT_PYTHON%" mcp_server\devops_mcp_server.py
) else if "%1"=="app" (
    echo [Chay thu nghiem Web App URL Shortener tai Local...]
    "%AGENT_PYTHON%" -m uvicorn app_url_shortener.main:app --host 127.0.0.1 --port 8000 --reload
) else if "%1"=="ai-local" (
    echo [Chay thu nghiem AI Telegram Bot + Healthcheck tai Local...]
    "%AGENT_PYTHON%" app_ai_telegram\bot\telegram_runner.py
) else if "%1"=="ai-deploy" (
    echo [Trien khai ca Web App va AI Bot tu Local len Azure ACA...]
    "%AGENT_PYTHON%" deploy_local.py
) else (
    echo [Cach su dung:]
    echo   run_chatops.bat mcp        : Kiem tra chay Azure DevOps MCP Server
    echo   run_chatops.bat app        : Chay thu nghiem URL Shortener tai localhost:8000
    echo   run_chatops.bat ai-local   : Chay thu nghiem AI Telegram Bot Server tai Local
    echo   run_chatops.bat ai-deploy  : Dong goi va Deploy AI Telegram Bot len Azure ACA
    echo.
    echo Vui long chon che do chay!
)

endlocal
