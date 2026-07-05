# Unattended Job Hunter for Task Scheduler (8:15 AM daily).
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$py = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "app\job_hunter.py"
$log = Join-Path $root "workspace\output\job-hunter-scheduled.log"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Add-Content -Path $log -Value "`n=== Job Hunter run $stamp ==="
& $py $script --unattended *>> $log
