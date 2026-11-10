$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.msi_services_start.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) start MSI services ==="

foreach ($s in 'Micro Star SCM','MSI Foundation Service','MSI_Center_Service') {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if (-not $svc) { W ("service not found: " + $s); continue }
    W ("{0}: {1} (startmode {2})" -f $s, $svc.Status, $svc.StartType)
    if ($svc.Status -ne 'Running') {
        try { Start-Service -Name $s -ErrorAction Stop; W ("started " + $s) }
        catch { W ("failed to start " + $s + ": " + $_.Exception.Message) }
    }
}

Start-Sleep -Seconds 8
W "--- states ---"
foreach ($s in 'Micro Star SCM','MSI Foundation Service','MSI_Center_Service') {
    $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
    if ($svc) { W ("{0}: {1}" -f $s, $svc.Status) }
}

W "--- processes ---"
W ((Get-Process | Where-Object { $_.Name -match '^MSI|DCv2' } | Select-Object Name, Id | Out-String))
W "=== done ==="
