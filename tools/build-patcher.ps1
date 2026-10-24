$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $repoRoot
$assetPath = Join-Path $repoRoot 'release\v0.855\patcher-assets'
python -m PyInstaller --noconfirm --clean --onefile --windowed --name PCE-Space-Adventure-Cobra-Kr-v0.855-Patcher --add-data "$assetPath;." --distpath release/v0.855 --workpath work/patcher-build --specpath work tools/release_patcher.py
if ($LASTEXITCODE -ne 0) { throw 'Patcher build failed' }
