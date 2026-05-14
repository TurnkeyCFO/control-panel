# Start Cloudflare quick tunnel and post URL to Slack.
# Run by Task Scheduler TurnkeyControlPanelTunnel at logon.
# Invokes cloudflared inline so we can capture its stderr in-process.

param()
$ErrorActionPreference = "Continue"

$cloudflared   = "$env:LOCALAPPDATA\turnkey-cp\cloudflared.exe"
$logDir        = "$env:LOCALAPPDATA\turnkey-cp"
$tunnelLog     = "$logDir\tunnel.log"
$tunnelUrlFile = "$logDir\tunnel.url"
$envFile       = "C:\Users\ricky_j3cdbqw\CLAUDE CODE PROJECTS\.env"

function Read-EnvFile {
    $map = @{}
    if (-not (Test-Path $envFile)) { return $map }
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        $line = $line.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or $line -notmatch "=") { continue }
        $idx = $line.IndexOf("=")
        $k = $line.Substring(0, $idx).Trim()
        $v = $line.Substring($idx + 1).Trim().Trim('"').Trim("'")
        $map[$k] = $v
    }
    return $map
}

function Post-Slack($token, $channel, $text) {
    $body = (@{ channel = $channel; text = $text } | ConvertTo-Json -Compress)
    try {
        Invoke-RestMethod -Uri "https://slack.com/api/chat.postMessage" `
            -Method Post -Body $body -ContentType "application/json; charset=utf-8" `
            -Headers @{ Authorization = "Bearer $token" } | Out-Null
    } catch {
        Add-Content $tunnelLog "Slack error: $_"
    }
}

function Alert-Failure($env2, $msg) {
    Add-Content $tunnelLog $msg
    $tok = $env2["SLACK_BOT_TOKEN"]
    $ch  = if ($env2["SLACK_CHANNEL_ASSISTANTBOT"]) { $env2["SLACK_CHANNEL_ASSISTANTBOT"] } else { "C0AQVEW4KK8" }
    if ($tok) { Post-Slack $tok $ch $msg }
}

# ── Kill stale cloudflared ────────────────────────────────────────────────
Stop-Process -Name "cloudflared" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

if (-not (Test-Path $cloudflared)) {
    $e = Read-EnvFile
    Alert-Failure $e ":x: Control Panel tunnel: cloudflared.exe not found at $cloudflared"
    exit 1
}

Add-Content $tunnelLog "=== Tunnel starting $(Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ') ==="

# ── Run cloudflared, process stderr line-by-line ──────────────────────────
$psi = [System.Diagnostics.ProcessStartInfo]::new()
$psi.FileName = $cloudflared
$psi.Arguments = "tunnel --url http://localhost:7823 --no-autoupdate"
$psi.UseShellExecute = $false
$psi.RedirectStandardError = $true
$psi.RedirectStandardOutput = $false
$psi.CreateNoWindow = $true

$proc = [System.Diagnostics.Process]::new()
$proc.StartInfo = $psi
$proc.Start() | Out-Null
$proc.Id | Out-File "$logDir\tunnel.pid" -Encoding utf8

# Read stderr synchronously until we find the URL or timeout
$url = $null
$deadline = (Get-Date).AddSeconds(40)

while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
        $e = Read-EnvFile
        Alert-Failure $e ":x: Control Panel tunnel: cloudflared exited (code $($proc.ExitCode)) before producing a URL"
        exit 1
    }
    $line = $proc.StandardError.ReadLine()
    if ($null -eq $line) { Start-Sleep -Milliseconds 100; continue }
    Add-Content $tunnelLog $line
    if ($line -match "https://[a-z0-9\-]+\.trycloudflare\.com") {
        $url = $Matches[0]
        break
    }
}

if (-not $url) {
    $proc.Kill()
    $e = Read-EnvFile
    Alert-Failure $e ":x: Control Panel tunnel: timed out waiting for URL"
    exit 1
}

$url.Trim() | Out-File $tunnelUrlFile -Encoding utf8

# ── Post success to Slack ─────────────────────────────────────────────────
$e         = Read-EnvFile
$slackTok  = $e["SLACK_BOT_TOKEN"]
$slackCh   = if ($e["SLACK_CHANNEL_ASSISTANTBOT"]) { $e["SLACK_CHANNEL_ASSISTANTBOT"] } else { "C0AQVEW4KK8" }
$cpToken   = $e["CONTROL_PANEL_ACCESS_TOKEN"]
$fullUrl   = if ($cpToken) { "$url/?token=$cpToken" } else { $url }
$msg       = ":satellite: *Control Panel is live*`n<$fullUrl|Open on phone>`n``$fullUrl``"

if ($slackTok) { Post-Slack $slackTok $slackCh $msg }
Add-Content $tunnelLog "Tunnel up: $url"

# ── Drain remaining stderr to log, keep alive ─────────────────────────────
$drainBlock = {
    param($p, $log)
    while (-not $p.HasExited) {
        $l = $p.StandardError.ReadLine()
        if ($l) { Add-Content $log $l }
        else { Start-Sleep -Milliseconds 200 }
    }
}
$job = Start-Job -ScriptBlock $drainBlock -ArgumentList $proc, $tunnelLog
$proc.WaitForExit()
$job | Remove-Job -Force
