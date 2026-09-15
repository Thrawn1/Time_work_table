[CmdletBinding()]
<#
.SYNOPSIS
  Build the Windows EXE (PyInstaller, --onefile) and the Time_table.zip bundle.

.DESCRIPTION
  Safe defaults: only non-personal files go into the bundle
  (calendar + role names + README). Personal handbooks, rates and the
  attlog journal are NOT copied unless -IncludePersonalData is given.
  Any error stops the script ($ErrorActionPreference='Stop' plus exit-code
  checks for external programs). Re-runs are idempotent.

.PARAMETER Python
  Python launcher command (default 'py').

.PARAMETER PyInstallerPin
  PyInstaller version pin for pip (default 'pyinstaller>=6.0').

.PARAMETER DataFile
  Relative DAT path inside data/ (e.g. '1_attlog.dat').
  Copied ONLY together with -IncludePersonalData.

.PARAMETER IncludePersonalData
  Opt-in: also copy personal files
  (id_employee.dat, wage_rates.dat, settlement_exceptions.dat + -DataFile).
  Off by default: the owner adds them manually.

.EXAMPLE
  .\generation_exe.ps1
.EXAMPLE
  .\generation_exe.ps1 -IncludePersonalData -DataFile '1_attlog.dat'
#>
param(
  [string]$Python = 'py',
  [string]$PyInstallerPin = 'pyinstaller>=6.0',
  [string]$DataFile = '',
  [switch]$IncludePersonalData
)

$ErrorActionPreference = 'Stop'

function Assert-LastExitCode([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "Step '$Step' failed with exit code $LASTEXITCODE. Build stopped."
  }
}

# 0. Clean start: remove previous run artifacts (idempotent re-runs).
foreach ($stale in @('.\Time_table', '.\Time_table.zip', '.\build', '.\dist', '.\Time_table.spec', '.\main.spec')) {
  if (Test-Path -LiteralPath $stale) {
    Remove-Item -LiteralPath $stale -Recurse -Force
  }
}

# 1. Interpreter.
& $Python --version
Assert-LastExitCode 'check Python'

# 2. Environment: .venv when present, system interpreter otherwise.
$VenvActivate = '.\.venv\Scripts\Activate.ps1'
if (Test-Path -LiteralPath $VenvActivate) {
  . $VenvActivate
} else {
  Write-Host 'INFO: .venv not found, using system Python.'
}
$PipCmd = 'pip'

# 3. Dependencies (runtime + builder), see requirements*.txt for versions.
& $PipCmd install -r requirements.txt
Assert-LastExitCode 'pip install requirements.txt'
& $PipCmd install $PyInstallerPin
Assert-LastExitCode "pip install $PyInstallerPin"

# 4. Build.
& pyinstaller --onefile --clean --name Time_table main.py
Assert-LastExitCode 'pyinstaller'
if (-not (Test-Path -LiteralPath '.\dist\Time_table.exe')) {
  throw 'Expected file .\dist\Time_table.exe was not created. Build stopped.'
}

# 5. Bundle: allowlist instead of wildcard-copying the working folder.
New-Item -ItemType Directory -Path '.\Time_table' | Out-Null
Copy-Item -LiteralPath '.\dist\Time_table.exe' -Destination '.\Time_table\Time_table.exe'
New-Item -ItemType Directory -Path '.\Time_table\data' | Out-Null
New-Item -ItemType Directory -Path '.\Time_table\data\variable_data_for_app' | Out-Null
$SafeFiles = @(
  'data\variable_data_for_app\holidays.dat',
  'data\variable_data_for_app\postponed_working_days.dat',
  'data\variable_data_for_app\roles_employee.dat'
)
foreach ($rel in $SafeFiles) {
  if (-not (Test-Path -LiteralPath $rel)) {
    throw "Required file '$rel' not found. Build stopped."
  }
  Copy-Item -LiteralPath $rel -Destination '.\Time_table\data\variable_data_for_app\'
}
Copy-Item -LiteralPath '.\README.md' -Destination '.\Time_table\README.md'

if ($IncludePersonalData) {
  Write-Host 'WARNING: copying personal data (-IncludePersonalData). Check who receives the archive.'
  foreach ($rel in @(
    'data\variable_data_for_app\id_employee.dat',
    'data\variable_data_for_app\wage_rates.dat',
    'data\variable_data_for_app\settlement_exceptions.dat'
  )) {
    if (-not (Test-Path -LiteralPath $rel)) {
      throw "File '$rel' not found but requested via -IncludePersonalData. Build stopped."
    }
    Copy-Item -LiteralPath $rel -Destination '.\Time_table\data\variable_data_for_app\'
  }
  if ($DataFile -ne '') {
    $src = Join-Path -Path 'data' -ChildPath $DataFile
    if (-not (Test-Path -LiteralPath $src)) {
      throw "DAT file '$src' not found. Build stopped."
    }
    Copy-Item -LiteralPath $src -Destination '.\Time_table\data\'
  }
} else {
  Write-Host 'INFO: personal files NOT included. Copy manually into Time_table\data\:'
  Write-Host 'INFO:   id_employee.dat, wage_rates.dat, settlement_exceptions.dat and your DAT file.'
}

# 6. Archive (-Force for idempotent re-runs).
Remove-Item -LiteralPath '.\dist' -Recurse -Force
Remove-Item -LiteralPath '.\build' -Recurse -Force
Compress-Archive -Path '.\Time_table' -DestinationPath '.\Time_table.zip' -Force
Write-Host 'Bundle contents:'
Get-ChildItem -Recurse -LiteralPath '.\Time_table' | ForEach-Object { Write-Host ("  " + $_.FullName) }
Write-Host 'DONE! Executable file generated'
