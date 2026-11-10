$ErrorActionPreference = 'Continue'
$log = 'C:\Users\MSII\OMNIVOICE\.nv_manual_install.log'
function W($m) { $m | Out-File -FilePath $log -Append -Encoding utf8 }
'' | Out-File -FilePath $log -Encoding utf8
W "=== $(Get-Date) manual NVIDIA driver install ==="

$src  = 'C:\Windows\SoftwareDistribution\Download\bf774616a074ed1d\813c84c3673bd93631bb6930b725beb430fbfc4c'
$work = 'C:\Users\MSII\OMNIVOICE\nv_driver'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$cab = Join-Path $work 'driver.cab'

if (-not (Test-Path $cab) -or (Get-Item $cab).Length -lt 100MB) {
    W "Stopping update services to release the file lock ..."
    Stop-Service wuauserv -Force -ErrorAction SilentlyContinue
    Stop-Service bits -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3

    W "Copying package ..."
    try {
        Copy-Item $src $cab -Force -ErrorAction Stop
        W ("Copied: " + [math]::Round((Get-Item $cab).Length/1MB,1) + " MB")
    }
    catch {
        W ("COPY FAILED: " + $_.Exception.Message)
        Start-Service wuauserv -ErrorAction SilentlyContinue
        exit 1
    }
}

$magic = [Text.Encoding]::ASCII.GetString([IO.File]::ReadAllBytes($cab)[0..3])
W ("File magic: " + $magic)

$ext = Join-Path $work 'extracted'
if ($magic -eq 'MSCF') {
    if (-not (Test-Path $ext)) { New-Item -ItemType Directory -Force -Path $ext | Out-Null }
    W "Expanding cab ..."
    & expand.exe $cab -F:* $ext | Out-Null
    W ("expand exit=" + $LASTEXITCODE)
}
else {
    W "Not a CAB; treating as a driver folder payload."
    $ext = $work
}

$infs = Get-ChildItem $ext -Recurse -Filter *.inf -ErrorAction SilentlyContinue
W ("INF files found: " + $infs.Count)
$infs | ForEach-Object { W ("  " + $_.FullName) }

if ($infs.Count -eq 0) {
    W "ERROR: no INF found"
    Start-Service wuauserv -ErrorAction SilentlyContinue
    exit 1
}

W "Installing via pnputil ..."
$out = & pnputil.exe /add-driver (Join-Path $ext '*.inf') /install /subdirs 2>&1
W ($out | Out-String)
W ("pnputil exit=" + $LASTEXITCODE)

Start-Service wuauserv -ErrorAction SilentlyContinue

Start-Sleep -Seconds 5
W "--- devices after install ---"
W ((Get-CimInstance Win32_VideoController | Select-Object Name, DriverVersion, Status | Out-String))
W "=== done ==="
