$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$assetPath = Join-Path $repoRoot 'release\v1.0\patcher-assets'
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PCE-Space-Adventure-Cobra-Kr-v1.0-r2-Patcher --add-data "$assetPath;." --distpath release/v1.0 --workpath work/patcher-build --specpath work tools/release_patcher.py
if ($LASTEXITCODE -ne 0) { throw 'Patcher build failed' }
