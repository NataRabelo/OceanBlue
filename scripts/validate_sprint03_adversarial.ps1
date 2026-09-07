param([string]$Project = "oceanblue-s03-validation-final")

$ErrorActionPreference = "Stop"
$workspace = Split-Path $PSScriptRoot -Parent
$evidence = Join-Path $workspace "docs/evidencias/producao/sprint-03-validacao"
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
    Invoke-RecordedDocker "build.txt" ($compose + @("build", "test", "smoke"))
    Invoke-RecordedDocker "image-user.txt" @("run", "--rm", "--network", "none", "--entrypoint", "id", "$Project-smoke", "-u")
    if ((Get-Content (Join-Path $evidence "image-user.txt")).Trim() -eq "0") { throw "Production image must not run as root." }
    Invoke-RecordedDocker "image.txt" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-smoke", "-m", "pip", "check")
    Invoke-RecordedDocker "image-default.txt" @("run", "--rm", "--network", "none", "--entrypoint", "python", "$Project-smoke", "-c", "from app.config import get_config, ProductionConfig; assert get_config() is ProductionConfig; print('DEFAULT PRODUCTION OK')")
    $imageChecks = foreach ($variable in @("DATABASE_URL", "SECRET_KEY", "JWT_SECRET_KEY", "FIELD_ENCRYPTION_KEY")) {
        $arguments = @("run", "--rm", "--network", "none",
            "-e", "DATABASE_URL=postgresql+psycopg2://unused:unused@127.0.0.1/oceanblue",
            "-e", "SECRET_KEY=validation-session-secret-32-characters",
            "-e", "JWT_SECRET_KEY=validation-jwt-secret-32-characters",
            "-e", "FIELD_ENCRYPTION_KEY=validation-field-secret-32-characters",
            "-e", "DB_WAIT_TIMEOUT_SECONDS=1", "-e", "$variable=", "$Project-smoke", "true")
        $output = & docker @arguments 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0 -or -not $output.Contains("Variaveis obrigatorias ausentes em producao: $variable")) {
            throw "Image accepted missing variable or failed unexpectedly: $variable"
        }
        "IMAGE REJECTS MISSING $variable BEFORE DATABASE OK"
    }
    $imageChecks | Out-File -Encoding utf8 (Join-Path $evidence "image-gates.txt")
    Invoke-RecordedDocker "pipeline.txt" ($compose + @("up", "--abort-on-container-exit", "--exit-code-from", "test"))
    Invoke-RecordedDocker "copy-junit.txt" ($compose + @("cp", "test:/tmp/junit.xml", (Join-Path $evidence "junit.xml")))
    Invoke-RecordedDocker "copy-coverage.txt" ($compose + @("cp", "test:/app/coverage.xml", (Join-Path $evidence "coverage.xml")))
    [xml]$junit = Get-Content -Raw (Join-Path $evidence "junit.xml")
    foreach ($suite in $junit.testsuites.testsuite) {
        if ([int]$suite.failures -or [int]$suite.errors -or [int]$suite.skipped) { throw "JUnit gate failed." }
    }
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

Get-ChildItem -File $evidence | Where-Object Name -ne "sha256sums.txt" | Sort-Object Name | ForEach-Object {
    "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash.ToLower(), $_.Name
} | Set-Content -Encoding utf8 (Join-Path $evidence "sha256sums.txt")
