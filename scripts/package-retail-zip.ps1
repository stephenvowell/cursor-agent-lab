# Zip Career Copilot for Gumroad / Lemon Squeezy delivery
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$Bin = Join-Path $Root "bin"
$Zip = Join-Path $Root "CareerCopilot-retail.zip"

if (-not (Test-Path (Join-Path $Bin "CareerCopilot.exe"))) {
    Write-Host "Run scripts/build-career-copilot.ps1 first."
    exit 1
}

$Staging = Join-Path $env:TEMP "CareerCopilot-retail"
if (Test-Path $Staging) { Remove-Item $Staging -Recurse -Force }
New-Item -ItemType Directory -Path $Staging | Out-Null

Copy-Item (Join-Path $Bin "CareerCopilot.exe") $Staging
Copy-Item (Join-Path $Bin "pack") (Join-Path $Staging "pack") -Recurse
Set-Content (Join-Path $Staging "career_copilot_root.txt") -Value (Join-Path $Staging "pack") -Encoding UTF8
Copy-Item (Join-Path $Root "docs\PRIVACY.md") $Staging
Copy-Item (Join-Path $Root "assets\career-copilot-demo.png") $Staging
$product = (Get-Content (Join-Path $Root "docs\PRODUCT.md") -Raw) -replace '\.\./assets/career-copilot-demo\.png', 'career-copilot-demo.png'
Set-Content (Join-Path $Staging "PRODUCT.md") -Value $product -Encoding UTF8

if (Test-Path $Zip) { Remove-Item $Zip -Force }
Compress-Archive -Path (Join-Path $Staging "*") -DestinationPath $Zip
Write-Host "Created: $Zip"
Write-Host "Upload this zip to your storefront. Email a license key from: python scripts/generate-license.py"
