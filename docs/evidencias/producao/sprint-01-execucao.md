# Sprint 1 de producao — execucao

Data: 2026-09-06. Base: `352a77c` (V2.0.1). Escopo: instalacao e verificacao reproduzivel, sem integracoes fiscais/bancarias reais.

## Resultado

Checkout de arquivos versionados exportado do indice Git para diretorio novo em TEMP, sem `.env`, `.venv`, `instance`, caches ou arquivos nao versionados. Build Linux com instalacao dos locks por hash e PostgreSQL descartavel: **63 testes passaram em 29,63 s**, sem falhas, skips, xfails ou warnings. Os **52 testes existentes foram preservados**, com 11 casos adicionais de configuracao/saude/CSRF. O CI minimo combinado de linhas e ramificacoes (50%) passou com **53,42%**. Isso nao equivale a homologacao funcional integral de todas as rotas.

As **19 migrations** passaram por upgrade individual, downgrade completo, verificacao de ausencia de tabelas/ENUMs orfaos e reupgrade ao unico head `2b3c4d5e6f7a`. **42 tabelas** e seus conjuntos de colunas coincidem com os modelos. Um tenant criado na revision inicial permaneceu ate head, exercitando os backfills de permissoes. A comparacao nao pretende certificar equivalencia integral de tipos, indices/defaults nem todas as combinacoes de dados historicos.

O inventario gerado lista **143 rotas**, sendo 29 fiscais/bancarias explicitamente fora do escopo funcional, e associa requisitos, servicos e testes diretos de servico sem confundir isso com cobertura HTTP.

O smoke da imagem de producao tambem passou com **exit 0**: container `healthy`, usuario `appuser`, entrypoint aplicando migrations e Gunicorn iniciando quatro workers. `python -m pip check` da imagem produtiva passou; `/api/ready` respondeu `database: ok`, `status: ok`. Nenhuma porta foi publicada e nenhuma credencial externa foi utilizada.

## Artefatos da execucao final

- [Log integral das migrations, inventario e pytest](sprint-01-validacao.txt).
- [JUnit: 63 testes, zero falhas/erros/skips](sprint-01-junit.xml).
- [Log de inicializacao de producao/Gunicorn](sprint-01-smoke.txt).
- Cobertura XML gerada pelo container: **5.759 / 9.988 linhas (57,66%)**, **699 / 2.102 ramificacoes (33,25%)**; combinado **6.458 / 12.090 (53,42%)**. Nenhum modulo de `app` omitido. O XML pode ser copiado conforme o guia; SHA-256 deste run: `a5eee0f84abdd211c3ce712755964e04f3669472756ea940facad546219bbbdc`. O hash identifica esta medicao (timestamps podem mudar em nova execucao), nao e um requisito de igualdade entre runs.

## Versoes verificadas

| Componente | Versao |
|---|---|
| Host | Windows / Docker Desktop, containers Linux amd64 |
| Docker Engine / Compose | 29.7.2 / 5.5.0 |
| Python | 3.12.12 |
| PostgreSQL | 16.12 (Debian 16.12-1.pgdg13+1) |
| Flask / Flask-SQLAlchemy / Flask-Migrate | 3.0.3 / 3.1.1 / 4.0.7 |
| SQLAlchemy / Alembic / psycopg2-binary | 2.0.52 / 1.19.2 / 2.9.9 |
| pytest / pytest-cov / coverage | 8.3.5 / 6.1.1 / 7.16.0 |
| pip / pip-tools | 25.0.1 / 7.4.1 |
| Gunicorn | 21.2.0 |

Todas as outras versoes/hashes estao nos dois locks. Imagem Python: `sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`. Imagem PostgreSQL: `sha256:23af655ba1ddf74eaa002e3deaf5fce022ab8791672336a7c1fb0ef2d57efb7f`.

## Comandos e resultados

1. Baseline anterior a configuracao nova: `python -m pytest -q --cov=app --cov-report=term --tb=short`, em container Python 3.12.12 com requirements originais e pytest instalado. Resultado: **52 passed, 14 warnings, 224,85 s**, cobertura somente de linhas **57%**. SQLite com schema `create_all`; nao validava migrations.
2. Resolucao: `pip-compile --generate-hashes --allow-unsafe --strip-extras --resolver=backtracking -o requirements.txt requirements.in` e equivalente para `requirements-dev.txt`. Pip 25.0.1 fixado tambem no lock de desenvolvimento para manter a ferramenta de resolucao no ambiente verificado.
3. Diagnostico PostgreSQL da suite legada, apos migrar: **52 passed, 2 warnings, 33,75 s**. Deprecacao do `get_engine` corrigida posteriormente.
4. Diagnostico focal: `python -m pytest tests/test_runtime.py tests/test_permissions_security.py -q --no-cov`: **18 passed em 5,46 s**.
5. Exportacao limpa PowerShell, apos `git add` e `git diff --cached --check`:

```powershell
$sprintCleanPath = Join-Path $env:TEMP 'oceanblue-sprint01-clean-20260906-v2'
New-Item -ItemType Directory -Path $sprintCleanPath
git checkout-index --all --prefix="$($sprintCleanPath.Replace('\','/'))/"
docker compose -p oceanblue-sprint01-clean -f "$sprintCleanPath/compose.test.yml" up --build --abort-on-container-exit --exit-code-from test
```

Resultado final do comando 5: **exit 0**, `No broken requirements found`, inventario OK, migrations OK e **63 passed**. O codigo/documentacao funcional exportados sao os do commit desta entrega; este relatorio e os logs foram acrescentados depois da medicao. Nao houve dependencia dos arquivos locais do worktree.

Para reproduzir apos checkout do commit, basta o comando padrao do [guia](../../02-instalacao-e-ambiente/como-rodar-o-projeto.md):

```sh
docker compose -f compose.test.yml up --build --abort-on-container-exit --exit-code-from test
docker compose -f compose.test.yml --profile smoke up -d --build --wait --wait-timeout 120 smoke
docker compose -f compose.test.yml --profile smoke ps
docker compose -f compose.test.yml --profile smoke down -v
```

O workflow GitHub Actions foi criado com esses gates e coleta de artefatos. Sua execucao remota nao foi disparada nesta tarefa; os comandos equivalentes foram executados localmente sobre exportacao limpa.

## Migrations exercitadas

Todas com upgrade e downgrade executados, inclusive merges:

```text
1150177c20ca  initial
7f3c1a2b9d4e  roles_and_permissions
9d1dca4d2bc5  v2
c3a1f9d4e8b2  convert_quantities_to_integer
4b2d8b0f6c11  platform_owners
8f6e4c2a1b9d  pdv_financeiro_permissions_and_defaults
b7c9d1e2f3a4  cupons_adiantamentos_validade_salario
d4e5f6a7b8c9  empresa_visual_mode
e6f7a8b9c0d1  stock_alert_settings
f2b4c6d8e9f1  client_wallet_messaging_and_reversal_controls
f9d0e1a2b3c4  boleto_financeiro_models
a1b2c3d4e5f6  stock_alert_dispatch_tracking
b3c4d5e6f7a8  cashback_sale_controls
a4f1c8d2e7b9  wholesale_and_fiscal_foundation
c9d8e7f6a5b4  merge_cashback_and_fiscal_heads
0f6a8c2d4e9b  audit_and_saas_limits
ea3d60221646  merge_migration_heads
1a2b3c4d5e6f  sprint3_boleto_fiscal_external_status
2b3c4d5e6f7a  sprint4_asaas_focus_real_configs
```

## Falhas encontradas e alteracoes

| Achado reproduzido | Correcao |
|---|---|
| Dependencias transitivas livres, MercadoPago sem versao, pytest ausente | Locks completos com hashes, dependencias prod/dev separadas e ferramentas fixadas |
| WeasyPrint/MercadoPago sem referencias no codigo | Removidos da instalacao; nenhuma funcionalidade/adaptador real alterado |
| SQLite e `create_all` ocultavam problemas de migrations | Suite inteira em PostgreSQL com schema migrado; reset por TRUNCATE e limpeza de sessao |
| Estado global de limiter/sessao e ambiente herdado | Fixtures isoladas, segredos de teste, validacao de banco, rede bloqueada e CSRF ativo |
| `f9d0e1a2b3c4`: `DROP CONSTRAINT None` falhava no downgrade | Descobre nomes reais das duas FKs antes de remove-las; compativel com nomes historicos do PostgreSQL |
| `1150177c20ca`: ENUMs sobravam apos downgrade, impedindo reupgrade (`DuplicateObject`) | Remove os oito ENUMs pertencentes a revision depois das tabelas |
| `7f3c1a2b9d4e`: tenant preexistente causava `DatatypeMismatch`, boolean recebia inteiro `1` | Dois INSERTs usam literal SQL `TRUE`; o tenant sentinela passou a exercitar esse caminho |
| `migrations/env.py`: API `get_engine()` depreciada | Usa `db.engine`, compativel com Flask-SQLAlchemy fixado |
| Primeira iteracao de cobertura omitia ramificacoes porque `.coverage*` tambem excluia `.coveragerc` do build | Ignora somente `.coverage` e `.coverage.*`; execucao final mede Branch/BrPart |
| Novo teste CSRF esperava mensagem interna e depois 403 | Ajustado ao contrato observado: 401 sem token; 400 de validacao do payload com token correto e perfil autorizado |
| Imagem instalava curl via apt mutavel | Healthcheck usa urllib da biblioteca padrao; base por digest e nenhum apt adicional |

Nao foram removidos testes, reduzidas assercoes existentes, usados skips/xfails nem implementadas chamadas reais a Asaas/Focus/SEFAZ. Mudancas em migrations de boleto dizem respeito exclusivamente ao rollback estrutural necessario para verificar todo o historico.

## Limites e pendencias fora desta Sprint

Cobertura de 53,42% combinada e um baseline com gate, nao aceite completo de produto. O [inventario](../../04-modulos-e-funcionalidades/inventario-producao-sprint-01.md) explicita lacunas de CRUD/HTTP e servicos. A homologacao manual de todos os fluxos e futura. O seed legado contem credenciais demonstrativas/imprime senhas; foi documentado como inadequado para producao, sem redesenho de onboarding nesta Sprint. Testes fiscais/bancarios existentes usam simulacoes e nao representam certificacao externa. Nao foram executados deploy remoto, restore de backup produtivo, carga concorrente ou teste nativo Windows.
