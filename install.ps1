# ====================================================================
# ClaudeGravity Installer (Windows PowerShell)
# Trägt den MCP-Server in alle gefundenen Clients ein und legt die
# globalen Befehle claudegravity, claudegravity-loop, claudegravity-mcp an.
#   .\install.ps1               installieren / aktualisieren
#   .\install.ps1 --uninstall   entfernen
#   .\install.ps1 --status      Status anzeigen
# ====================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$pythonArgs = @()
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command py -ErrorAction SilentlyContinue
    $pythonArgs = @("-3")
    if (-not $pythonCmd) {
        Write-Error "[!] FEHLER: Python 3.10+ wurde nicht im System-PATH gefunden."
        Write-Host "Bitte installiere Python von https://www.python.org und aktiviere 'Add Python to PATH'."
        exit 1
    }
}

$scriptPath = Join-Path $PSScriptRoot "install.py"
& $pythonCmd.Source @pythonArgs $scriptPath @args
exit $LASTEXITCODE
