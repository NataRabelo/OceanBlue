# Resumo executivo - Sprint 4

## O que foi implementado

- Provider real Asaas para boleto, mantendo mock.
- Provider real Focus NFe para NFC-e, mantendo mock.
- Configuracao Asaas e Focus por empresa/tenant com segredos criptografados.
- Webhook Asaas idempotente e validado por token.
- Consulta de boleto e NFC-e.
- Cancelamento NFC-e autorizado via provider.
- Storage de links/arquivos retornados.
- Telas operacionais com provider, status externo, links e acoes.
- Documentacao final e checklist de producao.

## Pronto para producao

Base tecnica e migrations estao prontas para homologacao assistida e preparacao de producao por tenant.

## Ainda depende de validacao externa

Credenciais reais Asaas/Focus, URL publica HTTPS, webhook configurado no Asaas, cadastro Focus por emitente, validacao fiscal com contador, teste sandbox/homologacao e aprovacao financeira.

## Testes

- Antes: `50 passed, 10 warnings`.
- Depois: `52 passed, 12 warnings`.

## Principais arquivos

- `app/models/db.py`
- `app/services/boleto_provider.py`
- `app/services/fiscal_provider.py`
- `app/services/boleto_service.py`
- `app/services/fiscal_service.py`
- `app/controllers/boleto_controller.py`
- `app/controllers/fiscal_controller.py`
- `app/static/js/modulos/boletos.js`
- `app/static/js/modulos/fiscal.js`
- `migrations/versions/2b3c4d5e6f7a_add_sprint4_asaas_focus_real_configs.py`
- `tests/test_integracoes_sprint4.py`

## Configurar Asaas

Usar `PUT /api/financeiro/boletos/configuracao-asaas/{empresa_id}` com ambiente, token, webhook URL e token de webhook. O token e salvo criptografado e nao e exibido depois.

## Configurar Focus NFe

Na tela fiscal da empresa, selecionar `Focus NFe`, informar token homologacao/producao e CNPJ emitente. Tokens sao mascarados apos salvar.

## Go/no-go

Go para homologacao assistida. No-go para producao imediata ate concluir checklist, validar integrações reais e aprovar com contador/responsavel financeiro.

## Pendencias fora do codigo

Credenciais, certificados/cadastros externos, URLs de webhook, homologacao fiscal/financeira, backup/storage definitivo e plano de suporte pos-go-live.
