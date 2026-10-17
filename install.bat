@echo off
REM ====================================================================
REM ClaudeGravity Installer (Windows CMD)
REM Traegt den MCP-Server in alle gefundenen Clients ein und legt die
REM globalen Befehle claudegravity, claudegravity-loop, claudegravity-mcp an.
REM   install.bat               installieren / aktualisieren
REM   install.bat --uninstall   entfernen
REM   install.bat --status      Status anzeigen
REM ====================================================================
setlocal
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>nul

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -3 "%~dp0install.py" %*
        exit /b %ERRORLEVEL%
    )
    echo [!] FEHLER: Python 3.10+ wurde nicht im System-PATH gefunden.
    echo Bitte installiere Python von https://www.python.org und setze das Häkchen bei "Add Python to PATH".
    exit /b 1
)

python "%~dp0install.py" %*
exit /b %ERRORLEVEL%
