param([string]$Project = "oceanblue-s06-proof", [string]$ImagePrefix = "oceanblue-s06-final", [string]$EvidenceDirectory = "docs/evidencias/producao/sprint-06-execucao/operational")
$ErrorActionPreference = "Stop"
$workspace = Split-Path $PSScriptRoot -Parent
Set-Location $workspace
if ($Project -notmatch '^oceanblue-s06-[a-z0-9-]+$') { throw "Exclusive Sprint 6 project required." }
$evidence = [IO.Path]::GetFullPath((Join-Path $workspace $EvidenceDirectory))
if (Test-Path -LiteralPath $evidence) { throw "New evidence directory required." }
New-Item -ItemType Directory -Path $evidence | Out-Null
$restoreProject = "$Project-restore"
$source = @("compose", "-p", $Project, "-f", "compose.test.yml", "-f", "compose.operational-test.yml")
$destination = @("compose", "-p", $restoreProject, "-f", "compose.test.yml")
function Invoke-RecordedDocker {
    param([string]$Log, [string[]]$Arguments)
    & docker @Arguments 2>&1 | Out-File -Encoding utf8 (Join-Path $evidence $Log)
    if ($LASTEXITCODE -ne 0) { throw "Docker failed: $Log" }
}
foreach ($name in @($Project, $restoreProject)) {
    $existing = & docker ps -aq --filter "label=com.docker.compose.project=$name"
    if ($LASTEXITCODE -ne 0 -or $existing) { throw "Project must be empty." }
}
try {
    foreach ($name in @($Project, $restoreProject)) {
        Invoke-RecordedDocker "tag-$name.txt" @("tag", "$ImagePrefix-smoke", "$name-smoke")
    }
    Invoke-RecordedDocker "source-database.txt" ($source + @("up", "-d", "--wait", "db-test"))
    Invoke-RecordedDocker "source-create.txt" ($source + @("--profile", "smoke", "create", "--no-build", "smoke", "proxy"))
    Invoke-RecordedDocker "tls.txt" @("run", "--rm", "--network", "none", "--user", "0", "--mount", "type=volume,source=$($Project)_proof-tls,target=/tls",
        "--entrypoint", "sh", "$ImagePrefix-test", "-c", "openssl req -x509 -newkey rsa:2048 -nodes -keyout /tls/privkey.pem -out /tls/fullchain.pem -days 2 -subj /CN=proxy -addext subjectAltName=DNS:proxy && chown 101:101 /tls/* && chmod 600 /tls/privkey.pem")
    Invoke-RecordedDocker "seed.txt" @("run", "--rm", "--network", "$($Project)_test", "--volumes-from", "$Project-smoke-1",
        "-e", "TEST_DATABASE_URL=postgresql+psycopg2://oceanblue_test:isolated-test-only@db-test:5432/oceanblue_test", "$ImagePrefix-test", "python", "-m", "scripts.seed_operational_proof")
    Invoke-RecordedDocker "source-start.txt" ($source + @("--profile", "smoke", "up", "-d", "--no-build", "--wait", "--wait-timeout", "120", "smoke", "proxy"))
    Invoke-RecordedDocker "https.txt" @("run", "--rm", "--network", "$($Project)_test", "--mount", "type=volume,source=$($Project)_proof-tls,target=/proof-tls,readonly", "$ImagePrefix-test", "python", "-m", "scripts.validate_https_proof")
    Invoke-RecordedDocker "read-only.txt" ($source + @("exec", "-T", "smoke", "python", "-c", "import os; assert os.geteuid() == 1000; assert not os.access('/app/wsgi.py', os.W_OK); print('NONROOT READONLY SOURCE VERIFIED')"))
    & pwsh -NoProfile -File scripts/operational_snapshot.ps1 -Mode backup -Project $Project -DatabaseContainer "$Project-db-test-1" -ApplicationContainer "$Project-smoke-1" -Database oceanblue_test -DatabaseUser oceanblue_test -Directory (Join-Path $evidence "live-forbidden") *> (Join-Path $evidence "backup-live-refused.txt")
    if ($LASTEXITCODE -eq 0 -or (Test-Path (Join-Path $evidence "live-forbidden"))) { throw "Live backup was not safely refused." }
    Invoke-RecordedDocker "stop-writers.txt" ($source + @("stop", "smoke", "proxy"))
    & pwsh -NoProfile -File scripts/operational_snapshot.ps1 -Mode backup -Project $Project -DatabaseContainer "$Project-db-test-1" -ApplicationContainer "$Project-smoke-1" -Database oceanblue_test -DatabaseUser oceanblue_test -Directory (Join-Path $evidence "snapshot") *> (Join-Path $evidence "backup.txt")
    if ($LASTEXITCODE -ne 0) { throw "Backup failed." }
    Invoke-RecordedDocker "restore-database.txt" ($destination + @("up", "-d", "--wait", "db-test"))
    Invoke-RecordedDocker "restore-create.txt" ($destination + @("--profile", "smoke", "create", "--no-build", "smoke"))
    Copy-Item -LiteralPath (Join-Path $evidence "snapshot") -Destination (Join-Path $evidence "tampered") -Recurse
    [IO.File]::AppendAllText((Join-Path $evidence "tampered/database.dump"), "synthetic-corruption")
    & pwsh -NoProfile -File scripts/operational_snapshot.ps1 -Mode restore -Project $restoreProject -DatabaseContainer "$restoreProject-db-test-1" -ApplicationContainer "$restoreProject-smoke-1" -Database oceanblue_test -DatabaseUser oceanblue_test -Directory (Join-Path $evidence "tampered") *> (Join-Path $evidence "tampered-refused.txt")
    if ($LASTEXITCODE -eq 0 -or -not (Get-Content -Raw (Join-Path $evidence "tampered-refused.txt")).Contains("Snapshot hash mismatch")) { throw "Corrupt snapshot was not refused." }
    & pwsh -NoProfile -File scripts/operational_snapshot.ps1 -Mode restore -Project $restoreProject -DatabaseContainer "$restoreProject-db-test-1" -ApplicationContainer "$restoreProject-smoke-1" -Database oceanblue_test -DatabaseUser oceanblue_test -Directory (Join-Path $evidence "snapshot") *> (Join-Path $evidence "restore.txt")
    if ($LASTEXITCODE -ne 0) { throw "Restore failed." }
    Invoke-RecordedDocker "restore-start.txt" ($destination + @("--profile", "smoke", "up", "-d", "--no-build", "--wait", "--wait-timeout", "120", "smoke"))
    Invoke-RecordedDocker "restore-smoke.txt" ($destination + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_smoke"))
    Invoke-RecordedDocker "restore-storage.txt" ($destination + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_storage_outage"))
    Invoke-RecordedDocker "restore-stop.txt" ($destination + @("stop", "smoke"))
    & pwsh -NoProfile -File scripts/operational_snapshot.ps1 -Mode restore -Project $restoreProject -DatabaseContainer "$restoreProject-db-test-1" -ApplicationContainer "$restoreProject-smoke-1" -Database oceanblue_test -DatabaseUser oceanblue_test -Directory (Join-Path $evidence "snapshot") *> (Join-Path $evidence "nonempty-refused.txt")
    if ($LASTEXITCODE -eq 0 -or -not (Get-Content -Raw (Join-Path $evidence "nonempty-refused.txt")).Contains("new empty database")) { throw "Nonempty restore was not refused." }
    Invoke-RecordedDocker "rollback-start.txt" @("run", "-d", "--rm", "--name", "$restoreProject-rollback", "--label", "com.docker.compose.project=$restoreProject", "--label", "com.docker.compose.service=rollback",
        "--network", "$($restoreProject)_test", "--volumes-from", "$restoreProject-smoke-1", "-e", "DATABASE_URL=postgresql+psycopg2://oceanblue_test:isolated-test-only@db-test:5432/oceanblue_test",
        "-e", "SECRET_KEY=isolated-smoke-session-secret-32-characters", "-e", "JWT_SECRET_KEY=isolated-smoke-jwt-secret-32-characters", "-e", "FIELD_ENCRYPTION_KEY=isolated-smoke-field-secret-32-characters",
        "--entrypoint", "gunicorn", "sha256:896e64670d1cf36bd15ae5b97784fed1ff564de6b98cbeaadaca9d8fa74529b1", "-w", "1", "-b", "0.0.0.0:5000", "--forwarded-allow-ips", "", "wsgi:app")
    Invoke-RecordedDocker "rollback-smoke.txt" @("exec", "$restoreProject-rollback", "python", "-c", "import time; time.sleep(2); from scripts.validate_smoke import main; main(); from app import create_app; from app.models.db import Venda, LancamentoFinanceiro; app=create_app(); context=app.app_context(); context.push(); assert Venda.query.count()==3; assert LancamentoFinanceiro.query.count()==3; print('PREVIOUS APPLICATION RUNS ON RESTORED SCHEMA; THREE SALES AND LEDGER ENTRIES PRESERVED')")
    Invoke-RecordedDocker "rollback-stop.txt" @("stop", "$restoreProject-rollback")
    Invoke-RecordedDocker "migration-downgrade.txt" @("run", "--rm", "--network", "$($restoreProject)_test", "-e", "TEST_DATABASE_URL=postgresql+psycopg2://oceanblue_test:isolated-test-only@db-test:5432/oceanblue_test", "$ImagePrefix-test", "python", "-c", "from scripts.test_environment import configure_test_environment; configure_test_environment(); from app import create_app; from flask_migrate import downgrade, upgrade; from app.extensions import db; from sqlalchemy import text; app=create_app(); context=app.app_context(); context.push(); expected=db.session.execute(text('SELECT count(*), sum(total) FROM vendas')).one(); db.session.remove(); downgrade(revision='9c0d1e2f3a4b'); upgrade(); assert db.session.execute(text('SELECT count(*), sum(total) FROM vendas')).one()==expected; print('MIGRATION DOWNGRADE REUPGRADE WITH THREE SALES VERIFIED; NO REQUEST TRACE DATA PRESENT')")
    Invoke-RecordedDocker "network.json" @("network", "inspect", "$($Project)_test", "$($restoreProject)_test")
    Invoke-RecordedDocker "proof-logs.txt" ($source + @("--profile", "smoke", "logs", "--no-color", "smoke", "proxy"))
} finally {
    & docker @source --profile smoke logs --no-color smoke proxy 2>&1 | Out-File (Join-Path $evidence "final-source-logs.txt")
    Invoke-RecordedDocker "cleanup-source.txt" ($source + @("--profile", "smoke", "down", "-v", "--remove-orphans"))
    Invoke-RecordedDocker "cleanup-restore.txt" ($destination + @("--profile", "smoke", "down", "-v", "--remove-orphans"))
    foreach ($name in @($Project, $restoreProject)) {
        foreach ($kind in @("container", "network", "volume")) {
            $remaining = & docker $kind ls -q --filter "label=com.docker.compose.project=$name"
            if ($kind -eq "container") { $remaining = & docker ps -aq --filter "label=com.docker.compose.project=$name" }
            if ($LASTEXITCODE -ne 0 -or $remaining) { throw "Project resources remain: $name $kind" }
        }
    }
    "Zero containers, networks and volumes for both proof projects." | Set-Content (Join-Path $evidence "cleanup-check.txt")
}
