param([string]$Project = 'oceanblue-s06-proxy-log', [Parameter(Mandatory)][string]$EvidenceDirectory, [string]$TestImage = 'oceanblue-s06-complete-test')
$ErrorActionPreference = 'Stop'
$workspace = Split-Path $PSScriptRoot -Parent
if ($Project -notmatch '^oceanblue-s0[67]-proxy-log[a-z0-9-]*$') { throw 'Exclusive proxy log project required.' }
$evidence = [IO.Path]::GetFullPath((Join-Path $workspace $EvidenceDirectory))
if (Test-Path -LiteralPath $evidence) { throw 'New evidence directory required.' }
New-Item -ItemType Directory -Path $evidence | Out-Null
function Docker {
    $output = & docker.exe @args 2>&1
    if ($LASTEXITCODE) { throw ($output | Out-String) }
    $output
}
if (Docker ps -aq --filter "label=com.docker.compose.project=$Project") { throw 'Project exists.' }
try {
    Docker network create --internal --label "com.docker.compose.project=$Project" $Project | Out-Null
    Docker volume create --label "com.docker.compose.project=$Project" "$Project-tls" | Out-Null
    Docker run --rm --network none --user 0 --mount "type=volume,source=$Project-tls,target=/tls" --entrypoint sh $TestImage -c 'openssl req -x509 -newkey rsa:2048 -nodes -keyout /tls/privkey.pem -out /tls/fullchain.pem -days 2 -subj /CN=proxy -addext subjectAltName=DNS:proxy && chown 101:101 /tls/* && chmod 600 /tls/privkey.pem' | Out-File (Join-Path $evidence 'tls.txt')
    Docker run -d --name $Project --label "com.docker.compose.project=$Project" --network $Project --network-alias proxy --network-alias app --user 101:101 --read-only --cap-drop ALL --security-opt no-new-privileges:true --tmpfs '/tmp:mode=1777,size=8m' --mount "type=bind,source=$workspace/infra/production/nginx.conf,target=/etc/nginx/nginx.conf,readonly" --mount "type=volume,source=$Project-tls,target=/etc/oceanblue/tls,readonly" nginxinc/nginx-unprivileged@sha256:7377697a821c131a924a7105fafbe7414db4e9fcc77a6f08f776f33f141ec3f8 | Out-Null
    $client = @'
import ssl, time
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
context = ssl.create_default_context(cafile='/tls/fullchain.pem')
for attempt in range(30):
    try:
        urlopen('https://proxy:8443/S06_PROXY_PASSWORD?cpf=52998224725&card=4111111111111111', context=context, timeout=3)
        raise AssertionError('Unavailable upstream must fail')
    except HTTPError as response:
        assert response.code == 502, response.code
        print('REAL TLS UPSTREAM FAILURE 502 VERIFIED')
        break
    except URLError:
        time.sleep(.1)
else:
    raise AssertionError('Proxy did not start')
'@
    Docker run --rm --network $Project --mount "type=volume,source=$Project-tls,target=/tls,readonly" $TestImage python -c $client | Out-File (Join-Path $evidence 'client.txt')
    $logs = Docker logs $Project | Out-String
    $logs | Set-Content (Join-Path $evidence 'proxy.txt')
    $leaked = @('S06_PROXY_PASSWORD', '52998224725', '4111111111111111') | Where-Object { $logs.Contains($_) }
    @{status=502; leaked_synthetic_sentinels=$leaked.Count; structured_access_log=$logs.Contains('"proxy_request"')} | ConvertTo-Json | Set-Content (Join-Path $evidence 'result.json')
    if ($leaked -or -not $logs.Contains('"proxy_request"')) { throw 'Proxy leaked private request data or lost structured access evidence.' }
} finally {
    & docker.exe rm -f $Project *> (Join-Path $evidence 'cleanup-container.txt')
    & docker.exe network rm $Project *> (Join-Path $evidence 'cleanup-network.txt')
    & docker.exe volume rm "$Project-tls" *> (Join-Path $evidence 'cleanup-volume.txt')
}
