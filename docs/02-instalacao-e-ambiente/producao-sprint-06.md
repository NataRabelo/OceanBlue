# Operação de produção — Sprint 6

Este pacote prepara instalação em um único host Docker Linux. O aceite é local: nenhum deploy,
push, provedor bancário/fiscal ou envio externo foi autorizado ou executado. Use o relatório
`../evidencias/producao/sprint-06-execucao.md` para resultados e limites da medição.

## Instalação e configuração oficial

Use `compose.production.yml` e `infra/production/nginx.conf`. Os composes antigos são de
desenvolvimento; não representam a topologia endurecida. Fixe `OCEANBLUE_IMAGE` e
`OCEANBLUE_PROXY_IMAGE` por digest aprovado. As versões resolvidas dos pacotes Python estão
nos locks com hashes; os assets de UI são locais e versionados. Reconstrua imagens em ambiente
de build separado; não instale dependências durante o início do serviço.

Crie `OCEANBLUE_ENV_FILE` fora do checkout, legível somente pelo operador, contendo as variáveis
de `.env.example`. Gere três segredos aleatórios distintos de pelo menos 32 caracteres, mais um
`METRICS_TOKEN` independente. `FIELD_ENCRYPTION_KEYS` preserva as chaves necessárias aos dados
e backups históricos. Nunca coloque segredos, URLs completas de banco, dumps ou certificados
privados reais no Git, nos logs, em tickets ou argumentos de terminal compartilhado.

Defina `OCEANBLUE_DATABASE_PASSWORD_FILE` com a senha do proprietário do banco e
`OCEANBLUE_TLS_DIRECTORY` com `fullchain.pem` e `privkey.pem`. O usuário 101 do proxy precisa
ler a chave; não conceda leitura global. O certificado deve corresponder ao domínio instalado.
Certificados de dois dias da prova descartável não servem para produção.

O banco usa volume `database`; a aplicação usa volume `files`, montado em `/app/instance`.
O diretório `/app/instance/storage` deve existir, pertencer a UID/GID 1000 e ter modo 0700.
Os arquivos novos usam umask 077. Nenhuma porta de banco, aplicação ou métricas é publicada.
Apenas 443 do proxy é publicado. A rede interna usa 172.30.61.0/24, com alocação dinâmica
na metade superior; o proxy ocupa 172.30.61.2. Se houver conflito de subrede, altere a rede
e `TRUSTED_PROXY_NETWORKS` juntos e repita a prova de cabeçalhos forjados.

Crie `oceanblue_runtime` com LOGIN, NOSUPERUSER, NOCREATEDB, NOCREATEROLE e senha privada pelo
canal administrativo do PostgreSQL. Use `oceanblue_owner` apenas para migrations. Depois do
upgrade, aplique `infra/production/runtime_grants.sql` como proprietário e configure DATABASE_URL
da aplicação com a credencial de runtime. Os testes verificam leitura e inclusão de auditoria,
recusando DDL, TRUNCATE, alteração de revision e exclusão de auditoria pelo papel restrito.
O dump não inclui papéis globais nem senhas: mantenha configuração de papéis e cofre de chaves
separados, recrie-os e reaplique grants após restore.

Valide a configuração sem imprimir os valores resolvidos:

```powershell
docker compose -f compose.production.yml config --quiet
docker build -t oceanblue-approved .
```

## Deploy e migrations

1. Registre digest atual, digest candidato, revision, chave ativa, janela e responsável.
2. Coloque o proxy em manutenção e pare aplicação, workers e demais escritores. Verifique
   ausência de conexões concorrentes. Mantenha a instância antiga e seus volumes preservados.
3. Execute backup de banco e arquivos. A ferramenta recusa aplicação ativa, outros clientes,
   sobrescrita de backup e containers fora do projeto indicado.
4. Com a credencial de proprietário, execute `flask db upgrade` uma única vez em container
   administrativo da imagem candidata. Nunca dê DDL ao processo HTTP.
5. Reaplique grants. Inicie a aplicação com `RUN_MIGRATIONS=false`, imagem somente leitura,
   UID 1000, todas as capabilities removidas e `no-new-privileges`.
6. Exija readiness 200, login, leitura e transação sintética autorizada, auditoria e métricas.
   Libere o proxy somente depois desses gates. Se falharem, execute o rollback descrito abaixo.

`/health` e `/api/health` verificam apenas o processo. `/readiness` e `/api/ready` verificam
conexão PostgreSQL, revision esperada e criação/fsync/remoção de arquivo sentinela no storage.
Banco indisponível, schema atrasado ou storage sem escrita retornam 503 no readiness. Falha de
storage bloqueia POST/PUT/PATCH/DELETE antes do controlador. A sonda não prova durabilidade
do equipamento, replicação, espaço futuro, todos os registros nem restauração de um backup.

## HTTPS, flags e arquivos

`FORCE_HTTPS` aceita apenas `true` em produção. A aplicação só confia em um salto de proxy
cujo IP de conexão pertença à lista explícita; X-Forwarded-Host não é aplicado. O nginx substitui
X-Forwarded-For, X-Forwarded-Proto e X-Request-ID. Cabeçalhos enviados diretamente pelo cliente
não liberam HTTP. A exceção de HTTP loopback limita-se às sondas internas de saúde.

`FEATURE_BOLETO`, `FEATURE_FISCAL` e `FEATURE_EXTERNAL_PROVIDERS` são explicitamente `false`.
Valores diferentes recusam startup produtivo. Boleto/Fiscal ficam ocultos e todas as rotas desses
blueprints retornam 404 antes da autenticação. Boleto também é removido das formas de pagamento
disponíveis no PDV e recusado pelo lookup de IDs. Adaptadores bancário/fiscal reais continuam
incondicionalmente bloqueados; os transportes de comunicação e a validação de destinos também
bloqueiam produção. A habilitação futura exige outra entrega e homologação; não há switch
operacional que autorize emissão real nesta versão. Testes usam simuladores em ambiente isolado.

Arquivos fiscais/bancários legados não são criados em produção enquanto os módulos estão
bloqueados. O backup cobre toda a árvore `instance`, incluindo caminhos históricos. Não exponha
esse volume como diretório estático do proxy. Exportações de relatórios são respostas autenticadas
em memória. CSP permite somente assets locais; o `unsafe-inline` legado permanece por scripts
de templates e está registrado como dívida de endurecimento, sem liberar CDN ou conexão externa.

## Backup e restore

Meta operacional inicial: backup diário e antes de cada migration; RPO de até 24 horas somente
quando o agendamento externo estiver instalado e monitorado. RTO deve ser medido com o volume
real; a prova pequena não define SLA produtivo. Para consistência banco/arquivos, mantenha todos
os escritores parados durante a captura e verificação. Não copie diretório físico do PostgreSQL
em execução; o script usa pg_dump custom, e restaura com pg_restore transacional e exit-on-error.

```powershell
pwsh -File scripts/operational_snapshot.ps1 -Mode backup -Project oceanblue-production -DatabaseContainer oceanblue-production-db-1 -ApplicationContainer oceanblue-production-app-1 -Database oceanblue -DatabaseUser oceanblue_owner -Directory D:/Backups/OceanBlue/2026-09-07
```

O destino deve ser novo. A ferramenta restringe ACL no Windows ou modo do diretório em Linux,
compara contagens e hashes de todas as tabelas e sequências antes/depois, e calcula SHA-256 de
dump e arquivos. Preserve `manifest.json` e o SHA-256 do manifesto em registro separado e confiável.
Hashes detectam alteração acidental; um atacante com acesso de escrita ao backup e manifesto
pode substituir ambos. Utilize armazenamento externo criptografado e imutável, conta separada
e custódia de chaves. A ferramenta não instala criptografia, imutabilidade nem cópia externa.

Para restaurar, crie outro projeto com PostgreSQL vazio e aplicação parada com volume vazio:

```powershell
pwsh -File scripts/operational_snapshot.ps1 -Mode restore -Project oceanblue-recovery -DatabaseContainer oceanblue-recovery-db-1 -ApplicationContainer oceanblue-recovery-app-1 -Database oceanblue -DatabaseUser oceanblue_owner -Directory D:/Backups/OceanBlue/2026-09-07
```

O script verifica todos os hashes antes de gravar, rejeita links, arquivos extras, banco preenchido
e storage preenchido. Restaura banco em uma transação, compara novamente todas as tabelas e
sequências e confere cada arquivo. Reaplica UID/GID do volume, mas não inicia a aplicação.
As pastas auxiliares `-destination-check` e `-restored-check` contêm cópias de verificação e devem
ficar na mesma área privada dos backups. Não altere nem remova essas pastas durante uma execução.
Execute smoke e validações de negócio antes de qualquer troca de tráfego. Uma falha mantém o
destino fora de serviço; preserve-o para análise e use outro destino vazio para nova tentativa.

## Rollback sem perda silenciosa

Rollback de aplicação: pare escritores, faça snapshot do estado atual e teste o digest anterior
contra uma cópia restaurada do schema atual. Execute Gunicorn diretamente, sem reaplicar migrations
antigas. Esta Sprint comprova essa compatibilidade para o digest da Sprint 5 registrado no runner,
com três vendas e seus lançamentos preservados. Não generalize para qualquer versão anterior.

Rollback de migration: a revision `a0d1e2f3a4b5` recusa downgrade quando existe request_id gravado,
pois a remoção da coluna perderia rastreabilidade. Sem esses dados, a prova descartável executa
downgrade/reupgrade mantendo vendas e totais. O histórico completo é também exercitado em banco
descartável vazio. Nunca rode downgrade base em produção.

Quando o downgrade for recusado, mantenha o serviço em manutenção e prefira correção para frente.
Se for necessária recuperação anterior, restaure o snapshot anterior em outro banco, compare o
manifesto com o estado atual e reconcilie todas as escritas posteriores. Divergência de contagens,
valores, estoque, carteira ou auditoria impede o corte. Não descarte o banco atual nem prometa
recuperar escritas posteriores ao backup sem uma fonte de replay previamente testada.

## Observabilidade, incidente e retenção

Logs de requisição são JSON com UTC, método, template da rota, status, duração e request ID.
Não incluem querystring, corpo, cookies, Authorization, URL do banco ou texto da exceção.
O proxy produz JSON equivalente sem caminho bruto. Logs de startup de Gunicorn/Alembic ainda
têm formato próprio. Retenção local do Docker é limitada a cinco arquivos de 10 MB por serviço.
No coletor, classifique logs de startup separadamente e restrinja acesso. Nenhum coletor remoto
foi instalado nesta tarefa.

O padrão oficial é um worker Gunicorn com quatro threads. Contadores de requisições, 5xx,
requisições acima de um segundo, duração acumulada, uptime e espaço livre ficam em `/metrics`.
São locais ao processo e reiniciam com ele. Não aumente workers sem implementar agregação.
O listener TLS 9443 do proxy, sem porta publicada, oferece `/metrics` com Bearer token; o listener
público retorna 404. O coletor interno deve validar o certificado e obter o token do cofre.
`infra/production/alerts.yml` define: readiness falhando por 1 min, erro acima de 1% por 5 min,
lentidão acima de 5% por 5 min e menos de 1 GiB livre por 5 min. Configure também ausência de
backup diário e teste mensal de restore no sistema de monitoramento do operador.

Em incidente, registre horário UTC e request ID, confirme health/readiness e espaço do volume,
verifique conectividade e estado do banco sem imprimir credenciais, e pare escritas quando
integridade for incerta. Preserve logs e snapshot. Não reenvie mensagens INCERTO nem edite
ledger diretamente. Resolva a causa, repita readiness, smoke e conciliação; registre responsável
e resultado antes de reabrir o serviço.

Auditoria está em `/api/auditoria/view`, exige `visualizar_auditoria` e respeita tenant/empresas
autorizadas. Usa cursor por ID, 50 eventos por página e máximo 100; não faz OFFSET crescente.
A resposta omite details, IP e User-Agent. Request IDs chegam também a inserts de triggers
via configuração transacional da sessão. Eventos globais ficam invisíveis a usuários limitados
a empresas. Permissões são relidas em cada requisição, inclusive após revogação.

Política inicial a ratificar com o responsável pelos dados: logs técnicos por 30 dias no coletor;
backups diários por 30 dias e mensais por 12 meses, mantendo pelo menos duas restaurações
verificadas. Documentos financeiros/auditoria seguem obrigação e retenção definida pela empresa;
não aplique limpeza genérica nesses dados. A anonimização operacional não apaga automaticamente
textos livres históricos, backups ou exportações anteriores. Bloqueio legal de retenção suspende
qualquer descarte. A ferramenta de snapshot não elimina backups nem aplica expurgo automático.

## Reproduzir as provas

```powershell
npm ci --ignore-scripts
node scripts/validate_workflow.cjs
pwsh -NoProfile -File scripts/validate_sprint06.ps1 -Project oceanblue-s06-repro -EvidenceDirectory docs/evidencias/producao/sprint-06-repro
pwsh -NoProfile -File scripts/validate_operational_proof.ps1 -Project oceanblue-s06-proof-repro -ImagePrefix oceanblue-s06-repro -EvidenceDirectory docs/evidencias/producao/sprint-06-proof-repro
```

Exige Docker Linux, PowerShell 7, Node 20 ou superior, imagens base/locks resolvíveis e imagem anterior fixada pelo
runner de rollback. As redes são internas e não publicam portas. Evidências contêm somente
dados e credenciais sintéticos. O segundo runner exige subrede 172.30.62.0/24 livre.

O workflow remoto chama-se `OceanBlue verification` e dispõe de 30 minutos: a regressão local
mediu 17m29s, excedendo o limite anterior de 15 minutos. A margem adicional acomoda build,
migrations e coleta sem reduzir a suíte ou o gate de cobertura. O validador YAML roda tanto no
workflow quanto no runner local; verifica timeout, suíte integral, migrations, cobertura e coleta
e limpeza incondicionais. O workflow remoto não foi disparado nesta entrega sem push/deploy.

Referências: [pg_dump PostgreSQL 16](https://www.postgresql.org/docs/16/app-pgdump.html),
[pg_restore PostgreSQL 16](https://www.postgresql.org/docs/16/app-pgrestore.html) e
[fronteira de confiança do ProxyFix](https://werkzeug.palletsprojects.com/en/stable/middleware/proxy_fix/).
