# Resumo executivo - Sprint 3

## O que foi implementado

- Separacao entre status interno e status oficial/externo para boletos e NFC-e.
- Camada provider para boleto e fiscal.
- Provider bancario mockado para registro em homologacao, PDF/HTML e retorno idempotente.
- Provider fiscal mockado para NFC-e em homologacao, protocolo, XML assinado/autorizado e DANFE HTML.
- Endpoints de registro/retorno de boleto e download de DANFE.
- Migration de Sprint 3.
- Telas com status interno e externo separados.
- Testes automatizados adicionais.

## O que ficou homologado

Fluxos internos de homologacao/mock: registro de boleto, baixa idempotente por retorno, envio NFC-e, persistencia de protocolo, XML autorizado e DANFE.

## Dependencias externas

Ainda dependem de credenciais, certificado, banco, SEFAZ ou integrador: API bancaria real, PDF oficial, webhook assinado, CNAB, assinatura digital real, autorizacao SEFAZ real, DANFE oficial do integrador, cancelamento, inutilizacao e contingencia.

## Resultado dos testes

- Antes: `python -m pytest` -> 49 passed, 10 warnings.
- Depois: `python -m pytest` -> 50 passed, 10 warnings.

## Arquivos principais criados ou alterados

- `app/models/db.py`
- `app/services/boleto_service.py`
- `app/services/boleto_provider.py`
- `app/services/fiscal_service.py`
- `app/services/fiscal_provider.py`
- `app/controllers/boleto_controller.py`
- `app/controllers/fiscal_controller.py`
- `app/templates/modulos/financeiro/boletos.html`
- `app/static/js/modulos/boletos.js`
- `app/templates/modulos/fiscal/fiscal.html`
- `app/static/js/modulos/fiscal.js`
- `migrations/versions/1a2b3c4d5e6f_add_sprint3_boleto_fiscal_external_status.py`
- `tests/test_boleto_service.py`
- `tests/test_fluxo_pdv_financeiro.py`

## Como operar boleto

Criar boleto, acionar registro em homologacao, conferir status bancario/protocolo/arquivos e processar retorno com `event_id` unico para baixa idempotente.

## Como operar nota fiscal

Configurar empresa fiscal, prevalidar venda, enviar NFC-e em homologacao, conferir status oficial autorizado, protocolo, XML e DANFE.

## Riscos e pendencias para producao

Substituir providers mockados por providers reais, validar certificados/credenciais, formalizar storage seguro, implementar assinatura/verificacao de webhooks, cancelamento, inutilizacao, contingencia e regras fiscais completas por UF/regime.

## Proximos passos recomendados

Escolher banco e integrador fiscal, obter credenciais de homologacao, mapear contratos reais de API, executar homologacao assistida com contador/banco/integrador e ampliar testes de erro de comunicacao, duplicidade externa e permissao por tenant.
