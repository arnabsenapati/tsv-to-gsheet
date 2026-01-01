# Starts the Cloud SQL Auth Proxy for the IIT JEE question bank instance.
# Usage examples:
#   ./cloud-sql-auth-proxy.ps1                  # default to 127.0.0.1:5432
#   ./cloud-sql-auth-proxy.ps1 -Port 15432      # override local port

param(
    [string]$ProxyPath = "C:\GCP\cloud-sql-proxy.x64.exe",
    [string]$Instance = "studentquestionbank-2b545:us-central1:iit-jee-question-bank",
    [int]$Port = 5432,
    [string]$ListenAddress = "127.0.0.1",
    [switch]$Login
)

# Optionally perform gcloud ADC login before starting the proxy.
if ($Login) {
    $gcloud = Get-Command gcloud -ErrorAction SilentlyContinue
    if (-not $gcloud) {
        Write-Error "gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install and ensure it's on PATH."
        exit 1
    }
    Write-Host "Running 'gcloud auth application-default login' to set Application Default Credentials..."
    & $gcloud.Source "auth" "application-default" "login"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "gcloud login failed (exit code $LASTEXITCODE)."
        exit $LASTEXITCODE
    }
}

# If the .exe is not present, try the non-.exe name (e.g., from a zip unzip).
if (-not (Test-Path $ProxyPath)) {
    # Try common local names from older downloads.
    $fallbacks = @(".\cloud_sql_proxy.exe", ".\cloud_sql_proxy", ".\cloud-sql-proxy.exe", ".\cloud-sql-proxy")
    foreach ($f in $fallbacks) {
        if (Test-Path $f) { $ProxyPath = $f; break }
    }
}

if (-not (Test-Path $ProxyPath)) {
    Write-Error "cloud_sql_proxy binary not found at '$ProxyPath'. Download it from https://cloud.google.com/sql/docs/postgres/sql-proxy."
    exit 1
}

# Build args for Cloud SQL Auth Proxy v2 (positional instance name plus address/port flags).
$proxyArgs = @(
    $Instance
    "--address=$ListenAddress"
    "--port=$Port"
)

Write-Host "Starting Cloud SQL Auth Proxy for instance '$Instance' on $ListenAddress`:$Port..."
& $ProxyPath @proxyArgs
