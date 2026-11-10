$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.gpu_driver_install.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8

W "=== $(Get-Date) NVIDIA driver install via Windows Update ==="

try {
    $s  = New-Object -ComObject Microsoft.Update.Session
    $sr = $s.CreateUpdateSearcher()
    W "Searching driver updates ..."
    $res = $sr.Search("IsInstalled=0 and Type='Driver'")

    $nv = @($res.Updates | Where-Object { $_.Title -match 'NVIDIA' })
    if ($nv.Count -eq 0) { W "ERROR: no NVIDIA driver update offered"; exit 1 }

    $u = $nv[0]
    W ("Found: " + $u.Title + "  (" + $u.DriverVerDate + ")")

    $coll = New-Object -ComObject Microsoft.Update.UpdateColl
    $null = $coll.Add($u)

    W "Downloading ..."
    $dl = $s.CreateUpdateDownloader()
    $dl.Updates = $coll
    $dr = $dl.Download()
    W ("Download result code: " + $dr.ResultCode + " (2=ok)")

    W "Installing ..."
    $inst = $s.CreateUpdateInstaller()
    $inst.Updates = $coll
    $ir = $inst.Install()
    W ("Install result code: " + $ir.ResultCode + " (2=ok, 3=ok+reboot)")
    W ("Reboot required: " + $ir.RebootRequired)

    Start-Sleep -Seconds 3
    W "--- device state after install ---"
    W ((Get-PnpDevice -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match 'VEN_10DE' } |
        Select-Object Status, Class, FriendlyName, InstanceId | Out-String))
}
catch {
    W ("EXCEPTION: " + $_.Exception.Message)
    exit 1
}

W "=== done ==="
