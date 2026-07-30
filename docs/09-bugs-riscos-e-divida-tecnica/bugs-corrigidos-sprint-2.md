# Bugs corrigidos e riscos tratados - Sprint 2

## Correcoes realizadas

### Recalculo cumulativo de boleto

Arquivo: `app/services/boleto_service.py`

O recalcule de juros/multa somava `total_juros + total_multa` ao `boleto.valor_restante` atual. Em chamadas repetidas para a mesma data, isso podia reaplicar o mesmo encargo no total do boleto. A correcao recompoe o total a partir da soma das parcelas recalculadas.

Teste adicionado: `tests/test_boleto_service.py::test_recalcular_juros_multa_nao_reaplica_total_de_forma_cumulativa`.

### Mensagens fiscais ambíguas

Arquivos:

- `app/services/fiscal_service.py`
- `app/controllers/fiscal_controller.py`
- `app/templates/modulos/fiscal/fiscal.html`
- `app/static/js/modulos/fiscal.js`
- `app/templates/modulos/pdv/pdv.html`
- `app/static/js/modulos/pdv.js`

Textos que poderiam sugerir autorizacao oficial foram ajustados para informar que o sistema gera XML fiscal interno e ainda nao assina nem autoriza na SEFAZ.

### Tela operacional inicial de boletos

Arquivos:

- `app/controllers/boleto_controller.py`
- `app/templates/modulos/financeiro/boletos.html`
- `app/static/js/modulos/boletos.js`
- `app/templates/modulos/financeiro/financeiro.html`
- `app/services/boleto_service.py`

Foi criada tela de listagem e filtros, com aviso operacional de que nao ha registro bancario real.

## Riscos remanescentes

- Status `EMITIDO` de boleto ainda existe no modelo atual e pode continuar confundindo integracao futura.
- Status `EMITIDA` fiscal ainda existe no enum atual, embora a UI tenha sido ajustada.
- Nao ha integracao bancaria real, CNAB, retorno, webhook ou PDF real.
- Nao ha assinatura/transmissao/autorizacao SEFAZ.
- Testes de UI ainda nao cobrem a tela de boletos.
- Warnings SQLAlchemy nos testes devem ser investigados antes de ampliar transacoes.
