# One-command dependency setup for Hipparchus (Windows PowerShell).
#
# Installs the Python packages Hipparchus needs into your normal Python.
# No virtual environment is created. Run this once after cloning:
#
#   .\setup.ps1          # core runtime (numpy, scipy, shapely, skia-python)
#   .\setup.ps1 -Maps    # also install optional local map-source backends
#
# Then launch with: .\run_hprs.ps1
param(
    [switch]$Maps
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# Pick an interpreter: HIPPARCHUS_PYTHON override, else the 'py' launcher, else 'python'.
$python = $env:HIPPARCHUS_PYTHON
if (-not $python) {
    if (Get-Command py -ErrorAction SilentlyContinue) { $python = "py" }
    else { $python = "python" }
}

# Verify Python 3.11+.
$versionCheck = & $python -c "import sys; print('%d.%d' % sys.version_info[:2]); sys.exit(0 if sys.version_info >= (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Hipparchus needs Python 3.11 or newer. Found Python $versionCheck at '$python'."
    exit 1
}

$packages = @("numpy", "scipy", "shapely", "skia-python")
if ($Maps) {
    $packages += @("fiona", "mapbox-vector-tile", "osmium", "pmtiles", "pyarrow", "rasterio", "scikit-image")
}

Write-Host "Hipparchus setup"
Write-Host "  Python: $python (version $versionCheck)"
Write-Host "  Installing: $($packages -join ', ')"
Write-Host ""

# Try a --user install first, then fall back to a plain install.
& $python -m pip install --user @packages
if ($LASTEXITCODE -ne 0) {
    & $python -m pip install @packages
}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Dependency install failed. Consider a virtual environment, conda, or a fresh python.org install."
    exit 1
}

# tkinter ships with Python and cannot be installed with pip.
& $python -c "import tkinter" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "tkinter is missing from this Python and cannot be installed with pip."
    Write-Warning "Reinstall Python from python.org with the 'tcl/tk and IDLE' option enabled."
    Write-Warning "Hipparchus needs tkinter to open its window."
}

Write-Host ""
Write-Host "Setup complete. Launch Hipparchus with:  .\run_hprs.ps1"
