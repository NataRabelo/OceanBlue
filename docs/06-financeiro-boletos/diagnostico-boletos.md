# Diagnostico de boletos

## Estado atual

O sistema possui uma implementacao parcial de boleto. A base tecnica existe, mas ainda nao caracteriza emissao bancaria real.

## O que existe

- `app/models/db.py`: entidades `BancoEmissor`, `ConfiguracaoParcelamento`, `RegraJurosMulta`, `Boleto`, `ParcelaBoleto` e `EventoBoleto`.
- `migrations/versions/f9d0e1a2b3c4_add_boleto_financeiro_models.py`: migration de modelos de boleto.
- `app/controllers/boleto_controller.py`: endpoints sob `/api/financeiro/boletos`.
- `app/services/boleto_service.py`: criacao, listagem, baixa e recalculo de juros/multa.
- `app/services/banco_emissor_service.py`: cadastro de banco emissor, parcelamento e regras.
- `app/repositorys/boleto_repository.py`: consultas e persistencia.
- `tests/test_boleto_service.py`: testes basicos de calculo.

## Endpoints encontrados

- `GET /api/financeiro/boletos`
- `POST /api/financeiro/boletos`
- `GET /api/financeiro/boletos/<id>`
- `POST /api/financeiro/boletos/<id>/baixar`
- `POST /api/financeiro/boletos/<id>/recalcular-juros`
- `GET/POST /api/financeiro/boletos/bancos-emissores`
- `GET/POST /api/financeiro/boletos/configuracoes-parcelamento`
- `GET/POST /api/financeiro/boletos/regras-juros-multa`

## Lacunas

- Nao ha integrador bancario real identificado.
- Nao ha geracao automatica confiavel de linha digitavel/codigo de barras.
- Nao ha remessa CNAB gerada.
- Nao ha processamento de retorno CNAB.
- Nao ha webhook bancario.
- Nao ha download/geracao real de boleto PDF.
- Nao ha tela propria de gestao de boletos claramente identificada.
- Baixa cria lancamento financeiro, mas precisa validacao mais ampla com parcelas, baixas parciais e conciliacao.

## Riscos

- O status `EMITIDO` pode ser usado sem registro efetivo em banco emissor.
- Juros/multa podem ser recalculados cumulativamente se nao houver controle de idempotencia.
- Dados sensiveis bancarios podem precisar de criptografia e mascaramento.
- A permissao usada esta acoplada a `criar_lancamento_financeiro`; pode ser necessario criar permissoes especificas de boleto.

## Recomendacao para Sprint 2

Antes de implementar emissao, escolher a estrategia: API bancaria/integrador, CNAB ou biblioteca de boleto. Definir banco alvo, ambiente homologacao, campos obrigatorios, layout, fluxo de status, PDF, remessa/retorno, conciliacao e tela operacional.
