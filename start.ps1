[CmdletBinding()]
param(
    [ValidateRange(1024,65535)][int]$Port = 8000,
    [switch]$NoBrowser,
    [string]$FFmpegDirectory
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Python environment missing. Run .\setup.ps1 first.' }
if (!(Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Built frontend missing. Run .\setup.ps1 first.' }

# Read literal KEY=value settings, never evaluate PowerShell from a .env file.
$envFile = Join-Path $projectRoot '.env'
$allowedSettings = @('CLIPFORGE_DATA_DIR', 'CLIPFORGE_FFMPEG', 'CLIPFORGE_FFPROBE', 'OLLAMA_BASE_URL', 'CLIPFORGE_MAX_UPLOAD_MB', 'TAVILY_API_KEY', 'WHISPER_CUDA_PATH')
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$' -and $allowedSettings -contains $Matches[1]) {
            $key = $Matches[1]
            $value = $Matches[2]
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) { $value = $value.Substring(1, $value.Length - 2) }
            if ($value) { [Environment]::SetEnvironmentVariable($key, $value, 'Process') }
        }
    }
}
if ($FFmpegDirectory) { $env:PATH = "$FFmpegDirectory;$env:PATH" }
$knownMedia = 'D:\ffmpeg-8.1.1-essentials_build\bin'
if (!(Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath (Join-Path $knownMedia 'ffmpeg.exe'))) { $env:PATH = "$knownMedia;$env:PATH" }
foreach ($tool in @('ffmpeg','ffprobe')) {
    $override = [Environment]::GetEnvironmentVariable("CLIPFORGE_$($tool.ToUpperInvariant())", 'Process')
    if ($override) {
        if (!(Test-Path -LiteralPath $override -PathType Leaf)) { throw "Invalid CLIPFORGE_$($tool.ToUpperInvariant()) path: $override" }
    } elseif (!(Get-Command "$tool.exe" -ErrorAction SilentlyContinue)) { throw "$tool is missing. Install FFmpeg and add its bin directory to PATH, or pass -FFmpegDirectory." }
}
# Check availability without claiming a port owned by another application.
$listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
try { $listener.Start() } catch { throw "Port $Port is in use. Try .\start.ps1 -Port 8001" } finally { $listener.Stop() }
$url = "http://127.0.0.1:$Port"
Write-Host "ClipForge: $url"
Write-Host 'Press Ctrl+C to stop. Files and projects remain saved locally.'
$browserJob = $null
if (!$NoBrowser) {
    $browserJob = Start-Job -ArgumentList $url -ScriptBlock {
        param($address)
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            try {
                $null = Invoke-WebRequest -Uri "$address/api/health" -UseBasicParsing -TimeoutSec 1
                Start-Process $address
                break
            } catch { Start-Sleep -Milliseconds 500 }
        }
    }
}
Push-Location $projectRoot
try {
    & $python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 130) { throw "Server exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
    if ($browserJob) { Stop-Job $browserJob -ErrorAction SilentlyContinue; Remove-Job $browserJob -Force -ErrorAction SilentlyContinue }
}

