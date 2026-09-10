# Oflaz Wordle installer for Windows.
#
#   irm https://raw.githubusercontent.com/Coflazo/wordle/main/install.ps1 | iex
#
# Clones the repo, installs Python, Git and the C++ build tools if they are
# missing, builds everything, and starts the game. Safe to re-run.

$ErrorActionPreference = 'Stop'

$Repo = 'https://github.com/Coflazo/wordle.git'
$Dir  = if ($env:WORDLE_DIR) { $env:WORDLE_DIR } else { Join-Path $HOME 'oflaz-wordle' }

function Say  ($m) { Write-Host "`n* $m" -ForegroundColor White }
function Info ($m) { Write-Host "  $m" }
function Die  ($m) { Write-Host "`nError: $m" -ForegroundColor Red; exit 1 }
function Have ($c) { $null -ne (Get-Command $c -ErrorAction SilentlyContinue) }

function Install-WithWinget ($id, $label) {
  if (-not (Have 'winget')) {
    Die "$label is missing and winget is not available. Install $label manually, then re-run this."
  }
  Info "$label is missing, installing"
  winget install --id $id --accept-source-agreements --accept-package-agreements --silent
  # winget updates the machine PATH but not this session's copy.
  $env:Path = [System.Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
              [System.Environment]::GetEnvironmentVariable('Path', 'User')
}

Say 'Checking prerequisites'

if (-not (Have 'git')) { Install-WithWinget 'Git.Git' 'Git' }

$python = $null
foreach ($c in @('python', 'python3', 'py')) {
  if (Have $c) {
    try {
      $v = & $c -c 'import sys; print("%d%02d" % sys.version_info[:2])' 2>$null
      if ([int]$v -ge 311) { $python = $c; break }
    } catch { }
  }
}
if (-not $python) {
  Install-WithWinget 'Python.Python.3.12' 'Python 3.12'
  $python = 'python'
}
Info "Python: $(& $python --version)"

# The native module needs MSVC. Probe the way setuptools does.
$hasMsvc = $false
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (Test-Path $vswhere) {
  $found = & $vswhere -latest -products * `
    -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath 2>$null
  if ($found) { $hasMsvc = $true }
}
if (-not $hasMsvc) {
  Info 'The C++ build tools are missing, installing (this one is large)'
  if (-not (Have 'winget')) {
    Die 'Install the Microsoft C++ Build Tools, selecting "Desktop development with C++", then re-run this.'
  }
  winget install --id Microsoft.VisualStudio.2022.BuildTools `
    --override '--quiet --wait --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended' `
    --accept-source-agreements --accept-package-agreements
}
Info 'C++ build tools: present'

if (Test-Path (Join-Path $Dir '.git')) {
  Say "Updating $Dir"
  git -C $Dir pull --ff-only --quiet
} else {
  Say "Cloning into $Dir"
  git clone --depth 1 --quiet $Repo $Dir
}

Say 'Building'
Set-Location $Dir
& $python run.py --setup-only
if ($LASTEXITCODE -ne 0) { Die 'the build failed. See the output above.' }

Write-Host "`nReady. Starting the game." -ForegroundColor Green
Write-Host "Next time, just run:  cd $Dir; python run.py`n"
& $python run.py
