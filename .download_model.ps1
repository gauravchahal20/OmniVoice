# Robust resumable download of OmniVoice weights via curl.
# The Python huggingface_hub downloader stalls on this network; plain HTTPS works.
$ErrorActionPreference = 'Continue'

$base = 'https://huggingface.co/k2-fsa/OmniVoice/resolve/main'
$dst  = 'C:\Users\MSII\OMNIVOICE\models\OmniVoice'

$files = @(
  'config.json',
  'tokenizer.json',
  'tokenizer_config.json',
  'chat_template.jinja',
  'README.md',
  'audio_tokenizer/config.json',
  'audio_tokenizer/preprocessor_config.json',
  'audio_tokenizer/LICENSE',
  'audio_tokenizer/README.md',
  'audio_tokenizer/model.safetensors',
  'model.safetensors'
)

foreach ($f in $files) {
  $out = Join-Path $dst ($f -replace '/', '\')
  $dir = Split-Path $out -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }

  Write-Host "=== $f ==="
  # -C - resumes partial files, --retry keeps going through flaky connections
  curl.exe -L -f -C - --retry 100 --retry-delay 3 --retry-all-errors `
           --connect-timeout 30 --speed-time 120 --speed-limit 1024 `
           -o "$out" "$base/$f"
  Write-Host "exit=$LASTEXITCODE size=$((Get-Item $out -ErrorAction SilentlyContinue).Length)"
}

Write-Host "ALL DONE"
