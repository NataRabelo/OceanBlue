# Sprint 2 — execucao

Data: 2026-09-06, America/Sao_Paulo; logs finais em 2026-09-07 UTC.

## Resultado

**Implementacao concluida e pronta para validacao independente.** Pipeline local completo com **141 testes aprovados, zero falhas/erros/skips**, cobertura combinada **57,49%**, migrations com ida/volta e smoke produtivo aprovados. Nenhuma falha critica/alta conhecida permanece no escopo implementado e verificado. Este relatorio nao substitui a validacao independente nem autoriza publicacao/deploy.

## Precondicao e base

- Worktree inicialmente limpo e HEAD destacado em `352a77c`.
- Executados `git fetch origin main` e `git merge --ff-only origin/main`; base avancou para `8f8c3b3`.
- Lido `docs/evidencias/producao/sprint-01-validacao.md`, com **Decisao: GO para a Sprint 1**, antes de modificar o codigo.
- Nenhum arquivo do checkout principal foi alterado. Nenhum push, merge remoto, deploy ou chamada real a Asaas/Focus/SEFAZ foi executado.

## Entregas e provas

| Area | Comportamento implementado | Verificacao |
|---|---|---|
| Identidade | Organizacao explicita no login operacional; plataforma selecionada separadamente; sem busca alternativa/fallback | Mesmo usuario/senha em dois tenants e owner; organizacao ausente/inexistente recusada; claims corretas |
| Senhas | Troca com senha atual; redefinicao por codigo aleatorio de 15 minutos, hash no banco, uso unico e vinculo a tenant/usuario/versao | Senha errada/curta, expiracao, reutilizacao, consumo concorrente e fluxo HTTP completo |
| Sessoes | Versao persistida e verificada; revogacao de logout no PostgreSQL; usuario/perfil ativo e permissoes atuais | Replay de cookie roubado recusado; troca/redefinicao revogam outras sessoes; desativacao tenant/owner e rotacao de kid |
| CSRF e HTTPS | Login com CSRF; logout POST; formularios de senha com CSRF; loopback HTTP somente para health/readiness; headers encaminhados apenas via ProxyFix configurado | Login sem CSRF, logout GET/escrita sem CSRF e headers forjados recusados |
| Tentativas | Contador PostgreSQL atomico por conta e IP; janela fixa, tentativas bem-sucedidas tambem contam; Retry-After e falha fechada | 15 tentativas concorrentes entre instancias: exatamente cinco aceitas; processos distintos compartilham contador; expiracao e X-Forwarded-For forjado |
| Erros | Erros inesperados e de banco sem detalhes internos na resposta; mensagens de provedores nao expoem corpo de erro/credenciais | Excecao com marcador privado nao chega ao cliente; erro de cota de importacao nao expoe SQL; paginas/API sensiveis no-store |
| Seeds | Senhas explicitas e fortes; nenhum segredo impresso; producao cria apenas owner; demo exige development e opt-in | Credencial ausente recusa; criacao/idempotencia do owner; opt-in de demo ignorado fora de development |
| Criptografia | Novas escritas Fernet v2 com identificador de chave; leitor legado v1; mapa de chaves validado; rotacao transacional e campos Text | Adulteracao/chave desconhecida, troca de chave, leitura legada, validacao sem escrita e rollback completo de campo corrompido |
| Isolamento | Filtros ORM de tenant/empresa e filhos; validacao de empresa inclusive para administrador; triggers de integridade em todas as tabelas com tenant e filhos de boleto | Consultas e bulk mutations cruzadas, FKs de outro tenant, vinculos financeiros entre empresas, CRUD HTTP, reset cruzado e fronteira plataforma/tenant |
| Migracao | Validacao dos vinculos legados antes do aceite; escopos persistidos imutaveis | Legado com funcionario ligado a role de outro tenant aborta upgrade e preserva revision anterior; saneamento permite reupgrade |
| SaaS | Cotas de empresas, funcionarios, produtos e vendas mensais no banco, serializadas por tenant | Concorrencia pela ultima vaga em cada um dos quatro recursos; importacoes recusam excedente e permitem atualizar existente |
| Trial | Calendario de Sao Paulo; ultimo dia inclusivo; data ausente/expirada bloqueia; mudanca de plano/status nao reinicia trial | Casos sem data, expirado, ultimo dia e alternancia active/trial preservando vencimento |
| Perfis/permissoes | Administracao de acessos exige administrador com todas as empresas e permissao especifica; auditoria transacional inclusive em lotes | Perfil customizado com permissoes nao escala privilegios; admin limitado a empresas nao altera conta compartilhada; role+links+auditoria revertem juntos |
| Comunicacao | Hosts aprovados pelo operador, DNS publico, SMTP com TLS, webhooks HTTPS sem redirects | Bloqueio de loopback, metadata, IPv6 local, host nao aprovado, credenciais na URL, HTTP, porta indevida e redirects |
| Fora do escopo | Asaas/Focus/SEFAZ reais continuam desativados | Seletores/transporte/webhook recusam uso real; testes legados de protocolo preservados com transporte e gate explicitamente simulados |

Os cadastros compartilhados no tenant e os registros empresariais estao descritos no [guia operacional](../../02-instalacao-e-ambiente/seguranca-sprint-02.md). O teste de inventario de triggers confere todas as FKs cobertas pela protecao; os testes comportamentais exercitam casos representativos, nao todas as combinacoes de todos os campos.

## Execucao final

Projeto Compose exclusivo `oceanblue-s02`, PostgreSQL em tmpfs, rede interna e nenhuma porta publicada. Imagens construidas com locks e hashes. O banco foi recriado antes do pipeline completo; a imagem de teste foi executada sem bind mount, evitando alteracoes durante os testes.

| Gate | Resultado |
|---|---|
| Dependencias prod/dev | Instalacao com hashes e `pip check` aprovados; adicionados cryptography 50.0.1, cffi 2.1.1 e pycparser 3.0 |
| Inventario | 146 rotas; arquivo atualizado e `--check` aprovado |
| Historico | 21 revisions, upgrade/downgrade base/reupgrade e sentinela preservada |
| Schema | 45 tabelas; colunas, tipos, indices e FKs iguais aos modelos |
| Pytest/JUnit | 141 testes; 0 falhas; 0 erros; 0 skips; 134,028 segundos |
| Cobertura | 6.370/10.372 linhas; 882/2.242 ramos; combinado 7.252/12.614 = 57,49%; gate de 50% preservado |
| Imagem produtiva | Default production; quatro variaveis obrigatorias ausentes recusadas antes da conexao ao banco |
| Smoke | Entrypoint, migrations, Gunicorn, usuario nao root e /api/health + /api/ready com HTTP 200/JSON valido |
| JavaScript | Verificacao de sintaxe dos dois arquivos alterados aprovada |
| Git | Diff sem erros de whitespace |
| Limpeza | Containers e rede do projeto de teste removidos; nenhum banco externo acessado |

Imagens verificadas: teste `sha256:1145c6385a9c243581d02f481fcd1bac8500bc9da724024e06405545dfb9cc12`; producao `sha256:ab093b338f7eb38505f0554b28621364bcc5427ceb1f3d7dc860a9b179bc1039`.

Durante a iteracao, foram corrigidos: lock de dependencias sem os pacotes considerados unsafe pelo pip-tools; helpers removidos inadvertidamente ao restringir os providers; e contexto global do fixture de migrations que mantinha uma transacao aberta apos testes CLI, bloqueando a limpeza. Uma execucao intermediaria com bind mount tambem observou arquivos em alteracao durante subprocessos de startup. Esses resultados nao foram usados como aceite. Depois das correcoes, uma suite de 123 testes passou; a execucao final, em imagem imutavel e banco novo, aprovou todos os 141 casos.

## Evidencias

- [Pipeline, migrations, inventario e suite](sprint-02/pipeline.txt)
- [JUnit final](sprint-02/junit.xml)
- [Cobertura final](sprint-02/coverage.xml)
- [Gate da imagem produtiva](sprint-02/image.txt)
- [Smoke HTTP/configuracao/usuario](sprint-02/smoke.txt)
- [Inicializacao produtiva](sprint-02/smoke-startup.txt)
- [Limpeza](sprint-02/cleanup.txt)
- [SHA-256 dos artefatos](sprint-02/sha256sums.txt)

## Reproducao

Em checkout limpo, com Docker Linux e shell POSIX (Git Bash no Windows):

```sh
docker compose -p oceanblue-s02-validation -f compose.test.yml build test smoke
sh scripts/validate_image.sh oceanblue-s02-validation-smoke
docker compose -p oceanblue-s02-validation -f compose.test.yml up --abort-on-container-exit --exit-code-from test
docker compose -p oceanblue-s02-validation -f compose.test.yml cp test:/tmp/junit.xml junit.xml
docker compose -p oceanblue-s02-validation -f compose.test.yml cp test:/app/coverage.xml coverage.xml
docker compose -p oceanblue-s02-validation -f compose.test.yml --profile smoke up -d --wait --wait-timeout 120 smoke
docker compose -p oceanblue-s02-validation -f compose.test.yml --profile smoke exec -T smoke python -m scripts.validate_smoke
docker compose -p oceanblue-s02-validation -f compose.test.yml --profile smoke down -v
```

## Limites operacionais

O ambiente produtivo real nao foi atualizado. A implantacao exige as novas migrations, novo login para usuarios, rotacao dos campos legados, configuracao de hosts de comunicacao e revisao da topologia de proxy, conforme o guia. A migration e a rotacao podem bloquear registros: dimensionar a janela com o volume real. Chaves de backups devem ser preservadas segundo a politica operacional.

O isolamento de leitura centralizado cobre consultas ORM; SQL bruto novo exige revisao explicita de escopo. Os triggers verificam integridade de vinculos, nao substituem autorizacao de leitura no banco. A lista de hosts deve conter apenas provedores confiaveis controlados pelo operador.

Nao foram executados carga produtiva, pentest externo, homologacao visual integral, backup/restore produtivo, pipeline remoto da Sprint 2 ou validacao independente. Nao houve reducao do gate de cobertura, testes desabilitados ou avance em boleto/fiscal reais.
