# Validacao adversarial de seguranca — Sprint 6

Base: `main` / `804256a`. Alteracoes limitadas a `app/operations.py`,
`app/security/proxy.py`, `app/security/headers.py` e
`tests/test_sprint06_security_adversarial.py`. Sem commit.

Docker autorizado durante a tarefa. Recursos exclusivos
`oceanblue-s06-security-944e-*`, PostgreSQL descartavel em tmpfs, rede interna,
sem portas publicadas ou integracoes externas. Imagem fornecida:
`oceanblue-s06-complete-test`, ID
`sha256:0e93bf35b7a44c0525d1ae30c9d0b2cf137e0739efe7ad1ddbf36ebccc480429`.

## Resultados

- `red.txt` / `red.xml`: **32 falhas, 17 aprovados**, antes das correcoes,
  com os tres arquivos de aplicacao da base montados explicitamente.
- `green.txt` / `green.xml`: **49 aprovados**, mesmos testes com as correcoes.
- `regression.txt` / `regression.xml`: **104 aprovados em 78,47 s**, incluindo
  a suite operacional Sprint 6, headers de seguranca e ataques da Sprint 2.

As contagens representam casos parametrizados, nao 32 vulnerabilidades distintas.

## Achados e correcoes

| Achado reproduzido | Correcao |
| --- | --- |
| Proxy confiavel encaminhando X-Forwarded-For loopback permitia HTTP nas quatro sondas, mesmo com X-Forwarded-Proto http | Preservar IP do transporte antes de ProxyFix; excecao apenas para GET/HEAD locais sem cabecalhos de encaminhamento |
| Campos permitidos do log JSON aceitavam senha, CPF, cartao, token, objetos e valores nao finitos | Validar evento, ID, metodo, status e duracao; obter template de rota do contexto, sem valores de URL; omitir dados invalidos |
| Metodo HTTP arbitrario era refletido no log | Metodos desconhecidos viram OTHER |
| Hook anterior encerrando requisicao gerava ID apenas na resposta, enquanto log recebia null e duracao podia ficar negativa | Inicializar ID em g no encerramento e calcular duracao nao negativa com um unico instante final |
| Authorization nao ASCII causava TypeError em compare_digest; token nao ASCII tambem falhava | Rejeitar credenciais nao ASCII com 404 antes da comparacao constante |
| Primeira coleta nao expunha contadores zerados | Inicializar todas as series de contadores |
| /health, /readiness e respostas negativas de /metrics podiam ser armazenadas em cache | Aplicar Cache-Control no-store tambem nessas rotas |
| Escrita parcial da sentinela era aceita como storage pronto | Verificar quantidade escrita e falhar com OSError, preservando limpeza |

Controles positivos cobrem loopback direto, proxy confiavel, ultimo salto,
cabecalhos de host/porta/prefixo ignorados, ID valido preservado, ID com CRLF
substituido, template de rota sem CPF, exclusao de query/body/cookie/Authorization,
texto/traceback de excecao omitidos, liveness independente de banco,
readiness 503 sem detalhes privados e bloqueio de metodos mutaveis sem storage.

## Reproduzir red e green

PowerShell, na raiz deste checkout com o teste novo. Usar um nome exclusivo
livre para o projeto; o exemplo abaixo nao reutiliza os recursos da execucao original.
Os comandos nao constroem imagens nem baixam dependencias Python.

```powershell
$securityRoot = (Get-Location).Path
$securityProject = 'oceanblue-s06-security-replay'
$securityImage = 'sha256:0e93bf35b7a44c0525d1ae30c9d0b2cf137e0739efe7ad1ddbf36ebccc480429'
$securityEvidence = Join-Path $securityRoot 'docs/evidencias/producao/sprint-06-validacao/security'
docker compose -p $securityProject -f compose.test.yml up -d --wait db-test
git archive --format=tar --output="$securityEvidence/baseline-804256a.tar" 804256a app/operations.py app/security/proxy.py app/security/headers.py
$securityCommon = @(
    '--rm', '--network', "${securityProject}_test",
    '-e', 'TEST_DATABASE_URL=postgresql+psycopg2://oceanblue_test:isolated-test-only@db-test:5432/oceanblue_test',
    '-e', 'FLASK_SKIP_DOTENV=1',
    '--mount', "type=bind,source=$securityRoot/tests/test_sprint06_security_adversarial.py,target=/app/tests/test_sprint06_security_adversarial.py,readonly",
    '--mount', "type=bind,source=$securityEvidence,target=/evidence"
)

docker run @securityCommon --name "${securityProject}-red" $securityImage sh -c 'tar -xf /evidence/baseline-804256a.tar -C /app && python -m pytest tests/test_sprint06_security_adversarial.py --no-cov --tb=short -q --junitxml=/evidence/replay-red.xml'
# Esperado: exit 1, 32 failed, 17 passed. A extracao ocorre somente no container.

$securityCode = @(
    '--mount', "type=bind,source=$securityRoot/app/operations.py,target=/app/app/operations.py,readonly",
    '--mount', "type=bind,source=$securityRoot/app/security/proxy.py,target=/app/app/security/proxy.py,readonly",
    '--mount', "type=bind,source=$securityRoot/app/security/headers.py,target=/app/app/security/headers.py,readonly"
)
docker run @securityCommon @securityCode --name "${securityProject}-green" $securityImage python -m pytest tests/test_sprint06_security_adversarial.py --no-cov --tb=short -q --junitxml=/evidence/replay-green.xml
# Esperado: exit 0, 49 passed.

docker run @securityCommon @securityCode --name "${securityProject}-regression" $securityImage python -m pytest tests/test_sprint06_security_adversarial.py tests/test_sprint06_operations.py tests/test_security_headers.py tests/test_sprint02_adversarial.py --no-cov --tb=short -q --junitxml=/evidence/replay-regression.xml
docker compose -p $securityProject -f compose.test.yml down -v
```

`baseline-804256a.tar` foi extraido de Git apenas com os tres arquivos de aplicacao.
O red original tambem usou esses arquivos da base, montados antes de qualquer
correcao. Os mounts explicitos evitam depender de pequenas diferencas entre o
conteudo da imagem fornecida e o checkout.

## Limites

Esta rodada exercita Flask/WSGI e componentes Python, com migrations no
PostgreSQL isolado. Nao constitui validacao integral, TLS real no nginx,
Gunicorn, carga, failover, coleta Prometheus, backup/restore ou deploy.
O cenario do hook anterior testa a composicao de callbacks; a factory atual
registra operacoes primeiro. Falhas de banco/storage dos testes novos usam
injecao controlada, exceto escrita e limpeza da sentinela no filesystem.
Revisao desatualizada e permissoes reais tambem sao cobertas pela suite operacional existente.

Usou-se `--no-cov` porque este e um recorte adversarial: nao foi aplicado o gate
global de cobertura de 50%. As duas integrais finais sao coordenadas pelo
responsavel pelo ambiente compartilhado. Metricas continuam locais ao processo,
como no contrato de um worker. Proxy confiavel ainda precisa substituir headers
e o backend precisa manter sua fronteira de rede. A validacao do formato do ID
nao o transforma em credencial de autenticacao. CSP legado nao foi alterado.
Dados sensiveis nos testes e evidencias red sao exclusivamente sinteticos.
O responsavel pela validacao operacional identificou separadamente possivel
vazamento de URI no error_log nginx durante falha de upstream e assumiu
nginx.conf e sua prova real. Este escopo nao verifica nem corrige logs nginx.
