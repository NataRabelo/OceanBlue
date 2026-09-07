param([string]$Project = "oceanblue-s02-final")

$ErrorActionPreference = "Stop"
$workspace = Split-Path $PSScriptRoot -Parent
$evidence = Join-Path $workspace "docs/evidencias/producao/sprint-02-validacao"
Set-Location $workspace
New-Item -ItemType Directory -Force $evidence | Out-Null
$compose = @("compose", "-p", $Project, "-f", "compose.test.yml")

function Invoke-RecordedDocker {
    param([string]$Log, [string[]]$Arguments)
    $ErrorActionPreference = "Continue"
    & docker @Arguments 2>&1 | Out-File -Encoding utf8 (Join-Path $evidence $Log)
    if ($LASTEXITCODE -ne 0) { throw "Docker failed ($LASTEXITCODE): $Log" }
}

$existing = & docker ps -aq --filter "label=com.docker.compose.project=$Project"
if ($LASTEXITCODE -ne 0 -or $existing) { throw "Choose a fresh isolated Compose project." }

try {
    Invoke-RecordedDocker "build-final.txt" ($compose + @("build", "test", "smoke"))
    Invoke-RecordedDocker "pipeline.txt" ($compose + @("up", "--abort-on-container-exit", "--exit-code-from", "test"))
    Invoke-RecordedDocker "copy-junit.txt" ($compose + @("cp", "test:/tmp/junit.xml", (Join-Path $evidence "junit.xml")))
    Invoke-RecordedDocker "copy-coverage.txt" ($compose + @("cp", "test:/app/coverage.xml", (Join-Path $evidence "coverage.xml")))
    Invoke-RecordedDocker "smoke-start.txt" ($compose + @("--profile", "smoke", "up", "-d", "--wait", "--wait-timeout", "120", "smoke"))
    Invoke-RecordedDocker "smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_smoke"))
    Invoke-RecordedDocker "security-smoke.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke"))
    Invoke-RecordedDocker "outage-stop.txt" ($compose + @("stop", "db-test"))
    Invoke-RecordedDocker "database-outage.txt" ($compose + @("exec", "-T", "smoke", "python", "-m", "scripts.validate_security_smoke", "--database-down"))
    Invoke-RecordedDocker "smoke-startup.txt" ($compose + @("logs", "--no-color", "smoke"))
    Invoke-RecordedDocker "images.txt" @("image", "inspect", "$Project-test", "$Project-smoke", "--format", "{{.Id}}")
}
finally {
    Invoke-RecordedDocker "cleanup.txt" ($compose + @("--profile", "smoke", "down", "-v"))
}
