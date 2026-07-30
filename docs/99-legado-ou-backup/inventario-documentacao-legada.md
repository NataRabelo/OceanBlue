# Inventario da documentacao legada

## Politica aplicada nesta Sprint 1

Nenhum documento legado foi apagado. Antes da reorganizacao, os arquivos `.md` existentes em `docs/` foram copiados para `docs/99-legado-ou-backup/`.

## Arquivos inventariados

| Arquivo legado | Conteudo identificado | Avaliacao | Destino recomendado |
| --- | --- | --- | --- |
| `analise_modulo_financeiro_boletos.md` | Analise ampla do modulo financeiro e planejamento de boletos, parcelamento e juros/multa. | Util, mas parcialmente superado pela implementacao parcial encontrada. | Preservar como referencia historica e substituir por `docs/06-financeiro-boletos/diagnostico-boletos.md` para o estado atual. |
| `arquitetura_deploy_vps.md` | Documento extenso de deploy VPS, Docker, banco, backups, rede e endpoints. | Muito util para producao/deploy. | Preservar e futuramente quebrar em documentos menores de arquitetura/ambiente/operacao. |
| `documentacao_tecnica.md` | Visao tecnica geral, stack, estrutura, multi-tenant e seguranca. | Util, mas desatualizada em relacao aos novos modulos fiscal/boleto. | Substituir pela nova base em `docs/00-visao-geral`, `docs/01-arquitetura` e `docs/03-banco-de-dados`. |
| `manual_clientes_cashback_mensageria.md` | Manual funcional de clientes, cashback e mensageria. | Util e especifico. | Preservar; incorporar futuramente em `docs/04-modulos-e-funcionalidades` ou `docs/05-fluxos-operacionais`. |
| `manual_uso.md` | Manual de uso operacional do sistema. | Util para usuarios, mas provavelmente incompleto frente aos modulos mais novos. | Preservar e revisar em sprint futura. |
| `plano_saas_comercial.md` | Posicionamento comercial e planos SaaS. | Util para estrategia/produto. | Preservar; mover futuramente para area de produto/comercial se desejado. |

## Decisoes

- Preservar todos os documentos legados.
- Usar a nova estrutura `docs/` como fonte principal para evolucao tecnica.
- Manter documentos legados apenas como referencia historica ate revisao manual.
- Nao apagar nem sobrescrever conteudo antigo sem autorizacao explicita do dono do sistema.
