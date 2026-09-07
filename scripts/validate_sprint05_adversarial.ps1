param([string]$Project, [string]$EvidenceDirectory)

$ErrorActionPreference = "Stop"
$workspace = Split-Path $PSScriptRoot -Parent
Set-Location $workspace
if ($Project -notmatch '^oceanblue-s05-audit-[a-z0-9-]+$') { throw "Use an exclusive Sprint 5 audit project." }
$evidence = Join-Path $workspace $EvidenceDirectory
New-Item -ItemType Directory -Force $evidence | Out-Null
$compose = @("compose", "-p", $Project, "-f", "compose.test.yml")

function Invoke-RecordedDocker {
    param([string]$Log, [string[]]$Arguments)
    $ErrorActionPreference = "Continue"
    & docker @Arguments 2>&1 | Out-File -Encoding utf8 (Join-Path $evidence $Log)
    if ($LASTEXITCODE -ne 0) { throw "Docker failed ($LASTEXITCODE): $Log" }
}

$existing = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
if ($LASTEXITCODE -ne 0 -or $existing) { throw "Project must be empty." }
try {
    $bases = @{
        "oceanblue-s05-accept-test" = "sha256:911e78aca5b6e2fe786fe5afa31c75323e3295aa74c0cdeccfe5f2de684ce2b6"
        "oceanblue-s05-accept-smoke" = "sha256:b2d581913deed102e29c0843665662e6d3ce1fe92319b89b70212360baf4c52f"
    }
    foreach ($base in $bases.GetEnumerator()) {
        $identity = & docker image inspect $base.Key --format "{{.Id}}"
        if ($LASTEXITCODE -ne 0 -or $identity -ne $base.Value) { throw "Frozen dependency image mismatch." }
        Invoke-RecordedDocker "$($base.Key)-source.json" @("run", "--rm", "--network", "none", "--entrypoint", "python", $base.Key, "-m", "scripts.source_manifest")
        $manifest = Get-Content -Raw (Join-Path $evidence "$($base.Key)-source.json") | ConvertFrom-Json -AsHashtable
        foreach ($name in @("requirements.txt", "requirements-dev.txt", "Dockerfile", "Dockerfile.test")) {
            if ((Get-FileHash -Algorithm SHA256 -LiteralPath $name).Hash.ToLower() -ne $manifest[$name]) { throw "Frozen dependency recipe changed: $name" }
        }
        "$($base.Key) $identity; dependency locks and canonical Dockerfiles unchanged." | Add-Content (Join-Path $evidence "frozen-dependencies.txt")
    }
    Invoke-RecordedDocker "build-test.txt" @("build", "--network", "none", "--pull=false", "-f", "Dockerfile.validation", "--target", "test", "-t", "$Project-test", ".")
    Invoke-RecordedDocker "build-production.txt" @("build", "--network", "none", "--pull=false", "-f", "Dockerfile.validation", "--target", "production", "-t", "$Project-smoke", ".")
    Invoke-RecordedDocker "image-user.txt" @("run", "--rm", "--network", "none", "--entrypoint", "id", "$Project-smoke", "-u")
    if ((Get-Content (Join-Path $evidence "image-user.txt")).Trim() -eq "0") { throw "Production user is root." }
    Invoke-RecordedDocker "image-dependencies.txt" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-smoke", "-m", "pip", "check")
    Invoke-RecordedDocker "image-default.txt" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-smoke", "-c", "from app.config import get_config, ProductionConfig; assert get_config() is ProductionConfig; print('DEFAULT PRODUCTION OK')")
    $checks = foreach ($variable in @("DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY")) {
        $arguments = @("run", "--rm", "--network", "none", "-e", "DATABASE_URL=postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue",
            "-e", "SECRET_KEY=validation-session-secret-32-characters", "-e", "JWT_SECRET_KEY=validation-jwt-secret-32-characters",
            "-e", "FIELD_ENCRYPTION_KEY=validation-field-secret-32-characters", "-e", "DB_WAIT_TIMEOUT_SECONDS=1",
            "-e", "$variable=", "$Project-smoke", "true")
        $output = & docker @arguments 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -or -not $output.Contains("Variaveis obrigatorias ausentes em producao: $variable")) {
            throw "Missing-variable gate failed: $variable"
        }
        "IMAGE REJECTS MISSING $variable BEFORE DATABASE OK"
    }
    $checks | Set-Content (Join-Path $evidence "image-gates.txt")
    Invoke-RecordedDocker "pipeline.txt" ($compose + @("up", "--no-build", "--pull", "never", "--abort-on-container-exit", "--exit-code-from", "test"))
    Invoke-RecordedDocker "network.json" @("network", "inspect", "$($Project)_test")
    $network = Get-Content -Raw (Join-Path $evidence "network.json") | ConvertFrom-Json
    if (-not $network[0].Internal) { throw "Network must be internal." }
    Invoke-RecordedDocker "copy-junit.txt" ($compose + @("cp", "test:/tmp/junit.xml", (Join-Path $evidence "junit.xml")))
    Invoke-RecordedDocker "copy-coverage.txt" ($compose + @("cp", "test:/app/coverage.xml", (Join-Path $evidence "coverage.xml")))
    Invoke-RecordedDocker "copy-e2e.txt" ($compose + @("cp", "test:/tmp/e2e", (Join-Path $evidence "e2e")))
    [xml]$junit = Get-Content -Raw (Join-Path $evidence "junit.xml")
    foreach ($suite in $junit.testsuites.testsuite) {
        if ([int]$suite.failures -or [int]$suite.errors -or [int]$suite.skipped) { throw "JUnit gate failed." }
    }
    foreach ($target in @("test", "smoke")) {
        Invoke-RecordedDocker "source-$target.json" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-$target", "-m", "scripts.source_manifest")
        $manifest = Get-Content -Raw (Join-Path $evidence "source-$target.json") | ConvertFrom-Json -AsHashtable
        foreach ($entry in $manifest.GetEnumerator()) {
            $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $workspace $entry.Key)).Hash.ToLower()
            if ($actual -ne $entry.Value) { throw "Source mismatch in ${target}: $($entry.Key)" }
        }
        "Verified $($manifest.Count) files against $target image." | Set-Content (Join-Path $evidence "source-$target-check.txt")
    }
    Invoke-RecordedDocker "smoke-start.txt" ($compose + @("--profile", "smoke", "up", "--no-build", "--pull", "never", "-d", "--wait", "--wait-timeout", "120", "smoke"))
    Invoke-RecordedDocker "smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_smoke"))
    Invoke-RecordedDocker "security-smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke"))
    Invoke-RecordedDocker "database-stop.txt" ($compose + @("stop", "db-test"))
    Invoke-RecordedDocker "database-outage.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke", "--database-down"))
    Invoke-RecordedDocker "images.txt" @("image", "inspect", "$Project-test", "$Project-smoke", "--format", "{{.Id}}")
    Invoke-RecordedDocker "smoke-startup.txt" ($compose + @("logs", "--no-color", "smoke"))
}
finally {
    Invoke-RecordedDocker "cleanup.txt" ($compose + @("--profile", "smoke", "down", "-v"))
    $remaining = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
    if ($LASTEXITCODE -ne 0 -or $remaining) { throw "Containers remain." }
    $remaining = & docker network ls -q --filter "label=com.docker.compose.project=$Project"
    if ($LASTEXITCODE -ne 0 -or $remaining) { throw "Networks remain." }
    "Zero containers and networks for $Project." | Set-Content (Join-Path $evidence "cleanup-check.txt")
}
Get-ChildItem -File -Recurse $evidence | Where-Object Name -ne "sha256sums.txt" | Sort-Object FullName | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower(), [System.IO.Path]::GetRelativePath($evidence, $_.FullName).Replace("\", "/")
} | Set-Content -Encoding utf8 (Join-Path $evidence "sha256sums.txt")
