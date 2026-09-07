# Checklist do candidato 2.1.0-rc.1

Este checklist substitui as orientações anteriores de habilitação Asaas/Focus. Emissão real
de boleto e Nota Fiscal está fora do candidato; blueprints, links e adaptadores ficam bloqueados.
WhatsApp/SMTP e demais transportes externos não são acionados na homologação nem liberados
pela instalação deste pacote. O código e testes legados permanecem preservados.

## Aceite do pacote

- [ ] Conferir GO da Sprint 6 e CI remoto do commit `7b0c97f`.
- [ ] Executar `scripts/validate_release_candidate.ps1` com projeto e diretório de evidências novos.
- [ ] Exigir regressão e reteste integrais com PostgreSQL real, zero falhas/erros/skips,
  preservação dos 758 casos anteriores e cobertura combinada não inferior à medição da Sprint 6.
- [ ] Conferir jornadas E2E, acessibilidade automatizada, viewports e motores realmente executados.
- [ ] Exigir gates de isolamento tenant/empresa, concorrência, idempotência e saldo/ledger.
- [ ] Conferir scans com data/ferramenta/escopo; revisar exceções e licenças sem tratar SBOM como parecer jurídico.
- [ ] Conferir manifesto SHA-256 das evidências, fontes, arquivo de distribuição e IDs de imagem.
- [ ] Revisar defeitos e limites da Sprint 7. NO-GO se qualquer gate obrigatório falhar ou não tiver prova.

## Instalação operacional

- [ ] Definir responsável, domínio, capacidade, manutenção, suporte, RPO/RTO e aceite por empresa.
- [ ] Usar exclusivamente `compose.production.yml`; fixar imagens aprovadas por digest.
- [ ] Executar scan de SO, CPython e bibliotecas nativas e resolver bloqueadores da instalação;
  os scans Python/npm deste candidato não cobrem essas camadas, e o Scout exigiu autenticação.
- [ ] Criar segredos privados independentes e chave de campos persistente, preservando chaves históricas.
- [ ] Criar roles de migration/runtime separados e aplicar `infra/production/runtime_grants.sql`.
- [ ] Preparar volumes persistentes, UID 1000 e storage 0700; validar espaço/alertas.
- [ ] Instalar certificado TLS válido, conferir hostname/expiração e redes/IP do proxy confiável.
- [ ] Manter as três flags `FEATURE_BOLETO`, `FEATURE_FISCAL`, `FEATURE_EXTERNAL_PROVIDERS` em `false`.
- [ ] Validar Compose com `config --quiet`, sem imprimir segredos resolvidos.
- [ ] Instalar backup externo criptografado/imutável com agendamento, retenção e custódia separada de chaves/hashes.
- [ ] Instalar coleta de logs/métricas e canal de alertas; provar disparo, resolução e ausência de séries.
- [ ] Medir carga e restauração com volume real. As medições sintéticas não definem SLA.

## Deploy e recuperação

- [ ] Registrar versão/digest/revision atual e candidato; parar proxy, aplicação, jobs e demais escritores.
- [ ] Capturar backup consistente banco+arquivos e preservar SHA-256 do manifesto em custódia independente.
- [ ] Executar upgrade uma vez com role proprietário; aplicar grants; não permitir DDL ao runtime.
- [ ] Iniciar candidato readonly/nonroot/capabilities removidas, `RUN_MIGRATIONS=false`.
- [ ] Exigir health/readiness, TLS, login, transação sintética autorizada, auditoria e métricas antes do tráfego.
- [ ] Em falha, parar escritores e preservar estado; validar imagem anterior em cópia restaurada antes da troca.
- [ ] Para restore usar banco/volume vazios, digest confiável obrigatório e comparação de tabelas/sequências/arquivos.
- [ ] Não remover marcador de restore incompleto para forçar readiness. Reconciliar ou usar destino novo.
- [ ] Não executar downgrade base em produção; downgrade que perde request IDs deve continuar recusado.
- [ ] Reconciliar escritas posteriores ao snapshot antes de liberar tráfego; registrar perdas/decisões explicitamente.

Detalhes e comandos: [runbook de produção](../02-instalacao-e-ambiente/producao-sprint-06.md).
O GO local de candidato não preenche automaticamente os itens de instalação acima.
