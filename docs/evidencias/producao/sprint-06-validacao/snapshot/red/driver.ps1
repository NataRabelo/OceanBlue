param($SnapshotScript,$Mode,$Project,$DatabaseContainer,$ApplicationContainer,$Database,$Directory,$Injection)
$ErrorActionPreference = 'Stop'
$script:injected = $false
function docker {
    $arguments = @($args)
    $isStorageCopy = $arguments[0] -eq 'cp' -and $arguments[-1] -eq "${ApplicationContainer}:/app/instance"
    if ($Injection -in @('copy-failure','rollback-failure','interrupt') -and $isStorageCopy -and -not $script:injected) {
        $script:injected = $true
        if ($Injection -eq 'interrupt') { throw [OperationCanceledException]::new('Injected interruption before storage copy') }
        & docker.exe @arguments 2>&1
        throw 'Injected storage-copy failure AFTER real copy'
    }
    if ($Injection -eq 'backup-failure' -and $arguments[0] -eq 'cp' -and $arguments[1] -like '*:/app/instance*') { throw 'Injected backup interruption' }
    if ($Injection -eq 'rollback-failure' -and $script:injected -and $arguments[0] -eq 'run') { throw 'Injected rollback helper failure' }
    & docker.exe @arguments 2>&1
    $global:LASTEXITCODE = $LASTEXITCODE
}
try {
    & $SnapshotScript -Mode $Mode -Project $Project -DatabaseContainer $DatabaseContainer -ApplicationContainer $ApplicationContainer -Database $Database -DatabaseUser proof -Directory $Directory
    exit 0
} catch {
    Write-Output $_
    exit 1
}
