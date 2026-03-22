$PBF_URL  = "https://download.geofabrik.de/europe/slovakia-latest.osm.pbf"
$PBF_FILE = "data\slovakia-latest.osm.pbf"

if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }

if (-not (Test-Path $PBF_FILE)) {
    Write-Host "Downloading Slovakia OSM extract (~300 MB)..."
    Invoke-WebRequest -Uri $PBF_URL -OutFile $PBF_FILE
    $PbfDate = Get-Date -Format "yyyy-MM-dd"
} else {
    Write-Host "PBF file already exists, skipping download."
    $PbfDate = (Get-Item $PBF_FILE).LastWriteTime.ToString("yyyy-MM-dd")
}

Write-Host "Stopping any existing containers..."
try { docker compose down 2>&1 | Out-Null } catch {}
foreach ($name in @("postgis_osm", "martin")) {
    try { docker rm -f $name 2>&1 | Out-Null } catch {}
}

Write-Host "Building and starting PostGIS..."
docker compose up -d --build postgis

Write-Host "Waiting for PostGIS to be ready..."
do {
    Start-Sleep -Seconds 2
    docker compose exec postgis pg_isready -U osmuser -d osm 2>$null | Out-Null
} until ($LASTEXITCODE -eq 0)
Write-Host "PostGIS is ready."

Write-Host "Loading OSM data with osm2pgsql (this may take several minutes)..."
docker compose exec postgis osm2pgsql `
    --create --slim --hstore `
    -d osm -U osmuser `
    /data/slovakia-latest.osm.pbf
if ($LASTEXITCODE -ne 0) { Write-Error "osm2pgsql failed"; exit 1 }

Write-Host "Creating streets vector-tile function..."
docker compose exec -T postgis psql -U osmuser -d osm -f /init.sql
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to create streets function"; exit 1 }

Write-Host "Recording PBF extract date in database ($PbfDate)..."
$insertDateSql = "INSERT INTO osm_metadata (key, value) VALUES ('data_date', '$PbfDate') ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;"
docker compose exec -T postgis psql -U osmuser -d osm -c $insertDateSql
if ($LASTEXITCODE -ne 0) { Write-Error "Failed to set data_date metadata"; exit 1 }

Write-Host "Starting Martin tile server..."
docker compose up -d martin

Write-Host ""
Write-Host "===== Setup complete ====="
Write-Host "PostGIS:  localhost:5434  (user: osmuser, password: osmpass, db: osm)"
Write-Host "Martin:   http://localhost:3001"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Copy src\.env.example to src\.env and fill in your API keys"
Write-Host "  2. pip install -r requirements.txt"
Write-Host "  3. python -m src.analysis.compute"
