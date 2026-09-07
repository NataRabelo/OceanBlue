param([string]$Project = "oceanblue-s06-snapshot-extra-$([guid]::NewGuid().ToString('N').Substring(0,8))")
$ErrorActionPreference = 'Stop'
if ($Project -notmatch '^oceanblue-s06-snapshot-[a-z0-9-]+$') { throw 'Exclusive snapshot project required.' }
$workspace = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../../..'))
$scriptPath = Join-Path $workspace 'scripts/operational_snapshot.ps1'
$evidence = Join-Path $PSScriptRoot 'supplemental-final'
if (Test-Path -LiteralPath $evidence) { throw 'Evidence exists.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$label = "com.docker.compose.project=$Project"
$databaseContainer = "$Project-db"
$app = "$Project-app"
$image = 'oceanblue-s06-release-smoke:latest'
$results = [Collections.Generic.List[object]]::new()
function Docker {
    $output = & docker.exe @args 2>&1
    if ($LASTEXITCODE) { throw "Isolated Docker operation failed: $output" }
    $output
}
function Sql([string]$Statement) { Docker exec $databaseContainer psql -X -U proof -d target_db -At -v ON_ERROR_STOP=1 -c $Statement }
if (Docker ps -aq --filter "label=$label") { throw 'Project exists.' }
try {
    Docker run -d --name $databaseContainer --label $label --network none --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=proof -e POSTGRES_PASSWORD=synthetic-only -e POSTGRES_DB=target_db postgres:16 | Out-Null
    Docker volume create --label $label "$app-files" | Out-Null
    Docker create --name $app --label $label --network none --mount "type=volume,source=$app-files,target=/app/instance" --entrypoint sleep $image 600 | Out-Null
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        & docker.exe exec $databaseContainer pg_isready -U proof -d target_db *> $null
        if (-not $LASTEXITCODE) { break }
        Start-Sleep -Milliseconds 500
    }
    foreach ($name in @('dump-wrong-revision', 'forged-custody', 'invalid-archive')) {
        $path = Join-Path $evidence $name
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'accepted/green/synthetic') -Destination $path -Recurse
        $manifest = Get-Content -LiteralPath (Join-Path $path 'manifest.json') -Raw | ConvertFrom-Json -AsHashtable
        $trusted = (Get-FileHash (Join-Path $path 'manifest.json')).Hash
        switch ($name) {
            'dump-wrong-revision' {
                Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'red/wrong-revision/database.dump') -Destination (Join-Path $path 'database.dump') -Force
                $manifest.files['database.dump'] = (Get-FileHash (Join-Path $path 'database.dump')).Hash.ToLowerInvariant()
            }
            'forged-custody' {
                [IO.File]::AppendAllText((Join-Path $path 'instance/storage/proof.txt'), 'forged')
                $manifest.files['instance/storage/proof.txt'] = (Get-FileHash (Join-Path $path 'instance/storage/proof.txt')).Hash.ToLowerInvariant()
                $manifest.created_utc = '2000-01-01T00:00:00Z'
            }
            'invalid-archive' {
                [IO.File]::WriteAllText((Join-Path $path 'database.dump'), 'not a PostgreSQL archive')
                $manifest.files['database.dump'] = (Get-FileHash (Join-Path $path 'database.dump')).Hash.ToLowerInvariant()
            }
        }
        $manifest | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath (Join-Path $path 'manifest.json') -Encoding utf8
        if ($name -ne 'forged-custody') { $trusted = (Get-FileHash (Join-Path $path 'manifest.json')).Hash }
        $timer = [Diagnostics.Stopwatch]::StartNew()
        & pwsh -NoProfile -File $scriptPath -Mode restore -Project $Project -DatabaseContainer $databaseContainer -ApplicationContainer $app -Database target_db -DatabaseUser proof -Directory $path -ExpectedManifestSha256 $trusted *> (Join-Path $evidence "$name.log")
        $code = $LASTEXITCODE
        $timer.Stop()
        $empty = (Sql "SELECT count(*) FROM pg_tables WHERE schemaname='public'") -eq '0'
        $storage = (Docker run --rm --label $label --network none --user 0 --volumes-from "${app}:ro" --entrypoint python $image -c "from pathlib import Path; import json; print(json.dumps(sorted(str(path.relative_to('/app/instance')) for path in Path('/app/instance').rglob('*'))))" | Out-String).Trim()
        $log = Get-Content -LiteralPath (Join-Path $evidence "$name.log") -Raw
        $expected = switch ($name) { 'dump-wrong-revision' { 'Database schema revision does not match' }; 'forged-custody' { 'Manifest custody SHA-256 mismatch' }; 'invalid-archive' { 'Docker operation failed' } }
        $passed = $code -ne 0 -and $empty -and -not $storage.Contains('proof.txt') -and $log.Contains($expected)
        $results.Add(@{case=$name; passed=$passed; exit_code=$code; database_empty=$empty; storage=$storage; seconds=$timer.Elapsed.TotalSeconds; expected_failure=$expected; trusted_manifest_sha256=$trusted})
        $results | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidence 'results.json')
        Write-Output "$name : $passed"
    }
} finally {
    $containers = @(Docker ps -aq --filter "label=$label")
    if ($containers.Count) { Docker rm -f @containers | Out-Null }
    $volumes = @(Docker volume ls -q --filter "label=$label")
    if ($volumes.Count) { Docker volume rm @volumes | Out-Null }
    @{project=$Project; script_sha256=(Get-FileHash $scriptPath).Hash; cases=$results.Count; passed=@($results | Where-Object passed).Count; resources_removed=$true} | ConvertTo-Json | Set-Content (Join-Path $evidence 'summary.json')
}
if (@($results | Where-Object { -not $_.passed }).Count) { throw 'Supplemental proof failed.' }
