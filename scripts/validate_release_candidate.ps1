param(
    [ValidatePattern('^oceanblue-s07-[a-z0-9-]+$')][string]$Project = 'oceanblue-s07-final',
    [string]$EvidenceDirectory = 'docs/evidencias/producao/sprint-07-execucao',
    [string]$Python = 'python',
    [ValidateSet('all', 'regression', 'retest', 'operations', 'assemble')][string]$Phase = 'all'
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
Set-Location $workspace
$baseline = '7b0c97f87ec8cf1a9584c389717383c457bc764f'
$raw = Join-Path $workspace ".release-work/$Project"
$evidence = [IO.Path]::GetFullPath((Join-Path $workspace $EvidenceDirectory))
if (-not $evidence.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar)) { throw 'Evidence must stay in workspace.' }
if ($Phase -eq 'all' -and (Test-Path $raw)) { throw 'Use a new project for a complete run.' }
New-Item -ItemType Directory -Force -Path $raw, $evidence | Out-Null
& git merge-base --is-ancestor $baseline HEAD
if ($LASTEXITCODE) { throw 'Sprint 6 base is not an ancestor.' }
$decision = Get-Content -Raw docs/evidencias/producao/sprint-06-validacao.md
if ($decision -notmatch '\*\*GO para homologação local da Sprint 6 corrigida') { throw 'Sprint 6 GO missing.' }
$run = Invoke-RestMethod -Uri 'https://api.github.com/repos/NataRabelo/OceanBlue/actions/runs/34102472661' -Headers @{Accept='application/vnd.github+json'; 'User-Agent'='OceanBlue-release-verifier'}
if ($run.head_sha -ne $baseline -or $run.status -ne 'completed' -or $run.conclusion -ne 'success') { throw 'Remote Sprint 6 gate failed.' }
$run | Select-Object id, head_sha, status, conclusion, html_url, updated_at | ConvertTo-Json | Set-Content (Join-Path $evidence 'sprint06-remote-gate.json')

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments, [string]$Log)
    & $Program @Arguments 2>&1 | Out-File -Encoding utf8 $Log
    if ($LASTEXITCODE) { throw "Command failed: $Log" }
}

function Invoke-ReleasePython {
    param([string[]]$Arguments)
    & docker run --rm --network none --mount "type=bind,source=$workspace,target=/workspace" --workdir /workspace --entrypoint python "$Project-regression-smoke" -m scripts.release_candidate @Arguments
    if ($LASTEXITCODE) { throw 'Release integrity gate failed.' }
}

if ($Phase -eq 'all') {
    Invoke-Checked $Python @('scripts/release_supply_chain.py', '--root', $workspace, '--output-dir', (Join-Path $evidence 'supply-chain')) (Join-Path $raw 'supply-chain-scan.txt')
}

foreach ($round in @('regression', 'retest')) {
    if ($Phase -notin @('all', $round)) { continue }
    $npmProgram = if ($IsWindows) { 'npm.cmd' } else { 'npm' }
    Invoke-Checked $npmProgram @('ci', '--ignore-scripts') (Join-Path $raw "npm-$round.txt")
    Invoke-Checked 'node' @('scripts/validate_release_config.cjs') (Join-Path $evidence 'production-config.json')
    Invoke-Checked 'pwsh' @('-NoProfile', '-File', 'scripts/validate_sprint06.ps1', '-Project', "$Project-$round", '-EvidenceDirectory', ".release-work/$Project/$round") (Join-Path $raw "$round-runner.txt")
    Invoke-ReleasePython @('curate', '--raw', ".release-work/$Project/$round", '--evidence', "$EvidenceDirectory/$round")
}

if ($Phase -in @('all', 'operations')) {
    Invoke-Checked 'docker' @('run', '--rm', '--network', 'none', '--entrypoint', 'dpkg-query', "$Project-regression-smoke", '-W') (Join-Path $evidence 'image-os-packages.txt')
    Invoke-Checked 'docker' @('run', '--rm', '--network', 'none', '--entrypoint', 'python', "$Project-regression-smoke", '--version') (Join-Path $evidence 'image-python-version.txt')
    $previous = Join-Path $raw 'previous'
    if (Test-Path $previous) { throw 'Previous build directory exists.' }
    New-Item -ItemType Directory -Path $previous | Out-Null
    Invoke-Checked 'git' @('archive', '--format=tar', '-o', (Join-Path $raw 'previous.tar'), $baseline, 'Dockerfile', '.dockerignore', 'app', 'scripts', 'migrations', 'requirements.txt', 'docker-entrypoint.sh', 'wsgi.py') (Join-Path $raw 'previous-archive.txt')
    Invoke-Checked 'tar' @('-xf', (Join-Path $raw 'previous.tar'), '-C', $previous) (Join-Path $raw 'previous-extract.txt')
    Invoke-Checked 'docker' @('build', '-t', "$Project-previous", $previous) (Join-Path $raw 'previous-build.txt')
    $rollbackImage = (& docker image inspect "$Project-previous" --format '{{.Id}}').Trim()
    if ($LASTEXITCODE) { throw 'Previous image missing.' }
    @{base_commit=$baseline; image_id=$rollbackImage; source='git archive of runtime paths, rebuilt from pinned Sprint 6 source; historical evidence and test traces omitted'} | ConvertTo-Json | Set-Content (Join-Path $evidence 'rollback-image.json')
    Invoke-Checked 'pwsh' @('-NoProfile', '-File', 'scripts/validate_operational_proof.ps1', '-Project', "$Project-ops", '-ImagePrefix', "$Project-regression", '-RollbackImage', $rollbackImage, '-EnableHttpLoad', '-EvidenceDirectory', ".release-work/$Project/operations") (Join-Path $raw 'operations-runner.txt')
    Invoke-ReleasePython @('curate', '--raw', ".release-work/$Project/operations", '--evidence', "$EvidenceDirectory/operations")
    $suffix = $Project.Substring('oceanblue-s07-'.Length)
    Invoke-Checked 'pwsh' @('-NoProfile', '-File', 'scripts/validate_snapshot_adversarial.ps1', '-Project', "oceanblue-s07-snapshot-$suffix", '-Image', "$Project-regression-smoke", '-EvidenceDirectory', ".release-work/$Project/snapshot") (Join-Path $raw 'snapshot-runner.txt')
    Invoke-ReleasePython @('curate', '--raw', ".release-work/$Project/snapshot/green", '--evidence', "$EvidenceDirectory/snapshot")
    Invoke-Checked 'pwsh' @('-NoProfile', '-File', 'scripts/validate_proxy_logs.ps1', '-Project', "oceanblue-s07-proxy-log-$suffix", '-TestImage', "$Project-regression-test", '-EvidenceDirectory', ".release-work/$Project/proxy") (Join-Path $raw 'proxy-runner.txt')
    Invoke-ReleasePython @('curate', '--raw', ".release-work/$Project/proxy", '--evidence', "$EvidenceDirectory/proxy")
    foreach ($rules in @('alerts.test.yml', 'alerts.adversarial.test.yml')) {
        Invoke-Checked 'docker' @('run', '--rm', '--network', 'none', '--mount', "type=bind,source=$workspace/infra/production,target=/rules,readonly", '--workdir', '/rules', '--entrypoint', 'promtool', 'prom/prometheus:v3.5.0@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996', 'test', 'rules', $rules) (Join-Path $evidence $rules.Replace('.yml', '.txt'))
    }
    foreach ($variable in @('DATABASE_URL', 'SECRET_KEY', 'JWT_SECRET_KEY', 'FIELD_ENCRYPTION_KEY')) {
        $output = & docker run --rm --network none -e DATABASE_URL=postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue -e SECRET_KEY=validation-session-secret-32-characters -e JWT_SECRET_KEY=validation-jwt-secret-32-characters -e FIELD_ENCRYPTION_KEY=validation-field-secret-32-characters -e DB_WAIT_TIMEOUT_SECONDS=1 -e "$variable=" "$Project-regression-smoke" true 2>&1
        if ($LASTEXITCODE -eq 0 -or -not ($output | Out-String).Contains("Variaveis obrigatorias ausentes em producao: $variable")) { throw 'Missing-secret startup gate failed.' }
    }
    @{missing_secrets_rejected=4; before_database=$true} | ConvertTo-Json | Set-Content (Join-Path $evidence 'image-startup-gates.json')
}

if ($Phase -in @('all', 'assemble')) {
    Invoke-Checked $Python @('scripts/release_supply_chain.py', '--root', $workspace, '--output-dir', (Join-Path $evidence 'supply-chain'), '--verify-only') (Join-Path $raw 'supply-chain-verification.txt')
    foreach ($required in @('operations/cleanup-check.txt', 'operations/http-load.json', 'snapshot/summary.json', 'proxy/result.json', 'image-startup-gates.json', 'alerts.test.txt', 'alerts.adversarial.test.txt')) {
        if (-not (Test-Path (Join-Path $evidence $required))) { throw "Missing operational evidence: $required" }
    }
    $snapshot = Get-Content -Raw (Join-Path $evidence 'snapshot/summary.json') | ConvertFrom-Json
    $proxy = Get-Content -Raw (Join-Path $evidence 'proxy/result.json') | ConvertFrom-Json
    if ($snapshot.failed -or -not $snapshot.resources_removed -or $proxy.leaked_synthetic_sentinels -or -not $proxy.structured_access_log) { throw 'Operational evidence failed.' }
    Invoke-ReleasePython @('summarize', '--evidence', $EvidenceDirectory)
    Invoke-ReleasePython @('traceability', '--evidence', $EvidenceDirectory)
    $referenceSources = $null
    foreach ($round in @('regression', 'retest')) {
        foreach ($target in @('test', 'smoke')) {
            $sources = Get-Content -Raw (Join-Path $evidence "$round/source-$target.json") | ConvertFrom-Json -AsHashtable
            if (-not $sources.Count) { throw 'Empty tested source manifest.' }
            foreach ($entry in $sources.GetEnumerator()) {
                $path = [IO.Path]::GetFullPath((Join-Path $workspace $entry.Key))
                if (-not $path.StartsWith($workspace + [IO.Path]::DirectorySeparatorChar) -or (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant() -ne $entry.Value) { throw "Tested source changed: $($entry.Key)" }
            }
            $canonical = $sources.Keys | Sort-Object | ForEach-Object { "$_=$($sources[$_])" }
            if ($referenceSources -and (Compare-Object $referenceSources $canonical)) { throw 'Tested source inventories differ.' }
            $referenceSources = $canonical
        }
    }
    & docker image inspect "$Project-regression-smoke" "$Project-regression-test" "$Project-retest-smoke" "$Project-retest-test" --format '{{.Id}}' | Set-Content (Join-Path $evidence 'candidate-image-ids.txt')
    if ($LASTEXITCODE) { throw 'Candidate images missing.' }
    foreach ($kind in @('container', 'network', 'volume')) {
        $remaining = & docker $kind ls -q --filter "label=com.docker.compose.project=$Project-regression"
        if ($kind -eq 'container') { $remaining = & docker ps -aq --filter "label=com.docker.compose.project=$Project-regression" }
        if ($LASTEXITCODE -or $remaining) { throw "Resources remain: $kind" }
    }
    Invoke-ReleasePython @('package', '--evidence', $EvidenceDirectory)
    $manifest = Get-Content -Raw (Join-Path $evidence 'release-manifest.json') | ConvertFrom-Json
    $packaged = Join-Path $raw ("packaged-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $packaged | Out-Null
    Invoke-Checked 'tar' @('-xf', (Join-Path $workspace "dist/$($manifest.package.name)"), '-C', $packaged) (Join-Path $raw 'package-extract.txt')
    Invoke-Checked 'docker' @('build', '-t', "$Project-packaged", $packaged) (Join-Path $raw 'package-build.txt')
    Invoke-Checked 'docker' @('run', '--rm', '--network', 'none', '-e', 'TEST_DATABASE_URL=postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue_test', '--entrypoint', 'python', "$Project-packaged", '-c', 'from pathlib import Path; from scripts.test_environment import configure_test_environment; configure_test_environment(); import wsgi; response=wsgi.app.test_client().get("/api/health"); assert response.status_code==200; assert response.json["version"]==Path("VERSION").read_text().strip(); print("ARCHIVE WSGI STARTUP AND HEALTH VERIFIED WITHOUT DATABASE OR EXTERNAL NETWORK")') (Join-Path $evidence 'package-startup.txt')
    & docker image inspect "$Project-packaged" --format '{{.Id}}' | Set-Content (Join-Path $evidence 'package-image-id.txt')
    if ($LASTEXITCODE) { throw 'Packaged image missing.' }
    Invoke-ReleasePython @('hash', '--evidence', $EvidenceDirectory)
    Invoke-ReleasePython @('verify', '--evidence', $EvidenceDirectory)
}
