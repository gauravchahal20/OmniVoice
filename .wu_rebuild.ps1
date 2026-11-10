$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.wu_rebuild.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) rebuild WU datastore + install NVIDIA driver ==="

W "Stopping services ..."
foreach ($s in 'wuauserv','bits','UsoSvc','DoSvc') {
    Stop-Service $s -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 4

$sd = 'C:\Windows\SoftwareDistribution'
$bak = "C:\Windows\SoftwareDistribution.bak_$(Get-Date -Format yyyyMMddHHmmss)"
W "Renaming $sd -> $bak"
try {
    Rename-Item $sd $bak -ErrorAction Stop
    W "renamed OK"
}
catch {
    W ("rename failed: " + $_.Exception.Message + " -- falling back to deleting Download subfolder")
    Remove-Item (Join-Path $sd 'Download') -Recurse -Force -ErrorAction SilentlyContinue
}

foreach ($s in 'wuauserv','bits','UsoSvc','DoSvc') {
    Start-Service $s -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 10

try {
    $sess = New-Object -ComObject Microsoft.Update.Session
    $sr = $sess.CreateUpdateSearcher()
    W "Searching (may take a minute) ..."
    $res = $sr.Search("IsInstalled=0 and Type='Driver'")
    $u = @($res.Updates | Where-Object { $_.Title -match 'NVIDIA' })[0]
    if (-not $u) { W "ERROR: NVIDIA driver not offered"; exit 1 }
    W ("Found: " + $u.Title + " | IsDownloaded=" + $u.IsDownloaded)

    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    $null = $coll.Add($u)

    $dl = $sess.CreateUpdateDownloader()
    $dl.Updates = $coll
    W "Download started $(Get-Date -Format HH:mm:ss)"
    $dr = $dl.Download()
    W ("Download result=" + $dr.ResultCode + " hresult=" + $dr.HResult + " at $(Get-Date -Format HH:mm:ss)")

    if ($dr.ResultCode -notin 2,3) { W "download did not succeed"; exit 1 }

    $inst = $sess.CreateUpdateInstaller()
    $inst.Updates = $coll
    W "Install started $(Get-Date -Format HH:mm:ss)"
    $ir = $inst.Install()
    W ("Install result=" + $ir.ResultCode + " hresult=" + $ir.HResult)
    W ("Reboot required: " + $ir.RebootRequired)
}
catch {
    W ("EXCEPTION: " + $_.Exception.Message)
}

Start-Sleep -Seconds 5
W "--- pnputil rescan ---"
W ((& pnputil /scan-devices 2>&1 | Out-String))
Start-Sleep -Seconds 5
W "--- devices ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
