param(
    [Parameter(Mandatory)][ValidateSet('backup', 'restore')][string]$Mode,
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$DatabaseContainer,
    [Parameter(Mandatory)][string]$ApplicationContainer,
    [Parameter(Mandatory)][string]$Database,
    [Parameter(Mandatory)][string]$DatabaseUser,
    [Parameter(Mandatory)][string]$Directory,
    [ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedManifestSha256
)

$ErrorActionPreference = 'Stop'
if ($Mode -eq 'restore' -and -not $ExpectedManifestSha256) { throw 'Restore requires ExpectedManifestSha256 from a separately trusted backup capture; do not derive trust from the supplied snapshot.' }
if ($Project -notmatch '^[a-z][a-z0-9-]+$' -or $Database -notmatch '^[a-z][a-z0-9_]+$' -or $DatabaseUser -notmatch '^[a-z][a-z0-9_]+$') { throw 'Invalid project/database identifier.' }
$snapshotRoot = [IO.Path]::GetFullPath($Directory)
$operation = [guid]::NewGuid().ToString('N')
$remoteDump = "/tmp/oceanblue-snapshot-$operation.dump"
$remoteSql = "/tmp/oceanblue-snapshot-$operation.sql"
$staging = "$snapshotRoot.partial-$operation"
$verification = "$snapshotRoot.verify-$operation"
$session = $null
$restoreTouched = $false
$commitAttempted = $false
$databaseValidated = $false
$marker = '.oceanblue-restore-incomplete'
function Invoke-Docker {
    param([string[]]$Arguments)
    $result = & docker @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw 'Docker operation failed; inspect the isolated container. No credentials printed.' }
    return $result
}
function Assert-NoLinks {
    param([string]$Path)
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            if ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Links are forbidden in snapshots and their ancestors.' }
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}
function New-PrivateDirectory {
    param([string]$Path)
    Assert-NoLinks $Path
    New-Item -ItemType Directory -Path $Path | Out-Null
    if ($IsWindows) {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        & icacls $Path /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
    } else { & chmod 700 $Path }
    if ($LASTEXITCODE -ne 0) { throw 'Could not restrict snapshot permissions.' }
}
function Get-FileManifest {
    param([string]$Root)
    Assert-NoLinks $Root
    $result = [ordered]@{}
    foreach ($entry in Get-ChildItem -LiteralPath $Root -Recurse -Force | Sort-Object FullName) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Links are forbidden in snapshots.' }
        if (-not $entry.PSIsContainer) {
            $relative = [IO.Path]::GetRelativePath($Root, $entry.FullName).Replace('\', '/')
            $result[$relative] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    }
    return $result
}
function Test-EqualMap {
    param($Expected, $Actual)
    if ($Expected -isnot [Collections.IDictionary] -or $Actual -isnot [Collections.IDictionary] -or $Expected.Count -ne $Actual.Count) { return $false }
    foreach ($key in $Expected.Keys) {
        if (@($Actual.Keys) -cnotcontains $key -or [string]$Expected[$key] -cne [string]$Actual[$key]) { return $false }
    }
    return $true
}
function Invoke-Sql {
    param([string]$Sql)
    if (-not $session) { return Invoke-Docker @('exec', $DatabaseContainer, 'psql', '-X', '-v', 'ON_ERROR_STOP=1', '-U', $DatabaseUser, '-d', $Database, '-At', '-c', $Sql) }
    $token = "snapshot_$([guid]::NewGuid().ToString('N'))"
    $session.StandardInput.WriteLine($Sql)
    $session.StandardInput.WriteLine("\echo $token")
    $session.StandardInput.Flush()
    $lines = [Collections.Generic.List[string]]::new()
    while ($true) {
        $pending = $session.StandardOutput.ReadLineAsync()
        if (-not $pending.Wait(120000)) { throw 'Snapshot SQL session timed out; leave application stopped.' }
        $line = $pending.Result
        if ($null -eq $line) { throw 'Snapshot SQL session failed; transaction is not accepted.' }
        if ($line -ceq $token) { break }
        if ($line.Length) { $lines.Add($line) }
    }
    return $lines.ToArray()
}
function Start-SqlSession {
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = if ($IsWindows) { 'docker.exe' } else { 'docker' }
    foreach ($argument in @('exec', '-i', '-e', "PGAPPNAME=oceanblue-snapshot-$operation", $DatabaseContainer, 'psql', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-U', $DatabaseUser, '-d', $Database)) { $start.ArgumentList.Add($argument) }
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardInput = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $script:session = [Diagnostics.Process]::Start($start)
    $script:sessionErrors = $session.StandardError.ReadToEndAsync()
    Invoke-Sql "BEGIN; SET LOCAL idle_in_transaction_session_timeout='60s'; SET LOCAL statement_timeout='120s'; SET LOCAL timezone='UTC'; SET LOCAL extra_float_digits=3;" | Out-Null
    if ((Invoke-Sql 'SELECT pg_try_advisory_xact_lock(186872945, hashtext(current_database()));') -ne 't') { throw 'Another snapshot operation holds the database lock.' }
}
function Assert-Quiescent {
    foreach ($container in @($DatabaseContainer, $ApplicationContainer)) {
        $metadata = (Invoke-Docker @('inspect', $container) | Out-String | ConvertFrom-Json)[0]
        if ($metadata.Config.Labels.'com.docker.compose.project' -ne $Project) { throw 'Container outside selected project.' }
        if ($container -eq $DatabaseContainer) { $script:databaseValidated = $true }
        if ($container -eq $ApplicationContainer) {
            if ($metadata.State.Running) { throw 'Stop application and all writers before taking or restoring a snapshot.' }
            $script:appMetadata = $metadata
            $script:storageMount = @($metadata.Mounts | Where-Object Destination -eq '/app/instance')
            if ($storageMount.Count -ne 1 -or -not $storageMount[0].RW) { throw 'Application storage must be a writable persistent mount.' }
            if (@($metadata.Mounts | Where-Object { $_.Destination.StartsWith('/app/instance/') }).Count) { throw 'Nested storage mounts are unsupported.' }
        }
    }
    $running = @(Invoke-Docker @('ps', '-q'))
    if ($running.Count) {
        $dockerExecutable = (Get-Command docker -CommandType Application | Select-Object -First 1).Source
        $inspection = & $dockerExecutable inspect @running 2>$null | Out-String
        $inspectionExit = $LASTEXITCODE
        $allMetadata = $inspection | ConvertFrom-Json
        if ($inspectionExit -ne 0) {
            $stillRunning = @(Invoke-Docker @('ps', '-q'))
            foreach ($identifier in $running) {
                if ($identifier -in $stillRunning -and -not @($allMetadata | Where-Object { $_.Id.StartsWith($identifier) }).Count) { throw 'Could not inspect a running container for storage writers.' }
            }
        }
        foreach ($candidate in $allMetadata) {
            foreach ($mount in $candidate.Mounts) {
                $source = $storageMount[0].Source.TrimEnd('/')
                $other = $mount.Source.TrimEnd('/')
                if ($mount.RW -and ($source -eq $other -or $source.StartsWith("$other/") -or $other.StartsWith("$source/"))) { throw 'Running container shares writable application storage. Stop all writers.' }
            }
        }
    }
    Invoke-Sql 'SELECT pg_stat_clear_snapshot();' | Out-Null
    if ([int](Invoke-Sql "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND backend_type='client backend';") -ne 0) { throw 'Other database clients remain. Stop all writers.' }
    if ([int](Invoke-Sql 'SELECT count(*) FROM pg_prepared_xacts WHERE database=current_database();') -ne 0) { throw 'Prepared database transactions remain.' }
}
function Invoke-Storage {
    param([string]$Code, [switch]$Writable)
    $volume = if ($Writable) { $ApplicationContainer } else { "${ApplicationContainer}:ro" }
    Invoke-Docker @('run', '--rm', '--label', "com.docker.compose.project=$Project", '--network', 'none', '--user', '0', '--volumes-from', $volume, '--entrypoint', 'python', $appMetadata.Image, '-c', $Code)
}
function Get-StorageInventory {
    $code = @'
import hashlib, json, os, stat
root = '/app/instance'
result = {}
if not stat.S_ISDIR(os.lstat(root).st_mode):
    raise RuntimeError('Storage root must be a directory, without links')
for parent, directories, files in os.walk(root, followlinks=False):
    for name in directories + files:
        path = os.path.join(parent, name)
        mode = os.lstat(path).st_mode
        relative = os.path.relpath(path, root).replace(os.sep, '/')
        if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            raise RuntimeError('Links and special files are forbidden in storage')
        if stat.S_ISDIR(mode):
            result[relative + '/'] = 'directory'
        else:
            with open(path, 'rb') as stream:
                result[relative] = hashlib.file_digest(stream, 'sha256').hexdigest()
print(json.dumps(result, sort_keys=True))
'@
    return Invoke-Storage $code | Out-String | ConvertFrom-Json -AsHashtable
}
function Get-DatabaseFingerprint {
    $result = [ordered]@{}
    foreach ($table in (Invoke-Sql "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")) {
        if ($table -notmatch '^[a-z][a-z0-9_]+$') { throw 'Unexpected table identifier.' }
        $result[$table] = [string](Invoke-Sql "SELECT count(*) || ':' || md5(coalesce(string_agg(md5(row_to_json(records)::text), '' ORDER BY md5(row_to_json(records)::text)), '')) FROM public.$table records;")
    }
    foreach ($sequence in (Invoke-Sql "SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename;")) {
        if ($sequence -notmatch '^[a-z][a-z0-9_]+$') { throw 'Unexpected sequence identifier.' }
        $result["sequence:$sequence"] = [string](Invoke-Sql "SELECT last_value || ':' || is_called FROM public.$sequence;")
    }
    return $result
}
function Assert-EmptyDatabase {
    $count = Invoke-Sql @'
SELECT
 (SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%') +
 (SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace) +
 (SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace) +
 (SELECT count(*) FROM pg_type WHERE typnamespace='public'::regnamespace) +
 (SELECT count(*) FROM pg_extension WHERE extname<>'plpgsql') +
 (SELECT count(*) FROM pg_largeobject_metadata) +
 (SELECT count(*) FROM pg_event_trigger) + (SELECT count(*) FROM pg_foreign_server) +
 (SELECT count(*) FROM pg_publication) + (SELECT count(*) FROM pg_subscription) +
 (SELECT count(*) FROM pg_default_acl);
'@
    if ([int]$count -ne 0) { throw 'Restore requires a new empty database, without user objects in any schema.' }
}
function Assert-SchemaRevision {
    if ((Invoke-Sql "SELECT to_regclass('public.alembic_version') IS NOT NULL;") -ne 't') { throw 'Database schema revision missing.' }
    if ([string](Invoke-Sql 'SELECT version_num FROM public.alembic_version ORDER BY version_num;') -cne $schemaRevision) { throw 'Database schema revision does not match application image.' }
}
try {
    Assert-NoLinks $snapshotRoot
    Assert-Quiescent
    $schemaRevision = (Invoke-Docker @('run', '--rm', '--label', "com.docker.compose.project=$Project", '--network', 'none', '--entrypoint', 'python', $appMetadata.Image, '-c', 'from alembic.script import ScriptDirectory; print(ScriptDirectory("/app/migrations").get_current_head())') | Out-String).Trim()
    if ($schemaRevision -notmatch '^[a-zA-Z0-9_]+$') { throw 'Application must have one known migration head.' }
    $postgresMajor = [int](Invoke-Sql 'SELECT current_setting(''server_version_num'')::integer / 10000;')
    $storageBefore = Get-StorageInventory
    if ($storageBefore.Contains($marker)) { throw 'Incomplete restore marker present. Keep application stopped and recover or replace this destination.' }
    Start-SqlSession
    Assert-Quiescent
    if ($Mode -eq 'backup') {
        if (Test-Path -LiteralPath $snapshotRoot) { throw 'Use a new snapshot directory; never overwrite a backup.' }
        Assert-SchemaRevision
        if ([int](Invoke-Sql "SELECT count(*) FROM pg_namespace WHERE nspname NOT IN ('public','information_schema') AND nspname NOT LIKE 'pg_%';") -ne 0 -or [int](Invoke-Sql 'SELECT count(*) FROM pg_largeobject_metadata;') -ne 0) { throw 'Snapshot fingerprints support public schema and filesystem storage only.' }
        New-PrivateDirectory $staging
        $before = Get-DatabaseFingerprint
        Invoke-Docker @('exec', $DatabaseContainer, 'pg_dump', '-U', $DatabaseUser, '-d', $Database, '--format=custom', '--no-owner', '--no-acl', '--file', $remoteDump) | Out-Null
        Invoke-Docker @('cp', "${DatabaseContainer}:$remoteDump", (Join-Path $staging 'database.dump')) | Out-Null
        Invoke-Docker @('cp', "${ApplicationContainer}:/app/instance", (Join-Path $staging 'instance')) | Out-Null
        $after = Get-DatabaseFingerprint
        Assert-Quiescent
        if (-not (Test-EqualMap $before $after)) { throw 'Database changed during backup; snapshot is not accepted.' }
        $storageAfter = Get-StorageInventory
        if (-not (Test-EqualMap $storageBefore $storageAfter)) { throw 'Storage changed during backup; snapshot is not accepted.' }
        $expectedFiles = [ordered]@{}
        foreach ($key in $storageAfter.Keys) { if (-not $key.EndsWith('/')) { $expectedFiles[$key] = $storageAfter[$key] } }
        if (-not (Test-EqualMap $expectedFiles (Get-FileManifest (Join-Path $staging 'instance')))) { throw 'Copied storage invariant mismatch.' }
        $manifest = [ordered]@{version=2; database=$Database; schema_revision=$schemaRevision; postgres_major=$postgresMajor; application_image=$appMetadata.Image; database_fingerprint=$after; files=(Get-FileManifest $staging); created_utc=[DateTime]::UtcNow.ToString('o')}
        $manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $staging 'manifest.json')
        Assert-NoLinks $snapshotRoot
        [IO.Directory]::Move($staging, $snapshotRoot)
        Write-Output "BACKUP VERIFIED: schema revision, tables, sequences and file SHA-256. Manifest SHA-256: $((Get-FileHash (Join-Path $snapshotRoot 'manifest.json')).Hash.ToLowerInvariant())"
    } else {
        $manifestPath = Join-Path $snapshotRoot 'manifest.json'
        if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Snapshot manifest missing.' }
        $actual = Get-FileManifest $snapshotRoot
        if ($actual['manifest.json'] -ine $ExpectedManifestSha256) { throw 'Manifest custody SHA-256 mismatch.' }
        $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -AsHashtable
        if ($manifest.version -ne 2 -or $manifest.version -is [string]) { throw 'Unsupported snapshot manifest version; create a version 2 snapshot.' }
        if ($manifest.schema_revision -cne $schemaRevision) { throw 'Snapshot schema revision does not match application image.' }
        if ($manifest.postgres_major -ne $postgresMajor) { throw 'Snapshot PostgreSQL major version mismatch.' }
        if ($manifest.files -isnot [Collections.IDictionary] -or $manifest.database_fingerprint -isnot [Collections.IDictionary]) { throw 'Invalid snapshot manifest maps.' }
        foreach ($key in $manifest.files.Keys) {
            if ($key -ceq "instance/$marker") { throw 'Snapshot contains an incomplete restore marker.' }
            if (($key -cne 'database.dump' -and -not $key.StartsWith('instance/', [StringComparison]::Ordinal)) -or $key -match '[\\:]' -or @($key.Split('/') | Where-Object { $_ -in @('', '.', '..') }).Count -or $manifest.files[$key] -cnotmatch '^[a-f0-9]{64}$') { throw 'Invalid snapshot path or hash; traversal is forbidden.' }
        }
        $actual.Remove('manifest.json') | Out-Null
        if (-not $manifest.files.Contains('database.dump') -or -not (Test-EqualMap $manifest.files $actual)) { throw 'Snapshot hash mismatch.' }
        if (-not (Test-Path -LiteralPath (Join-Path $snapshotRoot 'instance') -PathType Container)) { throw 'Snapshot storage directory missing.' }
        Assert-EmptyDatabase
        if (@($storageBefore.Keys | Where-Object { $_ -cne 'storage/' }).Count) { throw 'Restore requires empty application storage (only an empty storage directory is allowed).' }
        New-PrivateDirectory $verification
        Invoke-Docker @('cp', (Join-Path $snapshotRoot 'database.dump'), "${DatabaseContainer}:$remoteDump") | Out-Null
        Invoke-Docker @('exec', $DatabaseContainer, 'pg_restore', '--no-owner', '--no-acl', '--exit-on-error', '--file', $remoteSql, $remoteDump) | Out-Null
        Invoke-Storage "from pathlib import Path; Path('/app/instance/$marker').write_text('Restore incomplete. Keep writers stopped. Verify database outcome before recovery. Operation $operation')" -Writable | Out-Null
        $restoreTouched = $true
        Invoke-Sql "\i $remoteSql" | Out-Null
        Invoke-Sql "SET LOCAL idle_in_transaction_session_timeout='60s'; SET LOCAL statement_timeout='120s'; SET LOCAL timezone='UTC'; SET LOCAL extra_float_digits=3;" | Out-Null
        Assert-SchemaRevision
        if (-not (Test-EqualMap $manifest.database_fingerprint (Get-DatabaseFingerprint))) { throw 'Restored database invariant mismatch; transaction will roll back.' }
        Invoke-Docker @('cp', ((Join-Path $snapshotRoot 'instance') + '/.'), "${ApplicationContainer}:/app/instance") | Out-Null
        Invoke-Storage "import os; root='/app/instance'; os.chown(root,1000,1000); os.chmod(root,0o700); [(os.chown(os.path.join(parent,name),1000,1000),os.chmod(os.path.join(parent,name),0o700 if os.path.isdir(os.path.join(parent,name)) else 0o600)) for parent,dirs,files in os.walk(root) for name in dirs+files]" -Writable | Out-Null
        Get-StorageInventory | Out-Null
        Invoke-Docker @('cp', "${ApplicationContainer}:/app/instance/.", $verification) | Out-Null
        $restoredFiles = Get-FileManifest $verification
        $restoredFiles.Remove($marker) | Out-Null
        if (-not (Test-EqualMap (Get-FileManifest (Join-Path $snapshotRoot 'instance')) $restoredFiles)) { throw 'Restored storage mismatch; transaction will roll back.' }
        Assert-Quiescent
        $commitAttempted = $true
        Invoke-Sql 'COMMIT;' | Out-Null
        Invoke-Storage "from pathlib import Path; Path('/app/instance/$marker').unlink()" -Writable | Out-Null
        Write-Output 'RESTORE VERIFIED: compatible schema, database transaction committed only after storage verification; all table/sequence fingerprints and file SHA-256 match.'
    }
} catch {
    $failure = $_
    if ($restoreTouched -and -not $commitAttempted) {
        try {
            Invoke-Sql 'ROLLBACK;' | Out-Null
            Assert-EmptyDatabase
            Assert-Quiescent
            $keepStorage = if ($storageBefore.Contains('storage/')) { 'True' } else { 'False' }
            Invoke-Storage "import os,pathlib,shutil; root=pathlib.Path('/app/instance'); [(shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()) for path in root.iterdir() if path.name!='$marker']; ((root/'storage').mkdir(mode=0o700),os.chown(root/'storage',1000,1000)) if $keepStorage else None; (root/'$marker').unlink()" -Writable | Out-Null
            Write-Output 'ROLLBACK VERIFIED: database empty; copied files removed.'
        } catch { Write-Warning 'Rollback could not be verified. Incomplete marker retained: keep application stopped; recover or replace destination.' }
    } elseif ($commitAttempted) { Write-Warning 'Commit was attempted. Do not erase storage: reconcile database outcome and incomplete marker before starting application.' }
    throw $failure
} finally {
    if ($session) {
        try { $session.StandardInput.Close(); if (-not $session.WaitForExit(5000)) { $session.Kill() } } catch { Write-Warning 'SQL session cleanup requires inspection.' }
        $session.Dispose()
    }
    if ($databaseValidated) {
        try { Invoke-Docker @('exec', $DatabaseContainer, 'rm', '-f', '--', $remoteDump, $remoteSql) | Out-Null } catch { Write-Warning 'Remote temporary snapshot cleanup failed.' }
    }
    foreach ($temporary in @($staging, $verification)) {
        if (Test-Path -LiteralPath $temporary) {
            Assert-NoLinks $temporary
            if ([IO.Path]::GetFullPath($temporary) -notin @("$snapshotRoot.partial-$operation", "$snapshotRoot.verify-$operation")) { throw 'Unsafe temporary cleanup path.' }
            Remove-Item -LiteralPath $temporary -Recurse -Force
        }
    }
}
