[CmdletBinding()]
param(
    [switch]$InstallTranscription,
    [switch]$InstallDevTools,
    [string]$PythonExecutable,
    [string]$NodeDirectory,
    [string]$FFmpegDirectory
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot

function Invoke-Checked {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Executable $($Arguments -join ' ')" }
}

# Prefer the requested runtime, then PATH. The local REA runtime is only a fallback.
if ($NodeDirectory) {
    $nodeCandidate = Join-Path $NodeDirectory 'node.exe'
    if (!(Test-Path -LiteralPath $nodeCandidate -PathType Leaf)) { throw "Node executable not found: $nodeCandidate" }
    $env:PATH = "$NodeDirectory;$env:PATH"
}
$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$nodeSupported = $false
if ($nodeCommand) {
    $nodeText = (& $nodeCommand.Source --version).Trim().TrimStart('v')
    $nodeVersion = [version]$nodeText
    $nodeSupported = ($nodeVersion.Major -eq 20 -and $nodeVersion.Minor -ge 19) -or ($nodeVersion.Major -eq 22 -and $nodeVersion.Minor -ge 12) -or ($nodeVersion.Major -gt 22)
}
if (!$nodeSupported -and !$NodeDirectory) {
    $reaNode = 'E:\REA\tools\node-v24.22.3-win-x64'
    if (Test-Path -LiteralPath (Join-Path $reaNode 'node.exe')) {
        $env:PATH = "$reaNode;$env:PATH"
        $nodeCommand = Get-Command node.exe
        $nodeSupported = $true
    }
}
if (!$nodeSupported) { throw 'Install Node.js 20.19+, 22.12+, or a newer supported LTS; alternatively pass -NodeDirectory.' }
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (!$npmCommand) { throw 'npm.cmd was not found. Install Node.js with npm.' }

$pythonArgs = @()
if ($PythonExecutable) {
    $pythonCommand = Get-Command $PythonExecutable -ErrorAction Stop
} else {
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if (!$pythonCommand) {
        $pythonCommand = Get-Command py.exe -ErrorAction SilentlyContinue
        $pythonArgs = @('-3')
    }
}
if (!$pythonCommand) { throw 'Install Python 3.11 or newer, or pass -PythonExecutable C:\path\python.exe.' }
Invoke-Checked $pythonCommand.Source ($pythonArgs + @('-c', 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'))
$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $venvPython)) {
    Invoke-Checked $pythonCommand.Source ($pythonArgs + @('-m', 'venv', (Join-Path $projectRoot '.venv')))
}
Invoke-Checked $venvPython @('-c', 'import sys; assert sys.version_info >= (3,11), "Existing .venv requires Python 3.11+"')

# uv-created virtual environments may deliberately omit pip. ensurepip uses Python's bundled wheels.
& $venvPython -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("pip") else 1)'
if ($LASTEXITCODE -ne 0) { Invoke-Checked $venvPython @('-m', 'ensurepip', '--upgrade') }
Write-Host 'Installing Python packages. No speech or language model weights are downloaded by this script.'
Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $projectRoot 'requirements.txt'))
if ($InstallTranscription) {
    Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $projectRoot 'requirements-ai.txt'))
}
if ($InstallDevTools) {
    Invoke-Checked $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $projectRoot 'requirements-dev.txt'))
}

Push-Location (Join-Path $projectRoot 'frontend')
try {
    if (Test-Path -LiteralPath 'package-lock.json') { Invoke-Checked $npmCommand.Source @('ci') }
    else { Invoke-Checked $npmCommand.Source @('install') }
    Invoke-Checked $npmCommand.Source @('run', 'build')
} finally { Pop-Location }

if ($FFmpegDirectory) {
    if (!(Test-Path -LiteralPath (Join-Path $FFmpegDirectory 'ffmpeg.exe')) -or !(Test-Path -LiteralPath (Join-Path $FFmpegDirectory 'ffprobe.exe'))) {
        throw 'FFmpegDirectory must contain both ffmpeg.exe and ffprobe.exe.'
    }
    $env:PATH = "$FFmpegDirectory;$env:PATH"
}
$ffmpegCommand = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
$ffprobeCommand = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
$knownMedia = 'D:\ffmpeg-8.1.1-essentials_build\bin'
if ((!$ffmpegCommand -or !$ffprobeCommand) -and (Test-Path -LiteralPath (Join-Path $knownMedia 'ffmpeg.exe')) -and (Test-Path -LiteralPath (Join-Path $knownMedia 'ffprobe.exe'))) {
    $env:PATH = "$knownMedia;$env:PATH"
    $ffmpegCommand = Get-Command ffmpeg.exe
    $ffprobeCommand = Get-Command ffprobe.exe
}
if (!$ffmpegCommand -or !$ffprobeCommand) {
    Write-Warning 'Install FFmpeg (including ffprobe and libass) and add its bin directory to PATH before starting. No FFmpeg download was attempted.'
} else {
    Write-Host "FFmpeg detected: $($ffmpegCommand.Source)"
}
Write-Host 'Setup complete. Run .\start.ps1. Optional transcription weights download only when transcription is requested.'

