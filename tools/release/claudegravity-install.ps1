<#
Installiert ClaudeGravity als eigenständiges Programm (ohne Python) unter Windows, in PowerShell:

  irm https://github.com/gb-web-de/claudegravity-loop/releases/latest/download/claudegravity-install.ps1 | iex

Lädt das Archiv vom GitHub-Release, prüft die SHA-256-Summe und startet `claudegravity.exe install`:
Programm nach %LOCALAPPDATA%\ClaudeGravity\bin (im Benutzer-PATH), MCP-Server und Skill in alle gefundenen Clients.
$env:CLAUDEGRAVITY_VERSION = 'v1.6.0' nimmt eine bestimmte Version, $env:CLAUDEGRAVITY_ARCHIVE ein lokales Archiv.
Als Datei mit Parametern: .\claudegravity-install.ps1 -Version v1.6.0 -Archive <zip> -InstallArgs '--no-path'
#>
param(
    [string]$Version = $env:CLAUDEGRAVITY_VERSION,
    [string]$Archive = $env:CLAUDEGRAVITY_ARCHIVE,
    [string[]]$InstallArgs = @()
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = 'gb-web-de/claudegravity-loop'
# Windows auf ARM führt das x64-Programm über die eingebaute Emulation aus
$asset = 'claudegravity-windows-x86_64.zip'
# Der Release-Workflow trägt hier die Version des Releases ein; aus dem Repository geht es zur neuesten
$releaseTag = '__RELEASE_TAG__'
if ($releaseTag -like '__*') { $releaseTag = '' }
if (-not $Version) { $Version = $releaseTag }
if ($Version) { $base = "https://github.com/$repo/releases/download/$Version" }
else { $base = "https://github.com/$repo/releases/latest/download" }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ('claudegravity-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    $zip = Join-Path $tmp $asset
    if ($Archive) {
        Copy-Item -LiteralPath $Archive -Destination $zip
    }
    else {
        # Windows PowerShell 5.1 nimmt sonst ggf. kein TLS 1.2
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        Write-Host "[*] Lade $base/$asset"
        Invoke-WebRequest -UseBasicParsing -Uri "$base/$asset" -OutFile $zip
        $sums = Join-Path $tmp 'SHA256SUMS'
        Invoke-WebRequest -UseBasicParsing -Uri "$base/SHA256SUMS" -OutFile $sums
        $line = Get-Content -LiteralPath $sums | Where-Object { ($_ -split '\s+')[1] -in @($asset, "*$asset") } | Select-Object -First 1
        if (-not $line) { throw "$asset steht nicht in SHA256SUMS." }
        $expected = ($line -split '\s+')[0]
        $actual = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash
        if ($actual -ne $expected.ToUpper()) { throw "Prüfsumme von $asset stimmt nicht." }
    }
    Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
    $exe = Join-Path $tmp 'claudegravity\claudegravity.exe'
    & $exe install @InstallArgs
    # Kein exit: über "irm | iex" würde es das PowerShell-Fenster schließen
    if ($LASTEXITCODE -ne 0) { Write-Error "claudegravity install endete mit Code $LASTEXITCODE." }
}
finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
