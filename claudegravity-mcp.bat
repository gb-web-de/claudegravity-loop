@echo off
REM ====================================================================
REM ClaudeGravity MCP Server Windows CMD Launcher
REM ====================================================================
setlocal
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>nul

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -3 "%~dp0mcp_server.py" %*
        exit /b %ERRORLEVEL%
    )
    echo [!] FEHLER: Python 3.10+ wurde nicht im System-PATH gefunden.
    exit /b 1
)

python "%~dp0mcp_server.py" %*
exit /b %ERRORLEVEL%
