# Build Career Copilot retail pack: GUI exe + portable toolkit in bin/pack/

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$Bin = Join-Path $Root "bin"
$Pack = Join-Path $Bin "pack"
$OutExe = Join-Path $Bin "CareerCopilot.exe"
$App = Join-Path $Root "app"
$Assets = Join-Path $Root "assets"

New-Item -ItemType Directory -Path $Bin -Force | Out-Null
New-Item -ItemType Directory -Path $Pack -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Pack "workspace\output") -Force | Out-Null

function Sync-Dir($Name) {
    $src = Join-Path $Root $Name
    $dst = Join-Path $Pack $Name
    if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
    Copy-Item $src $dst -Recurse -Force
}

Write-Host "Assembling pack..."
Sync-Dir "app"
Sync-Dir "shared"
Sync-Dir "config"
Sync-Dir "assets"
Copy-Item (Join-Path $Root "requirements.txt") (Join-Path $Pack "requirements.txt") -Force
Copy-Item (Join-Path $Root ".env.example") (Join-Path $Pack ".env.example") -Force -ErrorAction SilentlyContinue
Copy-Item (Join-Path $Root "workspace\README.md") (Join-Path $Pack "workspace\README.md") -Force -ErrorAction SilentlyContinue

Push-Location $Root
try {
    if (-not (Test-Path (Join-Path $Root ".venv\Scripts\python.exe"))) {
        Write-Host "Creating build venv..."
        python -m venv .venv
    }
    Write-Host "Installing dependencies (build venv + pack venv)..."
    .\.venv\Scripts\pip install -q -r requirements.txt pyinstaller pillow

    if (-not (Test-Path (Join-Path $Pack ".venv\Scripts\python.exe"))) {
        python -m venv (Join-Path $Pack ".venv")
    }
    & (Join-Path $Pack ".venv\Scripts\pip.exe") install -q -r (Join-Path $Pack "requirements.txt")

    $IconArg = @()
    if (Test-Path (Join-Path $Assets "satori-icon.ico")) {
        $IconArg = @("--icon", (Join-Path $Assets "satori-icon.ico"))
    }

    $AddData = @()
    Get-ChildItem $Assets -File | ForEach-Object {
        $AddData += @("--add-data", "$($_.FullName);assets")
    }

    Write-Host "Building CareerCopilot.exe..."
    .\.venv\Scripts\python -m PyInstaller `
        --noconfirm `
        --onefile `
        --windowed `
        --name CareerCopilot `
        --distpath $Bin `
        --workpath (Join-Path $Root "build\career-copilot") `
        --specpath (Join-Path $Root "build\career-copilot") `
        --paths $App `
        @AddData `
        --hidden-import license `
        --hidden-import setup_wizard `
        --hidden-import paths `
        --hidden-import PIL._tkinter_finder `
        @IconArg `
        (Join-Path $App "career_copilot.py")

    if (-not (Test-Path $OutExe)) {
        throw "Build failed - $OutExe not created"
    }

    $Marker = Join-Path $Bin "career_copilot_root.txt"
    Set-Content -Path $Marker -Value (Resolve-Path $Pack).Path -Encoding UTF8

    Write-Host "Built: $OutExe"
    Write-Host "Pack:  $Pack"
}
finally {
    Pop-Location
}

$MyAppsPath = Join-Path $env:OneDrive "Desktop\myApps"
$ShortcutTargets = @(
    $MyAppsPath,
    (Join-Path $env:USERPROFILE "Desktop\myApps"),
    (Join-Path $env:USERPROFILE "Desktop")
) | Where-Object { $_ -and (Test-Path (Split-Path $_ -Parent)) } | Select-Object -Unique

foreach ($Desktop in $ShortcutTargets) {
    if (-not (Test-Path $Desktop)) { New-Item -ItemType Directory -Path $Desktop -Force | Out-Null }
    Copy-Item $OutExe (Join-Path $Desktop "CareerCopilot.exe") -Force
    Copy-Item (Join-Path $Bin "career_copilot_root.txt") (Join-Path $Desktop "career_copilot_root.txt") -Force
    # Retail zip must include pack/ next to exe — copy shortcut target uses bin as cwd
    $destPack = Join-Path $Desktop "pack"
    if (Test-Path $destPack) { Remove-Item $destPack -Recurse -Force }
    Copy-Item $Pack $destPack -Recurse -Force
    Set-Content -Path (Join-Path $Desktop "career_copilot_root.txt") -Value $destPack -Encoding UTF8
    $lnk = Join-Path $Desktop "Career Copilot.lnk"
    $Wsh = New-Object -ComObject WScript.Shell
    $Sc = $Wsh.CreateShortcut($lnk)
    $Sc.TargetPath = $OutExe
    $Sc.WorkingDirectory = $Desktop
    $Sc.Description = "Career Copilot - Job Scout + Hunter with yes/no approval"
    $Sc.IconLocation = "$OutExe,0"
    $Sc.Save()
    Write-Host "Shortcut: $lnk"
}

Write-Host ""
Write-Host "Done. Retail flow: launch CareerCopilot.exe -> Setup (license + API key + resume)"
Write-Host "Generate keys: python scripts/generate-license.py"
