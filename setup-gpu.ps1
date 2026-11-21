[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Run .\setup.ps1 -InstallTranscription first.' }
Write-Host 'Installing CUDA 12/cuDNN 9 runtime libraries for NVIDIA Whisper inference. These are large runtime packages, not model weights.'
if (Get-Command uv -ErrorAction SilentlyContinue) {
    & uv pip install --python $python 'nvidia-cublas-cu12==12.4.5.8' 'nvidia-cudnn-cu12==9.1.0.70'
} else {
    & $python -m ensurepip --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Could not enable pip.' }
    & $python -m pip install 'nvidia-cublas-cu12==12.4.5.8' 'nvidia-cudnn-cu12==9.1.0.70'
}
if ($LASTEXITCODE -ne 0) { throw 'GPU runtime installation failed.' }
Write-Host 'Restart ClipForge, then select Auto or NVIDIA GPU in Transcribe. No Codex restart is needed.'
