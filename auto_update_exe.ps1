#Requires -Version 5.1
$ErrorActionPreference = "Continue"
Set-Location -Path $PSScriptRoot

# ---------------------------------------------------------------
# WATCHER EN MODE POLLING — sans Register-ObjectEvent
# Evite tous les faux positifs du mode evenements.
# ---------------------------------------------------------------

$WATCH_DIR  = $PSScriptRoot
$COOLDOWN_S = 5
$POLL_S     = 2

function Get-SourceFiles {
    Get-ChildItem -Path $WATCH_DIR -File |
        Where-Object {
            $_.Extension.ToLowerInvariant() -eq '.py' -and
            $_.Name -notlike '*auto_update*'
        }
}

function Build-Exe {
    Write-Host ""
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Build en cours..." -ForegroundColor Cyan
    $logPath = Join-Path $WATCH_DIR "build_log.txt"
    & py -m PyInstaller --noconfirm --onefile --windowed main.py --name Lithotherapie 2>&1 |
        Tee-Object -FilePath $logPath | Out-Null
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0 -and (Test-Path ".\dist\Lithotherapie.exe")) {
        Copy-Item ".\dist\Lithotherapie.exe" ".\Lithotherapie.exe" -Force
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] EXE mis a jour : .\Lithotherapie.exe" -ForegroundColor Green
    } else {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Echec du build (code $exitCode). Voir : $logPath" -ForegroundColor Red
    }
}

Write-Host "Watcher demarre (polling toutes les ${POLL_S}s sur *.py)." -ForegroundColor White
Write-Host "Ctrl+C pour arreter."

$snapshot = @{}
foreach ($f in Get-SourceFiles) { $snapshot[$f.FullName] = $f.LastWriteTimeUtc }

$lastBuildTime = [DateTime]::MinValue

# Premier build immediat.
Build-Exe
$lastBuildTime = (Get-Date).ToUniversalTime()
$snapshot = @{}
foreach ($f in Get-SourceFiles) { $snapshot[$f.FullName] = $f.LastWriteTimeUtc }

while ($true) {
    Start-Sleep -Seconds $POLL_S
    $changed = $false ; $changedName = ""
    foreach ($f in Get-SourceFiles) {
        $prev = $snapshot[$f.FullName]
        if ($null -eq $prev -or $f.LastWriteTimeUtc -gt $prev) {
            $changed = $true ; $changedName = $f.Name
            $snapshot[$f.FullName] = $f.LastWriteTimeUtc
        }
    }
    if (-not $changed) { continue }
    $wait = $COOLDOWN_S - ((Get-Date).ToUniversalTime() - $lastBuildTime).TotalSeconds
    if ($wait -gt 0) {
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $changedName modifie (cooldown $([math]::Round($wait))s)." -ForegroundColor DarkGray
        continue
    }
    Build-Exe
    $lastBuildTime = (Get-Date).ToUniversalTime()
    $snapshot = @{}
    foreach ($f in Get-SourceFiles) { $snapshot[$f.FullName] = $f.LastWriteTimeUtc }
}

