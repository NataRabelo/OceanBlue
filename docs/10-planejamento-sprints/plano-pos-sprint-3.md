# Plano pos-Sprint 3

1. Escolher banco/integrador definitivo de boleto e obter credenciais de homologacao.
2. Substituir `MockApiBancariaProvider` por provider real mantendo contrato atual.
3. Validar PDF oficial do banco/integrador e assinatura de webhook.
4. Escolher integrador fiscal e mapear contrato de API para NFC-e.
5. Substituir `MockIntegradorFiscalProvider` por provider real.
6. Validar certificado A1, CSC, schema XML, DANFE e autorizacao em UF real.
7. Implementar cancelamento, inutilizacao, consulta e contingencia fiscal oficiais.
8. Migrar storage privado para S3/Azure Blob/GCS ou volume seguro com backup.
9. Criar permissoes especificas para boleto e nota fiscal, separadas de lancamentos financeiros.
10. Executar homologacao assistida com contador, banco e integrador antes de producao.
