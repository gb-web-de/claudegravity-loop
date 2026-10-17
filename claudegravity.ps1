# ====================================================================
# ClaudeGravity Windows PowerShell Launcher
# Unterstützt alle Parameter, Farben und UTF-8-Zeichenkodierung
# ====================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    if (-not $pythonCmd) {
        Write-Error "[!] FEHLER: Python 3.10+ wurde nicht im System-PATH gefunden."
        Write-Host "Bitte installiere Python von https://www.python.org und aktiviere 'Add Python to PATH'."
        exit 1
    }
}

$scriptPath = Join-Path $PSScriptRoot "loop.py"
& $pythonCmd.Source $scriptPath @args
exit $LASTEXITCODE
