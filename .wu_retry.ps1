$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.wu_retry.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) clean WU driver install ==="

W "Stopping update services ..."
Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
Stop-Service bits -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

# Remove only the download cache so the package is fetched fresh.
W "Clearing SoftwareDistribution\Download ..."
Get-ChildItem 'C:\Windows\SoftwareDistribution\Download' -Force -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Start-Service bits -ErrorAction SilentlyContinue
Start-Service wuauserv -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

try {
    $s = New-Object -ComObject Microsoft.Update.Session
    $sr = $s.CreateUpdateSearcher()
    W "Searching ..."
    $res = $sr.Search("IsInstalled=0 and Type='Driver'")
    $u = @($res.Updates | Where-Object { $_.Title -match 'NVIDIA' })[0]
    if (-not $u) { W "ERROR: driver not offered"; exit 1 }
    W ("Found: " + $u.Title)

    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    $null = $coll.Add($u)

    $dl = $s.CreateUpdateDownloader()
    $dl.Updates = $coll
    W "Download started $(Get-Date -Format HH:mm:ss)"
    $dr = $dl.Download()
    W ("Download result: " + $dr.ResultCode + " at $(Get-Date -Format HH:mm:ss)")

    $inst = $s.CreateUpdateInstaller()
    $inst.Updates = $coll
    W "Install started $(Get-Date -Format HH:mm:ss)"
    $ir = $inst.Install()
    W ("Install result: " + $ir.ResultCode + " (2/3 = success)")
    W ("Reboot required: " + $ir.RebootRequired)
}
catch {
    W ("EXCEPTION: " + $_.Exception.Message)
}

Start-Sleep -Seconds 5
W "--- devices ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
