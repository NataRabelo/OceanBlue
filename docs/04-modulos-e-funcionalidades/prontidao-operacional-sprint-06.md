# Matriz de prontidão operacional — Sprint 6

Base obrigatória: `ed7112154a3e94186b17fbfc0717fb59684432bc`, GO independente da Sprint 5.
As evidências históricas das Sprints 1–5 permanecem preservadas. O inventário gerado passa
a 165 rotas; vínculo estático com serviços não substitui os testes HTTP listados nesta matriz.

| Requisito | Implementação | Prova executável / critério |
|---|---|---|
| Persistência | Volume de banco e volume instance, imagem somente leitura, UID 1000, umask 077 | `validate_operational_proof.ps1`: arquivo sintético atravessa backup, restore e reinício; fonte não gravável |
| Storage indisponível | Sonda de criação exclusiva, fsync e remoção; escrita HTTP fecha antes do controlador | `validate_storage_outage.py`: chmod real, health 200, readiness/escrita 503, recuperação 200 |
| Processo / dependências | Aliases health/readiness, conexão, revision e storage | `test_sprint06_operations.py`, smoke e parada real do PostgreSQL |
| Configuração oficial | Compose produtivo, proxy TLS e credenciais de runtime separadas | Configuração Compose e prova nginx real; `test_runtime_database_role_cannot_ddl_truncate_or_erase_audit` |
| TLS / proxy | Origem do transporte restrita, um salto, cabeçalhos substituídos, sem confiança em Host encaminhado | `validate_https_proof.py`: certificado validado; proxy 200, acesso direto forjado 403 |
| Flags | Três flags explícitas false; startup recusa true/valor desconhecido; rotas e UI bloqueadas | Startup, UI autenticada e lookup de forma de pagamento; integrações reais incondicionalmente bloqueadas |
| Logs | JSON com request ID, template de rota, duração e status; conteúdo privado omitido | `test_request_id_redaction_and_metrics`, logs reais de nginx/Gunicorn no runner |
| Métricas / alertas | Contadores locais ao worker, duração, espaço livre e uptime; listener privado TLS com Bearer | HTTP de métricas com token e recusa sem token; regras versionadas em `alerts.yml` |
| Auditoria consultável | Permissão `visualizar_auditoria`, tenant e empresas autorizadas; projeção sem detalhes privados | Paginação, empresa externa, eventos globais, revogação de permissão, request ID e recusa de perda no downgrade |
| Performance | Cursor descendente, máximo 100 linhas, índice composto; nenhum lazy-load de entidades na projeção | 10.000 eventos, 50 resultados, máximo 30 consultas e menos de 2 s; EXPLAIN ANALYZE exige acesso por índice |
| Assets / acessibilidade | CSS/ícones locais, CSP sem CDN, nomes acessíveis, regiões roláveis focáveis, foco visível | Axe WCAG A/AA em cinco telas, viewport 390×844, sem requisições externas e sem overflow horizontal |
| Fluxo móvel | Remoção do bloqueio para largura inferior a 768px | Venda, resposta perdida, replay idempotente, cancelamento parcial/integral e reimpressão no Chromium móvel |
| Backup | pg_dump custom + árvore instance; aplicação parada, zero outros clientes, manifestos | Snapshot com três vendas, três lançamentos e arquivo; contagens/hashes/sequências conferidos |
| Restore | PostgreSQL novo, storage vazio, hashes antes de gravar, transação única, permissões restauradas | Restore efetivo; corrupção e banco preenchido recusados; smoke e falha de storage após restore |
| Rollback de aplicação | Digest anterior fixado, startup direto sem migrations antigas | Aplicação da Sprint 5 roda contra cópia restaurada; três vendas e lançamentos preservados |
| Rollback de migration | Volta protegida da revision nova; recusa com request_id persistido | Histórico completo em banco vazio; downgrade/reupgrade com três vendas; recusa transacional quando há rastreabilidade |
| Runbooks / retenção | Instalação, deploy, manutenção, incidente, backup, restore, rollback e políticas | `../02-instalacao-e-ambiente/producao-sprint-06.md`; logs Docker limitados; nenhum expurgo silencioso |

Limites: prova local em Linux/Chromium; regras de alerta não representam coletor ou canal de
notificação implantado. Benchmark de auditoria é uma amostra controlada, não teste de carga
produtiva. Axe não substitui uso manual de leitor de tela nem cobre todos os estados de todos
os modais. Backups de produção exigem custódia privada, criptografia, agendamento e retenção
ratificados pelo operador. O caos independente da Sprint 6 pertence à tarefa seguinte.
