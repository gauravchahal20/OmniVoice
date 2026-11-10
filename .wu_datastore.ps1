$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.wu_datastore.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) datastore reset + NVIDIA driver install ==="

foreach ($s in 'wuauserv','bits','UsoSvc','DoSvc') {
    Stop-Service $s -Force -ErrorAction SilentlyContinue
}
& net stop trustedinstaller 2>&1 | Out-Null
Start-Sleep -Seconds 5

$ds = 'C:\Windows\SoftwareDistribution\DataStore'
W "Removing DataStore contents ..."
Get-ChildItem $ds -Force -ErrorAction SilentlyContinue | ForEach-Object {
    try { Remove-Item $_.FullName -Recurse -Force -ErrorAction Stop; W ("deleted " + $_.Name) }
    catch { W ("could not delete " + $_.Name + ": " + $_.Exception.Message) }
}

$dlDir = 'C:\Windows\SoftwareDistribution\Download'
Get-ChildItem $dlDir -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
W "Download cache cleared."

foreach ($s in 'wuauserv','bits','UsoSvc','DoSvc') {
    Start-Service $s -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 15

try {
    $sess = New-Object -ComObject Microsoft.Update.Session
    $sr = $sess.CreateUpdateSearcher()
    W "Searching ..."
    $res = $sr.Search("IsInstalled=0 and Type='Driver'")
    $u = @($res.Updates | Where-Object { $_.Title -match 'NVIDIA' })[0]
    if (-not $u) { W "ERROR: driver not offered"; exit 1 }
    W ("Found: " + $u.Title + " | IsDownloaded=" + $u.IsDownloaded)

    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    $null = $coll.Add($u)

    $dl = $sess.CreateUpdateDownloader()
    $dl.Updates = $coll
    W "Download started $(Get-Date -Format HH:mm:ss)"
    $dr = $dl.Download()
    W ("Download result=" + $dr.ResultCode + " hresult=" + $dr.HResult + " at $(Get-Date -Format HH:mm:ss)")
    if ($dr.ResultCode -notin 2,3) { W "download failed"; exit 1 }

    $size = (Get-ChildItem $dlDir -Recurse -File -ErrorAction SilentlyContinue |
             Measure-Object Length -Sum).Sum
    W ("Payload on disk: " + [math]::Round($size/1MB,1) + " MB")

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

& pnputil /scan-devices 2>&1 | Out-Null
Start-Sleep -Seconds 8
W "--- devices ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
