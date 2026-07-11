# Rhyme fleet restart onto current code + watchdog registration.
# Run FROM AN ELEVATED PowerShell:
#   powershell -ExecutionPolicy Bypass -File D:\workspace\rhyme\scheduler\restart_fleet.ps1
#
# Stops each bot by pidfile, relaunches via its scheduled task (the sole
# sanctioned launch path, staggered 20s), and registers the watchdog task
# if it isn't registered yet.

Set-Location D:\workspace\rhyme

foreach ($mode in @("scalp30", "pullback30", "intraday", "spread2b")) {
    $pidfile = "paper_trader_$mode.pid"
    if (Test-Path $pidfile) {
        $botPid = Get-Content $pidfile -ErrorAction SilentlyContinue
        if ($botPid) {
            Write-Host "stopping $mode (PID $botPid)..."
            Stop-Process -Id $botPid -Force -ErrorAction SilentlyContinue
        }
    }
}

Start-Sleep 3

$tasks = @("\Rhyme\Rhyme-Scalp30", "\Rhyme\Rhyme-Pullback30", "\Rhyme\Rhyme-Intraday", "\Rhyme\Rhyme-Spread2B")
foreach ($task in $tasks) {
    Write-Host "launching $task..."
    schtasks /run /tn $task
    Start-Sleep 20
}

schtasks /query /tn "\Rhyme\Rhyme-Watchdog" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "registering \Rhyme\Rhyme-Watchdog..."
    schtasks /create /tn "\Rhyme\Rhyme-Watchdog" /xml "D:\workspace\rhyme\scheduler\Rhyme-Watchdog.xml"
} else {
    Write-Host "\Rhyme\Rhyme-Watchdog already registered."
}

Write-Host "done -- fleet relaunched; verify banners in paper_trade_*_stdout.log"
