# Relatorio Sprint 2

## Objetivo

Preparar o OceanBlue PDV para uma Sprint 3 segura de implementacao real de boleto e nota fiscal, sem implementar registro bancario real nem autorizacao SEFAZ.

## Analise realizada

- Validacao Git, ambiente, Docker, Gunicorn, `.env.example` e dependencias.
- Execucao de testes.
- Revisao de models, controllers, services, repositories, templates e JS de boleto/fiscal.
- Revisao de documentos da Sprint 1 e plano da Sprint 2.

## Resultado dos testes

- Suite completa inicial: 48 passed, 10 warnings.
- Teste especifico apos alteracoes: `tests/test_boleto_service.py` com 2 passed.
- Warnings: SQLAlchemy identity map em testes de fluxo PDV/financeiro.

## Correcoes e melhorias

- Corrigido risco de recalcule cumulativo de juros/multa em boleto.
- Adicionado teste para garantir idempotencia do recalcule na mesma data.
- Ajustadas mensagens fiscais no modulo fiscal e no PDV para diferenciar XML interno de autorizacao SEFAZ.
- Criada tela inicial de boletos com filtros e aviso de controle interno.
- Criados documentos tecnicos de ambiente, boleto, fiscal, UX, bugs, Sprint 2 e Sprint 3.

## Estado de boletos

Base interna pronta para evolucao, mas sem emissao bancaria real. A Sprint 3 deve separar status interno/bancario, escolher API/CNAB/integrador e implementar registro homologado com retorno/baixa idempotente.

## Estado de nota fiscal

Base interna pronta para evolucao, mas sem validade fiscal oficial. A Sprint 3 deve escolher integrador/biblioteca, separar status interno/SEFAZ e implementar assinatura/transmissao em homologacao.

## Decisoes pendentes

- Banco ou integrador de boleto.
- API bancaria, CNAB ou ambos.
- Modelo fiscal prioritario: NFC-e, NF-e ou ambos.
- UF, regime tributario e regras fiscais iniciais.
- Integrador fiscal terceiro ou implementacao direta.
- Local definitivo de certificados, XMLs, PDFs, remessas e retornos.

## Riscos antes da Sprint 3

- Confundir status interno com status oficial.
- Iniciar implementacao sem banco/integrador definido.
- Armazenar dados sensiveis sem politica de seguranca.
- Nao tratar idempotencia em webhooks/retornos.
- Nao cobrir rejeicoes fiscais/bancarias em testes.
