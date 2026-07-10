# Launch Hipparchus on Windows (PowerShell).
#
# First-time users: run  .\setup.ps1  once to install dependencies, then:
#   .\run_hprs.ps1
#
# Override the interpreter with:  $env:HIPPARCHUS_PYTHON = "C:\path\to\python.exe"
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Run from the source checkout: expose both src/ and the repo root.
$env:PYTHONPATH = "src;."

# Pick an interpreter: HIPPARCHUS_PYTHON override, else the 'py' launcher, else 'python'.
$python = $env:HIPPARCHUS_PYTHON
if (-not $python) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
    else { $python = "python" }
}

# Check required packages before launching; point at setup.ps1 if anything is missing.
$check = @"
import importlib.util, sys
required = {'numpy': 'numpy', 'scipy': 'scipy', 'shapely': 'shapely', 'tkinter': 'tkinter'}
missing = [pkg for mod, pkg in required.items() if importlib.util.find_spec(mod) is None]
if missing:
    sys.stderr.write('Missing required packages: ' + ', '.join(missing) + '\n')
    sys.exit(1)
if importlib.util.find_spec('skia') is None:
    sys.stderr.write('Warning: skia-python not installed; using the fallback renderer.\n')
"@
& $python -c $check
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Run setup once to install dependencies:  .\setup.ps1"
    exit 1
}

& $python -m hipparchus
