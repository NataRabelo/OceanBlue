param(
    [ValidateSet('red', 'green')][string]$Phase = 'green',
    [string]$Project = "oceanblue-s06-snapshot-$([guid]::NewGuid().ToString('N').Substring(0, 10))",
    [string]$EvidenceDirectory = 'docs/evidencias/producao/sprint-06-validacao/snapshot',
    [switch]$ExtendedOnly,
    [string]$Image = 'oceanblue-s06-release-smoke:latest',
    [string]$DatabaseImage = 'postgres:16@sha256:23af655ba1ddf74eaa002e3deaf5fce022ab8791672336a7c1fb0ef2d57efb7f'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
if ($Project -notmatch '^oceanblue-s0[67]-snapshot-[a-z0-9-]+$') { throw 'Exclusive snapshot project required.' }
$evidence = [IO.Path]::GetFullPath((Join-Path $workspace "$EvidenceDirectory/$Phase"))
if (Test-Path -LiteralPath $evidence) { throw 'Use a new evidence directory.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
$databaseContainer = "$Project-db"
$sourceApp = "$Project-source"
$targetApp = "$Project-target"
$snapshotScript = Join-Path $PSScriptRoot 'operational_snapshot.ps1'
$results = [Collections.Generic.List[object]]::new()
$label = "com.docker.compose.project=$Project"
function Docker {
    $output = & docker.exe @args 2>&1
    if ($LASTEXITCODE) { throw "Docker failed: $output" }
    $output
}
function Sql([string]$Statement, [string]$Name = 'source_db') {
    Docker exec $databaseContainer psql -X -v ON_ERROR_STOP=1 -U proof -d $Name -At -c $Statement
}
function Storage([string]$App, [string]$Code) {
    Docker run --rm --label $label --network none --user 0 --volumes-from $App --entrypoint python $image -c $Code
}
function Reset-Target {
    Docker exec $databaseContainer dropdb --if-exists --force -U proof target_db | Out-Null
    Docker exec $databaseContainer createdb -U proof target_db | Out-Null
    Storage $targetApp "import pathlib, shutil; root=pathlib.Path('/app/instance'); [(shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()) for p in root.iterdir()]; (root/'storage').mkdir()" | Out-Null
}
function Copy-Snapshot([string]$Name) {
    $path = Join-Path $evidence $Name
    Copy-Item -LiteralPath (Join-Path $evidence 'synthetic') -Destination $path -Recurse
    $path
}
function Save-Manifest([string]$Path, $Manifest) {
    $Manifest | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $Path 'manifest.json') -Encoding utf8
}
function Run-Snapshot([string]$Name, [string]$Mode, [string]$Path, [string]$Injection = '', [string]$App = '') {
    if (-not $App) { $App = if ($Mode -eq 'backup') { $sourceApp } else { $targetApp } }
    $db = if ($Mode -eq 'backup') { 'source_db' } else { 'target_db' }
    $trusted = if ($Mode -eq 'restore') { (Get-FileHash (Join-Path $Path 'manifest.json')).Hash } else { '' }
    if ($Name -eq 'custody-unpinned') { $trusted = '' }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    & pwsh -NoProfile -File (Join-Path $evidence 'driver.ps1') -SnapshotScript $snapshotScript -Mode $Mode -Project $Project -DatabaseContainer $databaseContainer -ApplicationContainer $App -Database $db -Directory $Path -Injection $Injection -TrustedManifestSha256 $trusted *> (Join-Path $evidence "$Name.log")
    $exitCode = $LASTEXITCODE
    $timer.Stop()
    [pscustomobject]@{exit_code=$exitCode; seconds=[Math]::Round($timer.Elapsed.TotalSeconds, 3); log="$Name.log"; script_sha256=(Get-FileHash $snapshotScript).Hash}
}
function Record([string]$Name, [bool]$Passed, $Observation) {
    $results.Add([ordered]@{case=$Name; passed=$Passed; observed=$Observation})
    $results | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath (Join-Path $evidence 'results.json') -Encoding utf8
    Write-Output "$Name : $Passed"
}
function Empty-Target {
    (Sql "SELECT count(*) FROM pg_tables WHERE schemaname='public'" 'target_db') -eq '0'
}
$driver = @'
param($SnapshotScript,$Mode,$Project,$DatabaseContainer,$ApplicationContainer,$Database,$Directory,$Injection,$TrustedManifestSha256)
$ErrorActionPreference = 'Stop'
$script:injected = $false
function docker {
    $arguments = @($args)
    $isStorageCopy = $arguments[0] -eq 'cp' -and $arguments[-1] -eq "${ApplicationContainer}:/app/instance"
    if ($Injection -in @('copy-failure','rollback-failure','interrupt','db-rollback-failure','hard-kill') -and $isStorageCopy -and -not $script:injected) {
        $script:injected = $true
        if ($Injection -eq 'interrupt') { throw [OperationCanceledException]::new('Injected interruption before storage copy') }
        & docker.exe @arguments 2>&1
        if ($Injection -eq 'hard-kill') {
            Set-Content -LiteralPath "$Directory.kill-ready" -Value 'Real storage copied; transaction not committed'
            while ($true) { Start-Sleep -Milliseconds 200 }
        }
        if ($Injection -eq 'db-rollback-failure') { & docker.exe exec $DatabaseContainer psql -U proof -d $Database -At -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND application_name LIKE 'oceanblue-snapshot-%'" }
        throw 'Injected storage-copy failure AFTER real copy'
    }
    if ($Injection -eq 'backup-failure' -and $arguments[0] -eq 'cp' -and $arguments[1] -like '*:/app/instance*') { throw 'Injected backup interruption' }
    if ($Injection -eq 'rollback-failure' -and $script:injected -and $arguments[0] -eq 'run') { throw 'Injected rollback helper failure' }
    if ($Injection -eq 'late-db-writer' -and $arguments -contains 'pg_dump') {
        & docker.exe @arguments 2>&1
        & docker.exe exec -d $DatabaseContainer psql -U proof -d $Database -c 'SELECT pg_sleep(90)' 2>&1
        $global:LASTEXITCODE = $LASTEXITCODE
        return
    }
    & docker.exe @arguments 2>&1
    $global:LASTEXITCODE = $LASTEXITCODE
}
try {
    $extra = @{}
    if ($TrustedManifestSha256) { $extra.ExpectedManifestSha256 = $TrustedManifestSha256 }
    if ($Injection -eq 'pinned') { $extra.ExpectedManifestSha256 = (Get-FileHash (Join-Path (Split-Path $Directory) 'synthetic/manifest.json')).Hash }
    & $SnapshotScript -Mode $Mode -Project $Project -DatabaseContainer $DatabaseContainer -ApplicationContainer $ApplicationContainer -Database $Database -DatabaseUser proof -Directory $Directory @extra
    exit 0
} catch {
    Write-Output $_
    exit 1
}
'@
$driver | Set-Content -LiteralPath (Join-Path $evidence 'driver.ps1') -Encoding utf8
$existing = Docker ps -aq --filter "label=$label"
if ($existing) { throw 'Project already exists.' }
try {
    Docker image inspect $image $DatabaseImage --format '{{.Id}}' | Set-Content (Join-Path $evidence 'images.txt')
    Docker run -d --name $databaseContainer --label $label --network none --tmpfs /var/lib/postgresql/data -e POSTGRES_USER=proof -e POSTGRES_PASSWORD=synthetic-only -e POSTGRES_DB=source_db $DatabaseImage | Out-Null
    foreach ($app in @($sourceApp, $targetApp)) {
        Docker volume create --label $label "$app-files" | Out-Null
        Docker create --name $app --label $label --network none --mount "type=volume,source=$app-files,target=/app/instance" --entrypoint sleep $image 600 | Out-Null
    }
    for ($attempt=0; $attempt -lt 60; $attempt++) {
        & docker.exe exec $databaseContainer pg_isready -U proof -d source_db *> $null
        if (-not $LASTEXITCODE) { break }
        Start-Sleep -Milliseconds 500
    }
    $head = (Docker run --rm --label $label --network none --entrypoint python $image -c 'from alembic.script import ScriptDirectory; print(ScriptDirectory("/app/migrations").get_current_head())' | Out-String).Trim()
    Sql "CREATE TABLE alembic_version(version_num varchar(32) PRIMARY KEY); INSERT INTO alembic_version VALUES ('$head'); CREATE TABLE proof_rows(id serial PRIMARY KEY, payload json, created_at timestamptz DEFAULT now()); INSERT INTO proof_rows(payload) VALUES ('{`"z`":1,`"a`":2}'), ('{`"a`":3}'); CREATE TABLE z_empty(id integer);" | Out-Null
    Storage $sourceApp "from pathlib import Path; root=Path('/app/instance/storage'); root.mkdir(exist_ok=True); (root/'proof.txt').write_text('synthetic-only: two records\n')" | Out-Null
    $backup = Run-Snapshot 'backup' 'backup' (Join-Path $evidence 'synthetic')
    Record 'backup-valid' ($backup.exit_code -eq 0) $backup
    if ($backup.exit_code) { throw 'Cannot continue without baseline snapshot.' }
    Reset-Target
    $restore = Run-Snapshot 'roundtrip' 'restore' (Join-Path $evidence 'synthetic')
    Record 'roundtrip' ($restore.exit_code -eq 0) $restore
    $recoveredRows = Sql 'SELECT count(*) FROM proof_rows' 'target_db'
    $recoveredSequence = Sql 'SELECT last_value FROM proof_rows_id_seq' 'target_db'
    $recoveredReceipt = (Storage $targetApp "from pathlib import Path; print(Path('/app/instance/storage/proof.txt').read_text().strip())" | Out-String).Trim()
    Record 'independent-recovery' ($recoveredRows -eq '2' -and $recoveredSequence -eq '2' -and $recoveredReceipt -eq 'synthetic-only: two records') @{rows=$recoveredRows; sequence=$recoveredSequence; receipt=$recoveredReceipt; backup_seconds=$backup.seconds; restore_seconds=$restore.seconds; lost_captured_records=0}
    if (-not $ExtendedOnly) {
    Sql "UPDATE alembic_version SET version_num='wrong_revision'" | Out-Null
    $wrong = Run-Snapshot 'backup-wrong-revision' 'backup' (Join-Path $evidence 'wrong-revision')
    Record 'backup-wrong-revision' ($wrong.exit_code -ne 0) $wrong
    Sql "UPDATE alembic_version SET version_num='$head'" | Out-Null
    foreach ($change in @('format-version','fingerprint-order','fingerprint-content','file-hash','traversal','manifest-pinned','custody-unpinned','restore-wrong-revision','postgres-version')) {
        Reset-Target
        $path = Copy-Snapshot $change
        $manifest = Get-Content -Raw (Join-Path $path 'manifest.json') | ConvertFrom-Json -AsHashtable
        switch ($change) {
            'format-version' { $manifest.version = 999 }
            'fingerprint-order' {
                $ordered = [ordered]@{}
                foreach ($key in @($manifest.database_fingerprint.Keys | Sort-Object -Descending)) { $ordered[$key] = $manifest.database_fingerprint[$key] }
                $manifest.database_fingerprint = $ordered
            }
            'fingerprint-content' { $manifest.database_fingerprint['proof_rows'] = '2:00000000000000000000000000000000' }
            'file-hash' { [IO.File]::AppendAllText((Join-Path $path 'instance/storage/proof.txt'), 'tampered') }
            'traversal' { $manifest.files['../escape'] = ('0' * 64) }
            'manifest-pinned' { $manifest.created_utc = '2000-01-01T00:00:00Z' }
            'custody-unpinned' {
                [IO.File]::AppendAllText((Join-Path $path 'instance/storage/proof.txt'), 'rewritten with its checksum')
                $manifest.files['instance/storage/proof.txt'] = (Get-FileHash (Join-Path $path 'instance/storage/proof.txt')).Hash.ToLowerInvariant()
            }
            'restore-wrong-revision' { $manifest.schema_revision = 'wrong_revision' }
            'postgres-version' { $manifest.postgres_major = 999 }
        }
        Save-Manifest $path $manifest
        $injection = if ($change -eq 'manifest-pinned') { 'pinned' } else { '' }
        $run = Run-Snapshot $change 'restore' $path $injection
        $empty = Empty-Target
        $pass = if ($change -eq 'fingerprint-order') { $run.exit_code -eq 0 } else { $run.exit_code -ne 0 -and $empty }
        Record $change $pass @{run=$run; database_empty=$empty}
    }
    foreach ($kind in @('table','schema','sequence','function','storage','storage-link')) {
        Reset-Target
        switch ($kind) {
            'table' { Sql 'CREATE TABLE sentinel(id integer); INSERT INTO sentinel VALUES (73)' 'target_db' | Out-Null }
            'schema' { Sql 'CREATE SCHEMA sentinel; CREATE TABLE sentinel.proof(id integer)' 'target_db' | Out-Null }
            'sequence' { Sql 'CREATE SEQUENCE sentinel' 'target_db' | Out-Null }
            'function' { Sql 'CREATE FUNCTION sentinel() RETURNS integer LANGUAGE sql AS $$ SELECT 73 $$' 'target_db' | Out-Null }
            'storage' { Storage $targetApp "from pathlib import Path; Path('/app/instance/storage/sentinel').write_text('preserve')" | Out-Null }
            'storage-link' { Storage $targetApp "import os; os.symlink('/tmp', '/app/instance/storage/link')" | Out-Null }
        }
        $path = Copy-Snapshot "nonempty-$kind"
        $run = Run-Snapshot "nonempty-$kind" 'restore' $path
        $noRestore = (Sql "SELECT to_regclass('public.proof_rows') IS NULL" 'target_db') -eq 't'
        Record "nonempty-$kind" ($run.exit_code -ne 0 -and $noRestore) @{run=$run; snapshot_table_absent=$noRestore}
    }
    foreach ($injection in @('copy-failure','interrupt','rollback-failure')) {
        Reset-Target
        $path = Copy-Snapshot $injection
        $run = Run-Snapshot $injection 'restore' $path $injection
        $empty = Empty-Target
        $state = (Storage $targetApp "from pathlib import Path; import json; print(json.dumps(sorted(str(p.relative_to('/app/instance')) for p in Path('/app/instance').rglob('*'))))" | Out-String).Trim()
        $safeStorage = if ($injection -eq 'rollback-failure') { $state.Contains('.oceanblue-restore-incomplete') } else { -not $state.Contains('proof.txt') }
        Record $injection ($run.exit_code -ne 0 -and $empty -and $safeStorage) @{run=$run; database_empty=$empty; storage=$state}
    }
    $path = Join-Path $evidence 'interrupted-backup'
    $run = Run-Snapshot 'interrupted-backup' 'backup' $path 'backup-failure'
    Record 'interrupted-backup' ($run.exit_code -ne 0 -and -not (Test-Path (Join-Path $path 'manifest.json'))) $run
    Docker start $sourceApp | Out-Null
    $run = Run-Snapshot 'active-app' 'backup' (Join-Path $evidence 'active-app')
    Record 'active-app' ($run.exit_code -ne 0) $run
    Docker stop $sourceApp | Out-Null
    Docker exec -d $databaseContainer psql -U proof -d source_db -c 'SELECT pg_sleep(90)' | Out-Null
    Start-Sleep -Milliseconds 500
    $run = Run-Snapshot 'active-db-client' 'backup' (Join-Path $evidence 'active-client')
    Record 'active-db-client' ($run.exit_code -ne 0) $run
    Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()" | Out-Null
    Docker run -d --name "$Project-writer" --label $label --network none --volumes-from $sourceApp --entrypoint sleep $image 180 | Out-Null
    $run = Run-Snapshot 'shared-storage-writer' 'backup' (Join-Path $evidence 'shared-writer')
    Record 'shared-storage-writer' ($run.exit_code -ne 0) $run
    Docker rm -f "$Project-writer" | Out-Null
    $junction = Join-Path $evidence 'root-junction'
    New-Item -ItemType Junction -Path $junction -Target (Join-Path $evidence 'synthetic') | Out-Null
    Reset-Target
    $run = Run-Snapshot 'root-junction' 'restore' $junction
    Record 'root-junction' ($run.exit_code -ne 0 -and (Empty-Target)) $run
    Remove-Item -LiteralPath $junction -Force
    }
    if ($Phase -eq 'green') {
        Reset-Target
        $path = Copy-Snapshot 'db-rollback-failure'
        $run = Run-Snapshot 'db-rollback-failure' 'restore' $path 'db-rollback-failure'
        $state = (Storage $targetApp "from pathlib import Path; print(Path('/app/instance/.oceanblue-restore-incomplete').exists())" | Out-String).Trim()
        Record 'db-rollback-failure' ($run.exit_code -ne 0 -and (Empty-Target) -and $state -eq 'True') @{run=$run; database_empty=(Empty-Target); incomplete_marker=$state}
        $run = Run-Snapshot 'retry-incomplete' 'restore' $path
        Record 'retry-incomplete' ($run.exit_code -ne 0 -and (Empty-Target)) $run
        $run = Run-Snapshot 'late-db-writer' 'backup' (Join-Path $evidence 'late-db-writer') 'late-db-writer'
        Record 'late-db-writer' ($run.exit_code -ne 0 -and -not (Test-Path (Join-Path $evidence 'late-db-writer/manifest.json'))) $run
        Sql "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()" | Out-Null
        Storage $sourceApp "import os; os.symlink('/tmp', '/app/instance/storage/link')" | Out-Null
        $run = Run-Snapshot 'source-link' 'backup' (Join-Path $evidence 'source-link')
        Record 'source-link' ($run.exit_code -ne 0) $run
        Storage $sourceApp "from pathlib import Path; Path('/app/instance/storage/link').unlink()" | Out-Null
        Reset-Target
        $path = Copy-Snapshot 'hard-kill'
        $start = [Diagnostics.ProcessStartInfo]::new()
        $start.FileName = (Get-Command pwsh).Source
        foreach ($argument in @('-NoProfile','-File',(Join-Path $evidence 'driver.ps1'),'-SnapshotScript',$snapshotScript,'-Mode','restore','-Project',$Project,'-DatabaseContainer',$databaseContainer,'-ApplicationContainer',$targetApp,'-Database','target_db','-Directory',$path,'-Injection','hard-kill','-TrustedManifestSha256',(Get-FileHash (Join-Path $path 'manifest.json')).Hash)) { $start.ArgumentList.Add($argument) }
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        $child = [Diagnostics.Process]::Start($start)
        $output = $child.StandardOutput.ReadToEndAsync()
        $errors = $child.StandardError.ReadToEndAsync()
        $timer = [Diagnostics.Stopwatch]::StartNew()
        while (-not (Test-Path -LiteralPath "$path.kill-ready") -and -not $child.HasExited -and $timer.Elapsed.TotalSeconds -lt 100) { Start-Sleep -Milliseconds 200 }
        $reached = Test-Path -LiteralPath "$path.kill-ready"
        if (-not $child.HasExited) { $child.Kill() }
        $child.WaitForExit()
        $output.Result + $errors.Result | Set-Content (Join-Path $evidence 'hard-kill.log')
        $timer.Restart()
        do {
            $sessions = Sql "SELECT count(*) FROM pg_stat_activity WHERE application_name LIKE 'oceanblue-snapshot-%'" 'target_db'
            if ($sessions -eq '0') { break }
            Start-Sleep -Milliseconds 500
        } while ($timer.Elapsed.TotalSeconds -lt 75)
        $state = (Storage $targetApp "from pathlib import Path; print(Path('/app/instance/.oceanblue-restore-incomplete').exists())" | Out-String).Trim()
        Record 'hard-kill' ($reached -and $sessions -eq '0' -and (Empty-Target) -and $state -eq 'True') @{reached_after_copy=$reached; sql_sessions=$sessions; database_empty=(Empty-Target); marker=$state; rollback_observed_seconds=[Math]::Round($timer.Elapsed.TotalSeconds,3)}
        $child.Dispose()
    }
} finally {
    $containers = @(Docker ps -aq --filter "label=$label")
    if ($containers.Count) { Docker rm -f @containers | Out-Null }
    $volumes = @(Docker volume ls -q --filter "label=$label")
    if ($volumes.Count) { Docker volume rm @volumes | Out-Null }
    $summary = [ordered]@{phase=$Phase; project=$Project; utc=[DateTime]::UtcNow.ToString('o'); script_sha256=(Get-FileHash $snapshotScript).Hash; cases=$results.Count; passed=@($results | Where-Object passed).Count; failed=@($results | Where-Object { -not $_.passed }).Count; postgres='16 real, network none'; external_integrations=$false; resources_removed=$true}
    $summary | ConvertTo-Json -Depth 8 | Set-Content (Join-Path $evidence 'summary.json')
}
if ($Phase -eq 'green' -and @($results | Where-Object { -not $_.passed }).Count) { throw 'Adversarial validation failed; see results.json.' }
