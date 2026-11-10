$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.nvwmi_install.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) NVWMI provider install + MSI Center restart ==="

$dir = 'C:\Users\MSII\OMNIVOICE\nvwmi\NVWMI'
if (-not (Test-Path (Join-Path $dir 'nvWmi64.exe'))) {
    $dir = 'C:\Users\MSII\OMNIVOICE\nvwmi'
}
W ("NVWMI dir: " + $dir)

$exe = Join-Path $dir 'nvWmi64.exe'
W "Running: nvWmi64.exe /install"
$out = & $exe /install 2>&1
W ($out | Out-String)
W ("exit=" + $LASTEXITCODE)
Start-Sleep -Seconds 5

W "--- NV WMI classes in root\WMI ---"
try {
    $cls = Get-CimClass -Namespace 'root\WMI' -ErrorAction Stop |
           Where-Object { $_.CimClassName -match '^NVIDIA' } |
           Select-Object -ExpandProperty CimClassName
    if ($cls) { W ($cls -join "`n") } else { W "(none)" }
}
catch { W ("WMI query failed: " + $_.Exception.Message) }

W "--- restarting MSI Center ---"
$svcs = @('MSI_Central_Service','MSI.CentralServer','MSI.TerminalServer','MSIService','MSIAPService','MSI_AI_Engine')
foreach ($s in $svcs) {
    $svc = Get-Service $s -ErrorAction SilentlyContinue
    if ($svc) { W ("stopping " + $s); Stop-Service $s -Force -ErrorAction SilentlyContinue }
}
Start-Sleep -Seconds 6
foreach ($s in $svcs) {
    $svc = Get-Service $s -ErrorAction SilentlyContinue
    if ($svc) { Start-Service $s -ErrorAction SilentlyContinue; W ("started " + $s + " -> " + (Get-Service $s).Status) }
}
Start-Sleep -Seconds 4

W "--- device check ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
