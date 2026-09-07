param(
    [Parameter(Mandatory)][ValidateSet("backup", "restore")][string]$Mode,
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$DatabaseContainer,
    [Parameter(Mandatory)][string]$ApplicationContainer,
    [Parameter(Mandatory)][string]$Database,
    [Parameter(Mandatory)][string]$DatabaseUser,
    [Parameter(Mandatory)][string]$Directory
)

$ErrorActionPreference = "Stop"
if ($Project -notmatch '^[a-z][a-z0-9-]+$' -or $Database -notmatch '^[a-z][a-z0-9_]+$' -or $DatabaseUser -notmatch '^[a-z][a-z0-9_]+$') {
    throw "Invalid project/database identifier."
}
function Invoke-Docker {
    param([string[]]$Arguments)
    $result = & docker @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Docker operation failed; inspect the isolated container. No credentials printed." }
    return $result
}
function Invoke-Sql {
    param([string]$Sql)
    return Invoke-Docker @("exec", $DatabaseContainer, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", $DatabaseUser, "-d", $Database, "-At", "-c", $Sql)
}
foreach ($container in @($DatabaseContainer, $ApplicationContainer)) {
    $metadata = (Invoke-Docker @("inspect", $container) | Out-String | ConvertFrom-Json)[0]
    if ($metadata.Config.Labels.'com.docker.compose.project' -ne $Project) { throw "Container outside selected project." }
    if ($container -eq $ApplicationContainer -and $metadata.State.Running) { throw "Stop application and all writers before taking or restoring a snapshot." }
    if ($container -eq $ApplicationContainer -and -not ($metadata.Mounts | Where-Object Destination -eq '/app/instance')) { throw "Application storage must be a persistent mount." }
}
if ([int](Invoke-Sql "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid <> pg_backend_pid() AND backend_type='client backend'") -ne 0) {
    throw "Other database clients remain. Stop all writers."
}
$snapshotRoot = [IO.Path]::GetFullPath($Directory)
function Get-FileManifest {
    param([string]$Root)
    $result = [ordered]@{}
    foreach ($entry in Get-ChildItem -LiteralPath $Root -Recurse -Force | Sort-Object FullName) {
        if ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Links are forbidden in snapshots." }
        if (-not $entry.PSIsContainer) {
            $relative = [IO.Path]::GetRelativePath($Root, $entry.FullName).Replace('\', '/')
            $result[$relative] = (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash.ToLower()
        }
    }
    return $result
}
function Get-DatabaseFingerprint {
    $tables = Invoke-Sql "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    $result = [ordered]@{}
    foreach ($table in $tables) {
        if ($table -notmatch '^[a-z][a-z0-9_]+$') { throw "Unexpected table identifier." }
        $result[$table] = Invoke-Sql "SELECT count(*) || ':' || md5(coalesce(string_agg(md5(row_to_json(records)::text), '' ORDER BY md5(row_to_json(records)::text)), '')) FROM public.$table records"
    }
    $sequences = Invoke-Sql "SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"
    foreach ($sequence in $sequences) {
        if ($sequence -notmatch '^[a-z][a-z0-9_]+$') { throw "Unexpected sequence identifier." }
        $result["sequence:$sequence"] = Invoke-Sql "SELECT last_value || ':' || is_called FROM public.$sequence"
    }
    return $result
}
$remoteDump = "/tmp/oceanblue-snapshot-$([guid]::NewGuid().ToString('N')).dump"
try {
    if ($Mode -eq "backup") {
        if (Test-Path -LiteralPath $snapshotRoot) { throw "Use a new snapshot directory; never overwrite a backup." }
        New-Item -ItemType Directory -Path $snapshotRoot | Out-Null
        if ($IsWindows) {
            $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            & icacls $snapshotRoot /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "Could not restrict backup ACL." }
        } else {
            & chmod 700 $snapshotRoot
            if ($LASTEXITCODE -ne 0) { throw "Could not restrict backup permissions." }
        }
        $before = Get-DatabaseFingerprint | ConvertTo-Json -Depth 5 -Compress
        Invoke-Docker @("exec", $DatabaseContainer, "pg_dump", "-U", $DatabaseUser, "-d", $Database, "--format=custom", "--no-owner", "--no-acl", "--file", $remoteDump) | Out-Null
        Invoke-Docker @("cp", "${DatabaseContainer}:$remoteDump", (Join-Path $snapshotRoot "database.dump")) | Out-Null
        Invoke-Docker @("cp", "${ApplicationContainer}:/app/instance", (Join-Path $snapshotRoot "instance")) | Out-Null
        $after = Get-DatabaseFingerprint | ConvertTo-Json -Depth 5 -Compress
        if ($before -ne $after) { throw "Database changed during backup; snapshot is not accepted." }
        $manifest = @{version=1; database=$Database; database_fingerprint=($after | ConvertFrom-Json -AsHashtable);
            files=(Get-FileManifest $snapshotRoot); created_utc=[DateTime]::UtcNow.ToString("o")}
        $manifest | ConvertTo-Json -Depth 8 | Set-Content -Encoding utf8 (Join-Path $snapshotRoot "manifest.json")
        Write-Output "BACKUP VERIFIED: tables, sequences and file SHA-256; application stopped."
    } else {
        if (-not (Test-Path -LiteralPath (Join-Path $snapshotRoot "manifest.json"))) { throw "Snapshot manifest missing." }
        $manifest = Get-Content -Raw (Join-Path $snapshotRoot "manifest.json") | ConvertFrom-Json -AsHashtable
        $actual = Get-FileManifest $snapshotRoot
        $actual.Remove("manifest.json") | Out-Null
        if ($actual.Count -ne $manifest.files.Count) { throw "Snapshot file count mismatch." }
        foreach ($key in $manifest.files.Keys) {
            if ($actual[$key] -ne $manifest.files[$key]) { throw "Snapshot hash mismatch." }
        }
        if ([int](Invoke-Sql "SELECT count(*) FROM pg_tables WHERE schemaname='public'") -ne 0) { throw "Restore requires a new empty database." }
        if ((Test-Path -LiteralPath "${snapshotRoot}-destination-check") -or (Test-Path -LiteralPath "${snapshotRoot}-restored-check")) { throw "Restore verification paths already exist." }
        foreach ($privateDirectory in @("${snapshotRoot}-destination-check", "${snapshotRoot}-restored-check")) {
            New-Item -ItemType Directory -Path $privateDirectory | Out-Null
            if ($IsWindows) {
                $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
                & icacls $privateDirectory /inheritance:r /grant:r "${identity}:(OI)(CI)F" | Out-Null
            } else {
                & chmod 700 $privateDirectory
            }
            if ($LASTEXITCODE -ne 0) { throw "Could not protect restore verification directory." }
        }
        Invoke-Docker @("cp", "${ApplicationContainer}:/app/instance/.", "${snapshotRoot}-destination-check") | Out-Null
        $destinationFiles = Get-FileManifest "${snapshotRoot}-destination-check"
        if ($destinationFiles.Count) { throw "Restore requires empty application storage." }
        Invoke-Docker @("cp", (Join-Path $snapshotRoot "database.dump"), "${DatabaseContainer}:$remoteDump") | Out-Null
        Invoke-Docker @("exec", $DatabaseContainer, "pg_restore", "-U", $DatabaseUser, "-d", $Database, "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction", $remoteDump) | Out-Null
        $restored = Get-DatabaseFingerprint
        if (($restored | ConvertTo-Json -Depth 5 -Compress) -ne ($manifest.database_fingerprint | ConvertTo-Json -Depth 5 -Compress)) { throw "Restored database invariant mismatch; do not start application." }
        Invoke-Docker @("cp", ((Join-Path $snapshotRoot "instance") + "/."), "${ApplicationContainer}:/app/instance") | Out-Null
        $appMetadata = (Invoke-Docker @("inspect", $ApplicationContainer) | Out-String | ConvertFrom-Json)[0]
        if (-not ($appMetadata.Mounts | Where-Object Destination -eq '/app/instance')) { throw "Application storage must be a persistent mount." }
        Invoke-Docker @("run", "--rm", "--network", "none", "--user", "0", "--volumes-from", $ApplicationContainer,
            "--entrypoint", "sh", $appMetadata.Image, "-c", "chown -R 1000:1000 /app/instance && chmod 700 /app/instance /app/instance/storage") | Out-Null
        Invoke-Docker @("cp", "${ApplicationContainer}:/app/instance/.", "${snapshotRoot}-restored-check") | Out-Null
        $restoredFiles = Get-FileManifest "${snapshotRoot}-restored-check"
        $expectedFiles = Get-FileManifest (Join-Path $snapshotRoot "instance")
        if (($restoredFiles | ConvertTo-Json -Compress) -ne ($expectedFiles | ConvertTo-Json -Compress)) { throw "Restored storage mismatch; do not start application." }
        Write-Output "RESTORE VERIFIED: new database, all table counts/content hashes, sequences and every file SHA-256 match."
    }
} finally {
    Invoke-Docker @("exec", $DatabaseContainer, "rm", "-f", "--", $remoteDump) | Out-Null
}
