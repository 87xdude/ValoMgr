param(
  [switch]$OneFile     = $false,                       # false => OneDir (empfohlen), true => OneFile
  [string]$Name        = "AccountMgr",                 # EXE/Ordner-Name (wird zu AccountMgr.exe)
  [string]$IconICO     = "app\resources\exe_logo.ico", # EXE-Icon
  [switch]$Console     = $false,                       # true => Konsole anzeigen
  [switch]$Clean       = $true,                        # build/dist aufräumen & --clean
  [switch]$Slim        = $true,                        # kleineres Bundle (kein --collect-all PySide6)
  [switch]$UseUPX      = $false,                       # UPX-Komprimierung
  [switch]$ExcludeHeavy= $true,                        # große, unnötige Module ausschließen
  [string]$Entry       = "app\__main__.py"             # Entry-Skript (Paketstart, rel. Importe ok)
)

$ErrorActionPreference = "Stop"
Write-Host "=== Build-Skript gestartet ===" -ForegroundColor Cyan
if ($PSScriptRoot) { Set-Location $PSScriptRoot }
try { Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force } catch { }

# Python finden
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) { $pyCmd = Get-Command py -ErrorAction SilentlyContinue }
if (-not $pyCmd) { throw "Python nicht gefunden. Bitte Python 3.x installieren." }
Write-Host "Python: $($pyCmd.Source)" -ForegroundColor Green

# venv anlegen/aktivieren
if (-not (Test-Path ".venv")) {
  Write-Host "Erstelle virtuelle Umgebung .venv ..." -ForegroundColor Cyan
  if ($pyCmd.Name -eq "py.exe") { & $pyCmd.Source -3 -m venv .venv } else { & $pyCmd.Source -m venv .venv }
}
. .\.venv\Scripts\Activate.ps1
Write-Host "venv aktiv: $((Get-Command python).Source)" -ForegroundColor Green

# pip/requirements/PyInstaller
Write-Host "pip aktualisieren ..." -ForegroundColor Cyan
python -m pip install --upgrade pip
if (Test-Path "requirements.txt") {
  Write-Host "requirements.txt installieren ..." -ForegroundColor Cyan
  python -m pip install -r requirements.txt
}
Write-Host "PyInstaller installieren/aktualisieren ..." -ForegroundColor Cyan
python -m pip install --upgrade pyinstaller

# Funktion: Prüfen, ob --contents-directory unterstützt wird
function Supports-ContentsDirectory {
  try {
    $help = & .\.venv\Scripts\pyinstaller.exe --help 2>&1 | Out-String
    return ($help -match "--contents-directory")
  } catch { return $false }
}

$hasContentsDir = Supports-ContentsDirectory
if ($hasContentsDir) {
  Write-Host "PyInstaller unterstützt --contents-directory (OK)." -ForegroundColor Green
} else {
  Write-Host "Achtung: Deine PyInstaller-Version kennt --contents-directory nicht. Verwende Standardnamen (_internal)." -ForegroundColor Yellow
}

# Clean
if ($Clean) {
  Write-Host "Aufräumen: build/ & dist/ löschen ..." -ForegroundColor DarkGray
  if (Test-Path build) { Remove-Item -Recurse -Force build }
  if (Test-Path dist)  { Remove-Item -Recurse -Force dist }
}

# PyInstaller-Argumente
$commonArgs = @()
if ($Clean) { $commonArgs += "--clean" }
$commonArgs += @("--name", $Name, "--noconfirm")
if (-not $Console) { $commonArgs += "--noconsole" }

# Deine Ressourcen als echte Dateien neben der EXE
$commonArgs += @("--add-data", "app\resources;app\resources")

# Slim vs. Full (Qt)
if (-not $Slim) {
  $commonArgs += @("--collect-all", "PySide6")
} else {
  Write-Host "Slim-Modus aktiv (keine vollständige PySide6-Sammlung)." -ForegroundColor DarkGray
}

# Icon
if ($IconICO -and (Test-Path $IconICO)) {
  $commonArgs += @("--icon", $IconICO)
  Write-Host "Nutze EXE-Icon: $IconICO" -ForegroundColor Green
} else {
  Write-Host "Hinweis: Icon '$IconICO' nicht gefunden – baue ohne Icon." -ForegroundColor Yellow
}

# OneFile/OneDir + ggf. Laufzeit-Ordner in 'data' umbenennen
if ($OneFile) {
  $commonArgs += "--onefile"
} else {
  $commonArgs += "--onedir"
  if ($hasContentsDir) {
    $commonArgs += @("--contents-directory", "data")   # statt _internal
  }
}

# Optional: schwere Module ausschließen
if ($ExcludeHeavy) {
  $commonArgs += @(
    "--exclude-module", "numpy",
    "--exclude-module", "pandas",
    "--exclude-module", "matplotlib",
    "--exclude-module", "scipy",
    "--exclude-module", "sklearn",
    "--exclude-module", "PIL"
  )
}

# UPX (optional)
function Find-UPX {
  $c = Get-Command upx -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  $local = Join-Path $PSScriptRoot "tools\upx\upx.exe"
  if (Test-Path $local) { return $local }
  return $null
}
if ($UseUPX) {
  $upx = Find-UPX
  if ($upx) {
    $upxDir = Split-Path $upx -Parent
    Write-Host "UPX gefunden: $upx" -ForegroundColor Green
    $commonArgs += @("--upx-dir", $upxDir)
  } else {
    Write-Host "UPX nicht gefunden – überspringe UPX-Komprimierung." -ForegroundColor Yellow
  }
}

# Build starten
if (-not (Test-Path $Entry)) { throw "Entry-Script '$Entry' nicht gefunden." }
Write-Host "Baue Entry: $Entry" -ForegroundColor Cyan
python -m PyInstaller $Entry @commonArgs

# Ergebnis prüfen
$exeOneFile = Join-Path "dist" "$Name.exe"
$exeOneDir  = Join-Path (Join-Path "dist" $Name) "$Name.exe"

if ($OneFile) {
  if (Test-Path $exeOneFile) {
    Write-Host "`n✅ Build fertig: $exeOneFile" -ForegroundColor Green
  } else {
    Write-Host "`n⚠️  EXE (OneFile) nicht gefunden. Ausgabe oben prüfen." -ForegroundColor Yellow
  }
} else {
  if (Test-Path $exeOneDir) {
    Write-Host "`n✅ Build fertig (OneDir): $exeOneDir" -ForegroundColor Green
    if ($hasContentsDir) {
      Write-Host "   → Runtime-Ordner: dist\$Name\data (statt _internal)" -ForegroundColor DarkGray
    } else {
      Write-Host "   → Runtime-Ordner: dist\$Name\_internal (PyInstaller < 6.3/ohne Option)" -ForegroundColor DarkGray
    }
    Write-Host "   → App-Assets:    dist\$Name\app\resources" -ForegroundColor DarkGray
  } else {
    Write-Host "`n⚠️  EXE (OneDir) nicht gefunden (dist\$Name\$Name.exe). Ausgabe oben prüfen." -ForegroundColor Yellow
  }
}

Write-Host "=== Build-Skript Ende ===" -ForegroundColor Cyan
