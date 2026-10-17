@echo off
REM ====================================================================
REM ClaudeGravity Windows CMD Launcher
REM Unterstützt alle Parameter, Farben und UTF-8-Zeichenkodierung
REM ====================================================================
setlocal
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul 2>nul

where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        py -3 "%~dp0loop.py" %*
        exit /b %ERRORLEVEL%
    )
    echo [!] FEHLER: Python 3.10+ wurde nicht im System-PATH gefunden.
    echo Bitte installiere Python von https://www.python.org und setze das Häkchen bei "Add Python to PATH".
    exit /b 1
)

python "%~dp0loop.py" %*
exit /b %ERRORLEVEL%
