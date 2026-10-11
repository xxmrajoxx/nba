# Registers a Windows Task Scheduler task that refreshes the nba database every morning.
# Run once from PowerShell:   .\scripts\register_scheduled_task.ps1
# Remove it again with:       Unregister-ScheduledTask -TaskName "nba-pipeline-daily"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

$action = New-ScheduledTaskAction -Execute $python -Argument "src\run_job.py all" -WorkingDirectory $projectRoot
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
# StartWhenAvailable runs a missed job as soon as the laptop is next on.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)

Register-ScheduledTask -TaskName "nba-pipeline-daily" -Action $action -Trigger $trigger -Settings $settings `
    -Description "Refresh NBA teams, players, schedule and game logs in SQL Server" -Force
