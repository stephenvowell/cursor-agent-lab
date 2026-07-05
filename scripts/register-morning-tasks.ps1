# Register 8 AM email check + 8:15 AM unattended Job Hunter (Windows Task Scheduler).
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Missing venv: $py - run: python -m venv .venv; pip install -r requirements.txt"
    exit 1
}

$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

# 8:00 — Gmail scan (popup + opens summary file)
$emailScript = Join-Path $root "app\job_email_checker.py"
$emailAction = New-ScheduledTaskAction -Execute $py -Argument "`"$emailScript`"" -WorkingDirectory $root
$emailTrigger = New-ScheduledTaskTrigger -Daily -At 8:00AM
Register-ScheduledTask -TaskName "JobEmailChecker" -Action $emailAction -Trigger $emailTrigger `
    -Settings $settings `
    -Description "Scan Gmail each morning; system-modal popup + open summary in workspace/output." `
    -Force | Out-Null

# 8:15 — Job Hunter (auto-approve; popup + open report when done)
$hunterScript = Join-Path $root "scripts\run-morning-job-hunter.ps1"
$hunterAction = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$hunterScript`"" `
    -WorkingDirectory $root
$hunterTrigger = New-ScheduledTaskTrigger -Daily -At 8:15AM
Register-ScheduledTask -TaskName "JobHunter" -Action $hunterAction -Trigger $hunterTrigger `
    -Settings $settings `
    -Description "Unattended Job Hunter: scout, score roles, draft cover letters; uses Cursor API." `
    -Force | Out-Null

Write-Host "Registered morning tasks:"
Get-ScheduledTask -TaskName "JobEmailChecker","JobHunter" | Format-Table TaskName, State
Get-ScheduledTaskInfo -TaskName "JobEmailChecker" | Select-Object TaskName, NextRunTime
Get-ScheduledTaskInfo -TaskName "JobHunter" | Select-Object TaskName, NextRunTime
