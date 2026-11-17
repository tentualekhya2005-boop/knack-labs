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

Write-Host "Creating databases upsk_sdf and linkops..."
& "$pgBin\createdb.exe" -U postgres -p 5432 upsk_sdf 2>$null
& "$pgBin\createdb.exe" -U postgres -p 5432 linkops 2>$null

Write-Host "Checking pg_isready..."
& "$pgBin\pg_isready.exe" -U postgres -p 5432
