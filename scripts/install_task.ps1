# Registers the Turnkey Control Panel to launch at user logon + a watchdog every 2 min.
# Runs as current user, no admin required.
# Also: tightens ACL on the local data dir and adds a Windows Firewall inbound-block rule for TCP 7823.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$runBat   = Join-Path $repoRoot "scripts\run.bat"
$watchdog = Join-Path $repoRoot "scripts\watchdog.ps1"

$dataDir = Join-Path $env:LOCALAPPDATA "turnkey-cp"
if (-not (Test-Path $dataDir)) { New-Item -ItemType Directory -Path $dataDir | Out-Null }

Write-Host "Tightening ACL on $dataDir (user-only)..."
& icacls $dataDir /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" | Out-Null

Write-Host "Registering logon task: TurnkeyControlPanel"
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runBat`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "TurnkeyControlPanel" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Registering watchdog task: TurnkeyControlPanel-Watchdog (every 2 min)"
$wdAction  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$watchdog`""
$wdTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 2) -RepetitionDuration (New-TimeSpan -Days 3650)
Register-ScheduledTask -TaskName "TurnkeyControlPanel-Watchdog" -Action $wdAction -Trigger $wdTrigger -Settings $settings -Force | Out-Null

Write-Host "Adding Windows Firewall inbound-block rule for TCP 7823 (loopback still works)"
try {
    Remove-NetFirewallRule -DisplayName "Turnkey Control Panel - block inbound" -ErrorAction SilentlyContinue | Out-Null
    New-NetFirewallRule -DisplayName "Turnkey Control Panel - block inbound" -Direction Inbound -Action Block -Protocol TCP -LocalPort 7823 -Profile Any | Out-Null
} catch {
    Write-Warning "Firewall rule add failed (may need admin). Not fatal; app still binds to 127.0.0.1 only."
}

Write-Host ""
Write-Host "Done. Reboot or run scripts\run.bat manually. Dashboard: http://127.0.0.1:7823"
