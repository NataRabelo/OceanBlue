# Sprint 2 — validacao adversarial independente

Data: 2026-09-06, America/Sao_Paulo; artefatos em 2026-09-07 UTC.

## Decisao

**GO para a Sprint 2 no escopo validado. Zero falhas criticas ou altas conhecidas abertas.** Oito achados corrigidos, 166 testes aprovados (25 novos), zero falhas/erros/skips, migrations e smoke produtivo aprovados, inclusive indisponibilidade real do banco. Este GO nao autoriza deploy nem integracoes reais.

| Gate final | Resultado |
|---|---|
| Dependencias e inventario | `pip check` e inventario de 146 rotas aprovados |
| Migrations | 21 revisions, upgrade/downgrade base/reupgrade, sentinela e comparacao de 45 tabelas aprovados |
| Suite/JUnit | 166 testes, 0 falhas, 0 erros, 0 skips; 138,116 segundos |
| Cobertura | 6.773/10.373 linhas e 929/2.238 ramos; combinado 7.702/12.611 = 61,07%; gate de 50% preservado |
| Imagem | Configuracao production, usuario nao root e quatro variaveis obrigatorias recusadas quando ausentes |
| Smoke | Gunicorn/entrypoint/migrations, health e readiness 200, tres headers de esquema forjados recusados com 403 |
| Banco parado | Liveness 200, readiness 503, login falha fechado e nao emite JWT; logs de aplicacao sem detalhes do driver |
| Inicializacao sem rede | Falha esperada com `OperationalError`, sem host/usuario/senha sinteticos na saida |
| Limpeza | Containers e redes dos tres projetos de validacao removidos |

## Base e isolamento da execucao

- Worktree inicialmente limpo, HEAD destacado em `352a77c`; sincronizado exclusivamente com a **main local `78ce583d9a0961bdb5d1b100da462688479bd639`**, por fast-forward. Sem fetch de remotos.
- Lido `docs/evidencias/producao/sprint-02-execucao.md` antes dos ataques e das alteracoes.
- PostgreSQL 16 exclusivo `oceanblue_test`, armazenamento tmpfs, redes Compose internas, nenhuma porta publicada. Projetos exclusivos `oceanblue-s02-adversarial`, `oceanblue-s02-proxy-before` e `oceanblue-s02-final`.
- Dados, senhas e marcadores `PRIVATE` inteiramente sinteticos. Os testes proíbem conexoes externas em Python; o isolamento de rede tambem cobre os processos de testes. Os ataques ao banco ocorreram somente nos projetos desta validacao.
- Nenhum push, integracao de branches apos a sincronizacao inicial, deploy, chamada real de boleto/Asaas ou Nota Fiscal/Focus/SEFAZ. Nenhum container de outro projeto foi alterado.

## Defeitos reproduzidos e corrigidos

| ID | Severidade | Ataque e efeito anterior | Correcao e regressao |
|---|---|---|---|
| VAL02-01 | Alta | Login de platform ignora tenant na autenticacao, mas usava esse campo no contador: seis nomes arbitrarios produziam seis respostas 401, sem 429. | Chave da plataforma ignora tenant. Testes sequenciais e 15 requisicoes HTTP concorrentes, com IPs e tenants diferentes: cinco verificacoes de senha e dez bloqueios. |
| VAL02-02 | Media | Contador convertia nomes para minusculas, mas autenticacao diferencia caixa. Tentativas contra `TENANT 1` bloqueavam a conta real de `Tenant 1`. Concatenacao por delimitador tambem nao representava tuplas sem ambiguidades. | Tupla JSON com nomes exatos e a mesma normalizacao da busca. Regressao de caixa e independencia de usuarios homonimos entre dois tenants e plataforma. |
| VAL02-03 | Baixa | CSRF Unicode provocava TypeError/500 no login e redefinicao. | Comparacao constante de bytes, tipos e presenca obrigatoria da sessao, sem valor sentinela. Unicode resulta em 400; suite preserva rejeicao de ausencia, replay e escritas sem CSRF. |
| VAL02-04 | Media | `/home` e `/platform/home` autenticados nao tinham `no-store`. | Toda resposta com usuario autenticado recebe `Cache-Control: no-store`; duas regressões de paginas, alem das APIs existentes. |
| VAL02-05 | Media | Corpo de resposta 2xx de webhook era lido integralmente e devolvido/armazenado como resposta de integracao; um provedor que ecoasse Authorization expunha a credencial e podia enviar um corpo excessivo. | Confirmacao local fixa; corpo externo nao e lido. Provedor simulado ecoando segredo fica fora da resposta e o teste verifica ausencia da leitura. |
| VAL02-06 | Baixa | Campos fiscais indicados pelo tenant consultavam existencia de arquivos e variaveis arbitrarias do servidor, mesmo com integracao real desativada. | Simulacao valida somente a declaracao dos campos e extensao; nao consulta filesystem nem ambiente. Mensagem explicita que o certificado real nao foi verificado. |
| VAL02-07 | Media | Readiness e entrypoint interpolavam excecoes completas de conexao em logs, expondo detalhes de infraestrutura e quaisquer dados contidos no erro do driver. | Logs mostram apenas o tipo da excecao. Regressao injeta SQL/parametros/driver com marcador privado; inicializacao real sem rede usa host/usuario/senha sinteticos e comprova ausencia desses marcadores. |
| VAL02-08 | Media | Gunicorn confiava nativamente em headers de esquema vindos de loopback, independentemente do ProxyFix: `/login` retornava HTTP 200 com X-Forwarded-Proto forjado e FORCE_HTTPS=true. | Comando produtivo inclui `--forwarded-allow-ips ""`. Regressao executa HTTP contra Gunicorn, cobrindo a camada que o cliente Flask dos testes anteriores nao exercitava. |

Os oito achados foram tratados no proprio worktree. VAL02-08 foi descoberto **depois** de uma suite completa aprovar 166 testes; por isso o aceite depende tambem do smoke real do servidor.

## Matriz de ataques

| Superficie | Casos exercitados | Resultado esperado/verificado |
|---|---|---|
| Autenticacao | Dois tenants e owner com mesmo usuario/senha; organizacao ausente/inexistente; conta inativa; claims tenant/sub/escopo/versao adulteradas sem assinatura valida | Identidade vinculada ao tenant informado; sem fallback; JWT adulterado recusado |
| Autorizacao | Todas as APIs, todos os metodos de negocio; token de plataforma em API operacional e vice-versa; perfil customizado tentando administrar acessos | 130 pares rota/metodo anonimos e 130 com escopo incorreto bloqueados; paginas protegidas podem redirecionar sem fornecer conteudo |
| CSRF | Login, redefinicao, logout e todas as escritas autenticadas; Unicode e cookie roubado | 57 pares de escrita sem CSRF bloqueados; entrada invalida nao produz 500 |
| Sessoes | Logout/replay; troca/redefinicao de senha; revogacao de usuario, perfil, permissao e acesso a empresa; rotacao de kid | Cookie anterior perde acesso conforme estado persistido; permissao e empresa reavaliadas no mesmo cookie |
| Tentativas | Threads, processos e instancias distintos; expiracao; IP forjado; variacao de tenant no owner; caixa e homonimos | Limites atomicos compartilhados, Retry-After, independencia das identidades e falha fechada |
| Tenant/IDs | Leitura, PUT e DELETE com IDs reais estrangeiros em categorias, clientes, produtos, funcionarios, roles e permissions; tenant/empresa enviados no corpo/query | Sem marcador privado na resposta; snapshots de nove tabelas do tenant alvo permanecem iguais |
| Multiempresa | Configuracao de cliente em outra empresa do mesmo tenant e em outro tenant: GET, PUT e teste de comunicacao; remocao da permissao global | Sem leitura, alteracao ou envio; configuracao protegida permanece intacta; empresa autorizada continua acessivel |
| Vendas/fiscal | Comprovante/cancelamento de venda estrangeira, XML/DANFE/consulta/cancelamento de nota estrangeira | Respostas 4xx, sem conteudo ou alteracao da venda/nota alvo |
| Integridade | FKs de outro tenant, vinculos financeiros entre empresas, filhos de venda/boleto/nota, consultas ORM e bulk mutations | Filtros e triggers impedem travessia; inventario de triggers cobre as FKs do schema |
| Cotas | Ultima vaga concorrente de produtos, empresas, funcionarios e vendas do mes; importacao com excedente e atualizacao existente | Exatamente uma criacao aceita por ultima vaga; sem extrapolacao; rollback das linhas recusadas |
| Trial | Data ausente, expiracao, ultimo dia em Sao Paulo e alternancia de plano/status | Negacao quando indisponivel, ultimo dia inclusivo, sem reinicio implicito |
| Banco indisponivel | Falhas injetadas no contador, leitura de sessao e commit do logout; PostgreSQL parado durante smoke; inicializacao sem rede | Sem autenticacao emitida em falha; rollback preserva sessao apos logout malsucedido; readiness 503 e liveness 200 |
| Seeds | Credencial ausente/fraca; idempotencia; tentativa de demo fora de development | Sem segredo impresso nem carga demo em producao |
| Criptografia | Envelope adulterado, chave desconhecida/rotacionada, legado v1, rotacao CLI e rollback por campo corrompido | Falha fechada; leitura legada e conversao transacional preservadas |
| Erros e segredos | Excecoes de API/banco, erro e sucesso do provedor, campos sensiveis, logs de startup/readiness | Sem detalhes privados em respostas e logs de aplicacao testados; confirmacao local do webhook |
| Headers/proxy | Loopback restrito a health/readiness, HTTP externo, headers forjados no cliente Flask e no Gunicorn produtivo; cookies seguros e no-store | Esquema nao e promovido por header sem confianca explicitamente configurada |
| Integracoes excluidas | Seletor, transporte e webhook Asaas; Focus/SEFAZ; redirects, allowlist/DNS e TLS de comunicacao | Integracoes reais continuam desativadas; nenhuma chamada real foi realizada |

Cobertura de autorizacao por rota/metodo nao significa exercicio de todas as combinacoes de payloads e FKs em cada endpoint. Os casos com IDs reais, snapshots e relacionamentos sao enumerados acima; os demais controles possuem regressões direcionadas em `tests/test_sprint02_security.py` e suites funcionais.

## Execucoes e artefatos

- [Baseline independente](sprint-02-validacao/baseline.txt): 141 testes aprovados na base original, migrations completas.
- [Reproducao anterior das regressões](sprint-02-validacao/regression-before.txt) e [JUnit](sprint-02-validacao/regression-before.xml): nove assercoes de comportamento falharam; uma decima falha era expectativa do novo teste sobre o destino de redirecionamento de pagina protegida, corrigida no teste. Nao foi contabilizada como vulnerabilidade.
- [Regressões apos primeiras correcoes](sprint-02-validacao/regression-after.txt) e [JUnit](sprint-02-validacao/regression-after.xml): 23 aprovadas, incluindo 317 verificacoes na matriz HTTP. Depois foram acrescentados dois casos de concorrencia/independencia, incluidos na suite final.
- [Suite antes do ajuste do Gunicorn](sprint-02-validacao/pre-proxy-fix-pipeline.txt), [smoke que detectou a falha](sprint-02-validacao/pre-proxy-fix-security-smoke.txt) e [prova de HTTP 200 com HTTPS obrigatorio](sprint-02-validacao/proxy-before.txt).
- [Pipeline final](sprint-02-validacao/pipeline.txt), [JUnit final](sprint-02-validacao/junit.xml) e [cobertura](sprint-02-validacao/coverage.xml).
- [Smoke produtivo](sprint-02-validacao/smoke.txt), [headers no Gunicorn](sprint-02-validacao/security-smoke.txt), [banco parado](sprint-02-validacao/database-outage.txt) e [logs produtivos](sprint-02-validacao/smoke-startup.txt).
- [Gate da imagem](sprint-02-validacao/image.txt), [startup sem banco e sem vazamento](sprint-02-validacao/startup-outage.txt), [identificadores das imagens](sprint-02-validacao/images.txt), [limpeza final](sprint-02-validacao/cleanup.txt) e [SHA-256](sprint-02-validacao/sha256sums.txt).

Nao houve reducao de cobertura minima, skip, xfail nem remocao de teste existente. Uma tentativa do runner no Windows PowerShell 5 interrompeu ao tratar mensagens normais do Docker em stderr como erro; o runner foi ajustado para decidir pelo exit code e executado com PowerShell 7. A primeira versao de testes tambem corrigiu o caminho real da pagina da plataforma. Essas iteracoes nao foram usadas como aceite.

Os artefatos gerados preservam seus bytes, incluindo CRLF e espacos emitidos pelo Docker; `.gitattributes` desativa conversao de texto e avisos de whitespace somente nessa pasta. Codigo e documentacao continuam sujeitos a verificacao normal de whitespace. O manifesto SHA-256 corresponde aos arquivos preservados.

## Reproducao

Docker Linux e PowerShell 7, na raiz de um checkout desta entrega:

```powershell
pwsh -NoProfile -File scripts/validate_sprint02.ps1 -Project oceanblue-s02-repro
```

O nome deve ser exclusivo e sem containers preexistentes. O script constroi imagens, valida dependencias/inventario/migrations, executa pytest, copia JUnit/cobertura, inicializa producao, executa smoke, para somente seu banco, testa falha fechada e remove seus containers/rede em `finally`. Os artefatos sao gravados nesta pasta de evidencias e podem substituir arquivos de uma reproducao anterior.

O gate adicional da imagem pode ser repetido em Git Bash:

```sh
sh scripts/validate_image.sh oceanblue-s02-repro-smoke
```

O teste adicional de startup com banco inacessivel usa exclusivamente valores sinteticos:

```powershell
docker run --rm --network none -e DATABASE_URL=postgresql+psycopg2://PRIVATE-user:PRIVATE-password@PRIVATE-host/oceanblue -e SECRET_KEY=validation-session-secret-32-characters -e JWT_SECRET_KEY=validation-jwt-secret-32-characters -e FIELD_ENCRYPTION_KEY=validation-field-secret-32-characters -e DB_WAIT_TIMEOUT_SECONDS=1 oceanblue-s02-repro-smoke true
```

Esse comando deve terminar com exit code diferente de zero e mostrar somente `OperationalError`, sem qualquer marcador `PRIVATE`. No teste com o banco parado, health/readiness e headers usam HTTP real contra Gunicorn; o POST de login usa o cliente Flask com configuracao produtiva e esquema HTTPS, atingindo o PostgreSQL realmente indisponivel.

Para repetir somente os ataques pytest, use um novo projeto Compose e `docker compose -p NOME -f compose.test.yml run --rm test python -m pytest tests/test_sprint02_adversarial.py --no-cov -s`; depois remova esse projeto com `down -v`. O gate de cobertura da suite completa continua em 50%; `--no-cov` e usado somente na reproducao isolada dos ataques.

## Limites do aceite

Esta e uma validacao local independente de codigo, banco isolado e imagem produtiva. Nao equivale a deploy, homologacao de integracao real, pentest externo, carga produtiva ou verificacao da topologia de proxy real. O operador ainda deve configurar corretamente a fronteira de proxy e manter exclusivamente hosts confiaveis na allowlist de comunicacao. SQL bruto futuro exige revisao explicita de escopo. Os logs de PostgreSQL nos artefatos contem SQL e hashes de senhas **sinteticas** dos testes; nao sao dados produtivos.

As correcoes nao exigem nova migration: o historico existente foi novamente exercitado por completo, incluindo ida/volta e deteccao de dados legados inconsistentes. A implantacao futura deve preservar as migrations da Sprint 2 e as instrucoes do [guia operacional atualizado](../../02-instalacao-e-ambiente/seguranca-sprint-02.md).
