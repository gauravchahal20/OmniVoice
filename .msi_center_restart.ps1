$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.msi_center_restart.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) restart MSI Center (re-enumerate GPU) ==="

W "--- before ---"
W ((Get-Process | Where-Object { $_.Name -match '^MSI' } | Select-Object Name, Id | Out-String))

foreach ($n in 'MSI.TerminalServer','MSI.CentralServer','MSI_AI_Engine','MSI_Central_Service','MSIAPService','MSIService') {
    $procs = Get-Process -Name $n -ErrorAction SilentlyContinue
    foreach ($p in $procs) {
        try { Stop-Process -Id $p.Id -Force -ErrorAction Stop; W ("killed " + $n + " pid " + $p.Id) }
        catch { W ("could not kill " + $n + " pid " + $p.Id + ": " + $_.Exception.Message) }
    }
}

Start-Sleep -Seconds 5
W "--- after kill ---"
W ((Get-Process | Where-Object { $_.Name -match '^MSI' } | Select-Object Name, Id | Out-String))

W "--- device still fine ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
