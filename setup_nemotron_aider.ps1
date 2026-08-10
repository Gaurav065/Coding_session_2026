$ErrorActionPreference = "Stop"

# 1. Install Aider via pip
Write-Host "Installing Aider..." -ForegroundColor Cyan
python -m pip install aider-chat
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install Aider. Make sure Python and pip are installed." -ForegroundColor Red
    exit 1
}

# 2. Prompt for the API key (if you're using NVIDIA NIM, you can get it from build.nvidia.com)
$apiKey = Read-Host "Please enter your NVIDIA API Key (nvapi-...)"

# 3. Set the required environment variables for the current session
$env:OPENAI_API_KEY = $apiKey
$env:OPENAI_API_BASE = "https://integrate.api.nvidia.com/v1"

# Note: You might want to make these environment variables persistent in your PowerShell profile, 
# but for now we set them for this session.

Write-Host "`nEnvironment variables set successfully for this session!" -ForegroundColor Green
Write-Host "Starting Aider with Nemotron 3 Ultra..." -ForegroundColor Cyan

# 4. Launch Aider with Nemotron 3 Ultra
aider --model nvidia/nemotron-3-ultra
