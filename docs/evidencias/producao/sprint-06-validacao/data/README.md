# Sprint 06 — validação adversarial de dados

Base: `804256ae6edafb4a2db99dcdb39ddacb987f9148`.

Execução em containers exclusivos `oceanblue-s06-data-*`, imagem local
`oceanblue-s06-complete-test`, PostgreSQL 16 exclusivo em rede interna,
sem portas publicadas, sem integrações externas e sem commits.

## Reprodução inicial

`before.xml` e `before.txt`: **19 falhas, 68 aprovados**, 91,60 s.
O teste novo e o controller original foram montados sobre a imagem local.
Os demais módulos vieram da imagem, sem incluir alterações simultâneas dos
outros agentes.

| Defeito reproduzido | Antes | Correção / responsável |
| --- | --- | --- |
| `empresa_id=` e parâmetros duplicados (`empresa_id=1&empresa_id=3`, `limit=1&limit=100`, `before=20&before=1`) | Filtro vazio ampliava a consulta; duplicatas usavam silenciosamente o primeiro valor | Controller rejeita parâmetros vazios, duplicados e valores não inteiros ASCII com HTTP 400 |
| `limit=1_0`, empresa negativa, zero ou acima de `2147483647` | Formatos e limites inconsistentes: resposta 200/403 | Mesma validação explícita, limitada a dez caracteres antes da conversão |
| Registro `id=2147483647` na primeira página | Nunca retornava, pois o cursor padrão era usado como limite exclusivo | Filtro por cursor aplicado somente quando o cliente envia `before` |
| Factories de boleto/fiscal chamadas fora de testes com flags desligadas ou adulteradas | Retornavam providers mock, permitindo simulação fora do ambiente de testes apesar do bloqueio HTTP | Factories exigem ambiente de testes e a flag do módulo exatamente `True` |
| Probe com escrita zero, parcial ou bytes corrompidos retornando tamanho correto | Probe reportava sucesso | Security corrigiu tamanho da escrita; após autorização do coordenador, data acrescentou readback e comparação integral do sentinela após fsync |

As falhas de parsing são de contrato e previsibilidade; os ataques executados
não demonstraram vazamento entre tenants. O bloqueio de integrações reais já
impedia rede e decriptação de credenciais, independentemente da falha das factories.

## Cobertura adversarial

- Tenant por cookie, query string e headers; assinatura JWT adulterada; usuário
  anônimo, dono da plataforma e permissão desativada após login.
- Revogação de vínculo empresarial entre páginas, escopo vazio, empresa inativa,
  eventos globais, empresas de outro tenant e projeção sem detalhes privados.
- Cursor exclusivo, inserção concorrente entre páginas, ausência de repetição,
  fim da lista, maior ID inteiro, números enormes, sinal, espaços, Unicode e NUL.
- Tentativas HTTP POST/PUT/PATCH/DELETE e UPDATE/DELETE/TRUNCATE SQL sob a role
  runtime real, com verificação de SQLSTATE `42501` e preservação do registro.
- Storage relativo, traversal, raiz ausente/arquivo, symlinks na raiz e no pai,
  colisões com symlinks/hardlinks sem alteração do alvo, erros EROFS/EACCES/ENOSPC/EIO,
  diretório sem permissão de escrita sob usuário não root, limpeza e recuperação.
- Corrupção de bytes e bytes excedentes com retorno de escrita aparentemente correto;
  erros de seek/leitura falham fechados e removem o probe.
- Readiness e mutações com disco cheio respondem 503, enquanto liveness permanece 200.
- Flags de produção não canônicas, factories em produção e flags inválidas em testes,
  bloqueio de providers reais antes da rede/segredos e downloads SSRF/file/traversal.

## Execução e isolamento

Imagem de testes: `sha256:0e93bf35b7a44c0525d1ae30c9d0b2cf137e0739efe7ad1ddbf36ebccc480429`.
PostgreSQL: `sha256:23af655ba1ddf74eaa002e3deaf5fce022ab8791672336a7c1fb0ef2d57efb7f`.

Banco `oceanblue_test` em tmpfs, containers `oceanblue-s06-data-db` e
`oceanblue-s06-data-db-final`, rede interna
`oceanblue-s06-data-net`. Nenhum Docker de outro agente foi alterado.
O fixture existente migra e limpa somente esse banco exclusivo.

Comando dentro da imagem para reprodução:

```text
python -u -m pytest tests/test_sprint06_data_adversarial.py -o addopts= --junitxml=/evidence/after.xml -q
```

`-o addopts=` desabilita apenas o gate global de cobertura nessa execução focal;
nenhum teste é marcado como skip/xfail. A regressão geral continua sendo uma
execução separada coordenada pelo responsável pela integração.

## Retestes

| Artefato | Resultado | Código exercitado |
| --- | --- | --- |
| `after.xml`, `after.txt` | 92 aprovados, 3 falhas, 77,48 s | Controller e providers corrigidos; storage original da imagem. Só escrita zero/parcial/corrompida ainda falhava |
| `regression.xml`, `regression.txt` | 123 aprovados, 1 falha, 119,73 s | Data + operações Sprint06 + boleto + bloqueio real Sprint02, com correção de escrita parcial de security. Só corrupção silenciosa ainda falhava |
| `final.xml`, `final.txt` | **176 aprovados, 0 falhas, 0 erros, 0 skips; 117,51 s** | Versão final de data e readback, testes adversariais security e regressões existentes |
| `readonly-mount.txt` | PASS, EROFS real, uid 1000 | Versão final em container sem rede, root filesystem somente leitura e bind mount somente leitura |
| `full-tmpfs.txt` | PASS, ENOSPC real e recuperação | Versão final em tmpfs exclusivo de 64 KiB, preenchido integralmente; sem probe residual; sucesso após liberar espaço |

O readback usa o mesmo descritor aberto com `O_RDWR`, faz seek ao início e lê
`len(sentinela) + 1`, rejeitando conteúdo diferente, truncamento e bytes extras.
Mantém criação exclusiva, proteção contra symlink, modo 0600, fsync e limpeza.
Não pretende atestar integridade de todos os documentos históricos do storage.

`final-source-hashes.json` registra SHA-256 dos oito arquivos montados na
execução final. O código de security em headers/proxy foi montado para exercitar
os testes daquele agente, sem edição por data. Além do módulo de testes novo,
as alterações deste lote são o controller de auditoria, os dois providers e
somente o readback em `operations.py`, autorizado posteriormente pelo coordenador.

Composição da execução final: **98 casos data**, **49 casos security** e
**29 casos existentes** (operações Sprint06, boleto e bloqueio de integrações Sprint02).

```text
python -u -m pytest tests/test_sprint06_data_adversarial.py tests/test_sprint06_security_adversarial.py tests/test_sprint06_operations.py tests/test_boleto_service.py tests/test_sprint02_security.py::test_real_integrations_and_webhook_stay_disabled -o addopts= --junitxml=/evidence/final.xml -q
```

`final-source-check.txt`: os oito arquivos preservaram seus hashes durante a
execução final. App/testes deste lote congelados para build. Nenhuma integração
externa executada e nenhum commit criado. `cleanup.txt` registra a remoção
exclusiva dos containers e da rede deste lote.

## Complemento final: restauração incompleta

Após a execução de 176 casos, o coordenador acrescentou o contrato do snapshot:
`root.parent/.oceanblue-restore-incomplete` deve impedir o uso do storage.
Foram escritos **oito casos antes da correção**, cobrindo marcador como arquivo,
diretório, symlink válido e symlink quebrado, tanto no probe quanto no HTTP.

- `marker-before.xml` / `marker-before.txt`: **8 falhas, 98 desmarcados; 15,96 s**.
  O probe aceitava o storage e readiness retornava 200 com restore incompleto.
- Correção: `storage_probe` rejeita marcador existente ou symlink, inclusive
  quebrado, com `OSError` antes de criar/abrir qualquer arquivo de probe.
- `marker-after.xml` / `marker-after.txt`: **8 aprovados, 98 desmarcados; 6,96 s**.
  Marcador bloqueia readiness e POST/PUT/PATCH/DELETE com 503, impede execução
  da mutação, mantém liveness 200 e não deixa probes. Após remoção, readiness e
  todas as mutações retornam 200 sem reiniciar a aplicação.
- `marker-regression.xml` / `marker-regression.txt`: **79 aprovados, 101
  desmarcados; 17,02 s**, sem falhas, erros ou skips. Exercita todos os casos de
  storage em data/operações e os 49 casos adversariais completos de security.

```text
python -u -m pytest tests/test_sprint06_data_adversarial.py tests/test_sprint06_security_adversarial.py tests/test_sprint06_operations.py -k "storage or test_sprint06_security_adversarial" -o addopts= --junitxml=/evidence/marker-regression.xml -q
```

O arquivo data agora contém **106 casos**. A execução de 176 casos documentada
acima precede este complemento; a seleção de 79 é a regressão específica após
a última alteração. As regressões integrais ficam com o coordenador.

`marker-source-hashes.json` e `marker-source-check.txt` identificam e conferem
os oito arquivos montados no estado **definitivo para o build**, substituindo
o congelamento anterior. Nenhum arquivo app/testes foi alterado após esses hashes.
Containers exclusivos `oceanblue-s06-data-marker-*`, rede interna e PostgreSQL
em tmpfs foram usados; `marker-cleanup.txt` registra a remoção dos recursos.
