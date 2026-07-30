# Especificacao tecnica de boletos

## Estado atual

O sistema possui base interna de boleto financeiro, mas nao possui emissao bancaria real. O modulo controla bancos emissores, configuracao de parcelamento, regras de juros/multa, boletos, parcelas, eventos, baixa manual e recalcule de encargos.

## Componentes analisados

- `app/models/db.py`: `BancoEmissor`, `ConfiguracaoParcelamento`, `RegraJurosMulta`, `Boleto`, `ParcelaBoleto`, `EventoBoleto`.
- `app/controllers/boleto_controller.py`: endpoints sob `/api/financeiro/boletos`.
- `app/services/boleto_service.py`: criacao, listagem, baixa e recalculo.
- `app/services/banco_emissor_service.py`: cadastro de banco emissor, parcelamento e regras.
- `app/repositorys/boleto_repository.py`: consultas e persistencia.
- `tests/test_boleto_service.py`: calculo de juros/multa e protecao contra recalcule cumulativo.
- `app/templates/modulos/financeiro/boletos.html`: tela operacional inicial criada na Sprint 2.

## Fluxo atual

1. Usuario com permissao financeira chama endpoints de boleto.
2. `criar_boleto` valida empresa, cliente, banco emissor, forma de pagamento, categoria, valor e vencimento.
3. O boleto nasce como `PENDENTE`.
4. Quando ha parcelas, o service define parcelas como `EMITIDO` e o boleto tambem passa para `EMITIDO`.
5. Eventos sao gravados como `EMISSAO`, mesmo sem banco real.
6. Baixa manual soma `valor_pago`, reduz `valor_restante`, atualiza status e cria `LancamentoFinanceiro`.
7. Recalculo busca regra vigente, calcula juros/multa por parcela e atualiza valores restantes.

## Problemas atuais

- `EMITIDO` significa emissao interna, nao registro bancario.
- Nao ha linha digitavel/codigo de barras gerados por banco.
- Nao ha PDF real de boleto.
- Nao ha remessa CNAB, retorno CNAB ou webhook bancario.
- Nao ha conciliacao automatica entre pagamento bancario e baixa financeira.
- Permissao ainda reutiliza `criar_lancamento_financeiro`; podem ser necessarias permissoes especificas.
- Dados bancarios sensiveis ainda nao tem politica formal de mascaramento/criptografia.
- Antes da Sprint 2, o valor do boleto podia receber juros/multa cumulativos em recalculos repetidos.

## Correcao aplicada na Sprint 2

O recalcule de juros/multa passou a recompor `boleto.valor_restante` a partir da soma dos `valor_restante` das parcelas recalculadas. Assim, chamadas repetidas para a mesma data nao acrescentam novamente os mesmos encargos sobre o total anterior.

## Estados recomendados

Separar estado interno de estado bancario:

- `RASCUNHO_INTERNO`
- `PENDENTE_VALIDACAO`
- `PRONTO_PARA_REGISTRO`
- `REGISTRO_SOLICITADO`
- `REGISTRADO_BANCO`
- `REGISTRO_REJEITADO`
- `PDF_DISPONIVEL`
- `VENCIDO`
- `PAGO_PARCIAL`
- `PAGO`
- `BAIXADO_MANUALMENTE`
- `CANCELAMENTO_SOLICITADO`
- `CANCELADO_BANCO`
- `ESTORNADO`

Se os enums atuais forem preservados, criar campos adicionais como `status_bancario`, `registrado_em`, `protocolo_registro`, `mensagem_retorno_banco` e `origem_baixa`.

## Dados bancarios necessarios

- Banco, agencia, conta, digitos, carteira, variacao, convenio/codigo cedente.
- CNPJ/CPF e razao social do beneficiario.
- Endereco completo do beneficiario.
- Nosso numero e regra de sequenciamento.
- Especie documento, aceite, instrucoes, juros, multa, desconto, protesto/negativacao se aplicavel.
- Credenciais de API ou parametros CNAB por banco.
- Ambiente homologacao/producao.
- Chaves/segredos com armazenamento seguro.

## Opcoes de integracao

### API bancaria

Melhor para bancos com API madura. Permite registro, consulta, PDF, webhook e baixa com menor dependencia de arquivos. Exige contrato, credenciais, homologacao e tratamento robusto de retornos.

### CNAB

Melhor quando o banco exige remessa/retorno ou quando a operacao ja usa intercambio de arquivos. Exige gerador por layout, controle de sequencial de remessa, importacao de retorno e auditoria dos arquivos.

### Hibrido

API para bancos modernos e CNAB como fallback por banco/carteira. Exige uma camada de adaptadores por provedor.

## Estrutura sugerida

- `BoletoProvider`: interface com `registrar`, `consultar`, `cancelar`, `gerar_pdf`, `processar_retorno`.
- `BoletoRegistroBancario`: status bancario, protocolo, nosso numero final, erros, payload de request/response higienizado.
- `BoletoArquivo`: remessa, retorno, PDF, HTML, comprovantes e metadados.
- `BoletoWebhookEvento`: evento externo, assinatura, payload bruto, status de processamento.
- `BaixaBancaria`: valor pago, data credito, tarifa, origem, identificador do banco e vinculo com lancamento financeiro.

## Tela operacional

A Sprint 2 criou uma tela inicial em `/api/financeiro/boletos/view` com listagem e filtros por status, cliente, vencimento e venda. A tela informa que os boletos sao controles internos e que ainda nao ha registro bancario real.

## Tarefas recomendadas para Sprint 3

1. Escolher banco/integrador e confirmar API, CNAB ou modelo hibrido.
2. Separar status interno e status bancario.
3. Criar migration para registro bancario, arquivos e eventos externos.
4. Implementar adaptador de homologacao sem afetar regras financeiras existentes.
5. Implementar geracao/armazenamento de PDF apenas com retorno bancario ou layout validado.
6. Implementar webhook ou importacao de retorno CNAB.
7. Criar conciliacao de baixa bancaria com lancamento financeiro idempotente.
8. Criar testes de registro, rejeicao, baixa, retorno duplicado, cancelamento e recalcule.
