param([string]$Project = "oceanblue-s06-final", [string]$EvidenceDirectory = "docs/evidencias/producao/sprint-06-execucao/final")
$ErrorActionPreference = "Stop"
$workspace = Split-Path $PSScriptRoot -Parent
Set-Location $workspace
if ($Project -notmatch '^oceanblue-s06-[a-z0-9-]+$') { throw "Exclusive Sprint 6 project required." }
$evidence = [IO.Path]::GetFullPath((Join-Path $workspace $EvidenceDirectory))
if (Test-Path -LiteralPath $evidence) { throw "New evidence directory required." }
New-Item -ItemType Directory -Path $evidence | Out-Null
& node scripts/validate_workflow.cjs *> (Join-Path $evidence "workflow.json")
if ($LASTEXITCODE -ne 0) { throw "Workflow validation failed; install locked Node development dependencies with npm ci --ignore-scripts." }
$compose = @("compose", "-p", $Project, "-f", "compose.test.yml")
function Invoke-RecordedDocker {
    param([string]$Log, [string[]]$Arguments)
    & docker @Arguments 2>&1 | Out-File -Encoding utf8 (Join-Path $evidence $Log)
    if ($LASTEXITCODE -ne 0) { throw "Docker failed: $Log" }
}
$existing = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
if ($LASTEXITCODE -ne 0 -or $existing) { throw "Project must be empty." }
try {
    Invoke-RecordedDocker "build.txt" ($compose + @("build", "test", "smoke"))
    Invoke-RecordedDocker "dependencies.txt" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-smoke", "-m", "pip", "check")
    Invoke-RecordedDocker "user.txt" @("run", "--rm", "--network", "none", "--entrypoint", "id", "$Project-smoke", "-u")
    if ((Get-Content (Join-Path $evidence "user.txt")).Trim() -eq "0") { throw "Root image refused." }
    try {
        Invoke-RecordedDocker "pipeline.txt" ($compose + @("up", "--no-build", "--pull", "never", "--abort-on-container-exit", "--exit-code-from", "test"))
    } finally {
        & docker @compose cp test:/tmp/junit.xml (Join-Path $evidence "junit.xml") 2>&1 | Out-File (Join-Path $evidence "copy-junit.txt")
        & docker @compose cp test:/app/coverage.xml (Join-Path $evidence "coverage.xml") 2>&1 | Out-File (Join-Path $evidence "copy-coverage.txt")
        & docker @compose cp test:/tmp/e2e (Join-Path $evidence "e2e") 2>&1 | Out-File (Join-Path $evidence "copy-e2e.txt")
        & docker @compose cp test:/tmp/benchmark-s06.json (Join-Path $evidence "benchmark.json") 2>&1 | Out-File (Join-Path $evidence "copy-benchmark.txt")
        & docker @compose cp test:/tmp/load-s06.json (Join-Path $evidence "load.json") 2>&1 | Out-File (Join-Path $evidence "copy-load.txt")
    }
    [xml]$junit = Get-Content -Raw (Join-Path $evidence "junit.xml")
    foreach ($suite in $junit.testsuites.testsuite) {
        if ([int]$suite.failures -or [int]$suite.errors -or [int]$suite.skipped) { throw "JUnit gate failed." }
    }
    foreach ($target in @("test", "smoke")) {
        Invoke-RecordedDocker "source-$target.json" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-$target", "-m", "scripts.source_manifest")
        $manifest = Get-Content -Raw (Join-Path $evidence "source-$target.json") | ConvertFrom-Json -AsHashtable
        foreach ($entry in $manifest.GetEnumerator()) {
            if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $workspace $entry.Key)).Hash.ToLower() -ne $entry.Value) { throw "Source mismatch: $($entry.Key)" }
        }
        "Verified $($manifest.Count) files." | Set-Content (Join-Path $evidence "source-$target-check.txt")
    }
    Invoke-RecordedDocker "smoke-start.txt" ($compose + @("--profile", "smoke", "up", "--no-build", "--pull", "never", "-d", "--wait", "--wait-timeout", "120", "smoke"))
    Invoke-RecordedDocker "smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_smoke"))
    Invoke-RecordedDocker "security-smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke"))
    Invoke-RecordedDocker "storage-outage.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_storage_outage"))
    Invoke-RecordedDocker "database-stop.txt" ($compose + @("stop", "db-test"))
    Invoke-RecordedDocker "database-outage.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke", "--database-down"))
    Invoke-RecordedDocker "network.json" @("network", "inspect", "$($Project)_test")
    Invoke-RecordedDocker "images.txt" @("image", "inspect", "$Project-test", "$Project-smoke", "--format", "{{.Id}}")
    Invoke-RecordedDocker "logs.txt" ($compose + @("logs", "--no-color", "smoke"))
} finally {
    Invoke-RecordedDocker "cleanup.txt" ($compose + @("--profile", "smoke", "down", "-v"))
    $remaining = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
    if ($LASTEXITCODE -ne 0 -or $remaining) { throw "Project containers remain." }
    "Zero project containers." | Set-Content (Join-Path $evidence "cleanup-check.txt")
}
