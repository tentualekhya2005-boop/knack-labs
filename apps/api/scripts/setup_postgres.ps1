$zipPath = "C:\Users\ALEKHYA\.gemini\antigravity\pgsql.zip"
$extractPath = "C:\Users\ALEKHYA\.pgsql"

if (-not (Test-Path "$extractPath\bin\postgres.exe")) {
    Write-Host "Extracting PostgreSQL binaries..."
    Expand-Archive -LiteralPath $zipPath -DestinationPath "C:\Users\ALEKHYA" -Force
}

$pgBin = "C:\Users\ALEKHYA\pgsql\bin"
$pgData = "C:\Users\ALEKHYA\pgsql\data"
$pgLog = "C:\Users\ALEKHYA\pgsql\logfile.log"

if (-not (Test-Path $pgData)) {
    Write-Host "Initializing PostgreSQL cluster with trust auth..."
    & "$pgBin\initdb.exe" -D $pgData -U postgres -A trust -E UTF8
}

Write-Host "Starting PostgreSQL server on port 5432..."
& "$pgBin\pg_ctl.exe" -D $pgData -o "-p 5432" -l $pgLog start

Start-Sleep -Seconds 3

Write-Host "Creating upsk_sdf database..."
& "$pgBin\createdb.exe" -U postgres -p 5432 upsk_sdf 2>$null
if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 1) {
    Write-Host "Database ready."
}

