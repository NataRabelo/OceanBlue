param([string]$Project = "oceanblue-s05-final", [string]$EvidenceDirectory = "docs/evidencias/producao/sprint-05-execucao")

$ErrorActionPreference = "Stop"
& (Join-Path $PSScriptRoot "validate_sprint04.ps1") -Project $Project -EvidenceDirectory $EvidenceDirectory
