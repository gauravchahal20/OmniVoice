$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.gpu_rescan.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8

W "=== $(Get-Date) elevated rescan ==="
W "--- before ---"
W ((Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | Select-Object Status,FriendlyName,InstanceId | Out-String))

W "--- pnputil /scan-devices ---"
W ((& pnputil /scan-devices 2>&1 | Out-String))

Start-Sleep -Seconds 3

W "--- after: display class ---"
W ((Get-PnpDevice -Class Display -ErrorAction SilentlyContinue | Select-Object Status,FriendlyName,InstanceId | Out-String))

W "--- any PCI device with vendor 10DE (NVIDIA) ---"
$nv = Get-PnpDevice -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*VEN_10DE*' }
if ($nv) { W (($nv | Select-Object Status,Class,FriendlyName,InstanceId,Problem | Out-String)) } else { W "NONE" }

W "--- unknown / problem devices ---"
W ((Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.Status -ne 'OK' } | Select-Object Status,Class,FriendlyName,InstanceId | Out-String))

W "--- PCI bus count ---"
W ("PCI devices enumerated: " + (Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'PCI\*' }).Count)

W "=== done ==="
