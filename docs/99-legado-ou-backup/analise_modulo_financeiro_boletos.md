# Análise do módulo financeiro e expansão para boletos, parcelamentos e juros/multa

## 1. Objetivo do documento

Este documento consolida o entendimento do módulo financeiro do OceanBlue, sua arquitetura atual, seus pontos de integração e os principais itens que devem ser avaliados para implementar:

- emissão de boletos;
- parcelamento em boleto;
- cálculo e correção de juros e multa;
- rastreio de status, vencimentos e baixa/estorno.

O foco está em alinhar a implementação futura com o modelo multi-tenant, os fluxos operacionais já existentes e as regras de negócio do PDV.

---

## 2. Contexto do módulo financeiro no sistema

O módulo financeiro já é um componente central do sistema e atua como camada de integração entre:

- PDV e vendas finalizadas;
- controle de caixa e fechamento operacional;
- entradas e saídas manuais;
- adiantamentos de funcionários;
- relatórios financeiros e gestão de estoque.

Na arquitetura atual, o financeiro não é um módulo isolado. Ele recebe eventos de negócio de outras áreas e transforma esses eventos em lançamentos financeiros consolidados.

### 2.1. Principais responsabilidades atuais

- registrar entradas e saídas financeiras;
- consolidar receitas e despesas por empresa e período;
- apoiar o fechamento de caixa;
- gerar relatórios de fluxo de caixa, produtos mais vendidos e adiantamentos;
- permitir lançamentos manuais por categoria e forma de pagamento;
- refletir automaticamente o impacto financeiro de vendas no PDV.

---

## 3. Arquitetura atual do módulo financeiro

### 3.1. Estrutura de camadas

A implementação atual segue o padrão do projeto:

- [app/controllers/financeiro_controller.py](app/controllers/financeiro_controller.py): expõe endpoints HTTP para painel, lançamentos, fechamentos e relatórios.
- [app/services/financeiro_service.py](app/services/financeiro_service.py): concentra as regras de negócio, validações, geração de lançamentos e cálculo de caixa.
- [app/repositorys/financeiro_repository.py](app/repositorys/financeiro_repository.py): centraliza consultas e acesso aos dados financeiros.
- [app/models/db.py](app/models/db.py): define as entidades financeiras e seus relacionamentos.
- [app/templates/modulos/financeiro](app/templates/modulos/financeiro): interface de usuário para o módulo.
- [app/static/js/modulos](app/static/js/modulos): comportamento do painel financeiro e da tela de lançamentos.

### 3.2. Fluxo de execução atual

1. O controller recebe a requisição do frontend.
2. O serviço valida escopo, permissões e dados da operação.
3. O repositório consulta o banco e aplica filtros por tenant e empresa.
4. O resultado é serializado e devolvido ao frontend.

### 3.3. Ponto de extensão recomendado

A implementação de boletos deve seguir a mesma arquitetura, adicionando:

- um novo serviço dedicado para boletos;
- um repositório específico para consultas e status;
- modelos de domínio para vencimentos, parcelas e eventos de cobrança;
- endpoints HTTP para emissão, consulta, baixa e reprocessamento.

---

## 4. Banco de dados e entidades relevantes

O modelo atual já oferece uma base forte para expansão financeira. As entidades mais relevantes são:

### 4.1. Entidades existentes

- FormaPagamento
  - representa formas de pagamento como Dinheiro, Pix, Cartão, Boleto e Crediario.
  - já é usada para classificar cada lançamento financeiro.

- CategoriaFinanceira
  - organiza entradas e saídas financeiras.
  - utilizada para categorizar lançamentos manuais e automáticos.

- Venda
  - armazena o cabeçalho da venda, status, subtotal, desconto, total e dados do cliente/empresa.

- PagamentoVenda
  - representa cada parcela de pagamento associada a uma venda.
  - hoje funciona como base para a geração de lançamentos financeiros.

- LancamentoFinanceiro
  - é o maior ponto de integração do módulo financeiro.
  - armazena entradas, saídas, reversões e vinculação com venda, item de venda e categoria.
  - é a entidade mais importante para qualquer expansão futura.

- FechamentoCaixa
  - registra o fechamento do caixa e o confronto com o saldo esperado.

- AdiantamentoFuncionario
  - representa valores ou produtos entregues antecipadamente a funcionários e gera impacto financeiro.

### 4.2. Limitações do modelo atual para boletos

O modelo atual não implementa ainda:

- controle de boleto como documento financeiro com número, linha digitável, vencimento e status;
- gestão de parcelas ou títulos associados a um mesmo contrato/pagamento;
- regras de juros e multa por atraso;
- histórico de eventos do boleto, como emissão, vencimento, pagamento, estorno e baixa;
- diferenciação entre valor nominal, valor pago, valor restante e valor atualizado.

### 4.3. Modelos sugeridos para implementação futura

A seguir, um modelo de dados recomendado para suportar boletos com parcelamento e correção financeira:

#### 4.3.1. Boleto

Campos sugeridos:

- tenant_id
- empresa_id
- cliente_id
- venda_id (opcional)
- numero_boleto
- status
- valor_nominal
- valor_pago
- valor_restante
- data_emissao
- data_vencimento
- data_pagamento
- data_baixa
- forma_pagamento_id
- categoria_id
- observacao
- codigo_barras
- linha_digitavel
- arquivo_pdf_path
- arquivo_html_path

#### 4.3.2. ParcelaBoleto

Campos sugeridos:

- boleto_id
- numero_parcela
- valor_parcela
- valor_pago
- valor_restante
- data_vencimento
- data_pagamento
- status
- juros_calculados
- multa_calculada
- desconto_aplicado
- observacao

#### 4.3.3. ConfiguracaoBoleto

Campos sugeridos:

- tenant_id
- empresa_id
- juros_diario_percentual
- multa_percentual
- multa_fixa
- dias_grace
- dias_carencia
- aceite_automatico
- banco_codigo
- beneficiario_nome
- beneficiario_documento
- conta_bancaria_id

#### 4.3.4. EventoBoleto

Campos sugeridos:

- boleto_id
- parcela_id
- tipo_evento
- descricao
- valor
- criado_por_funcionario_id
- criado_em

Esses modelos devem manter a lógica de auditoria e serem sempre ligados ao tenant e à empresa correta.

---

## 5. Funcionalidades financeiras já existentes

### 5.1. Painel financeiro

O painel financeiro consolidará:

- entradas e saídas;
- saldo;
- faturamento;
- ticket médio;
- margem bruta;
- estoque em valor;
- projeções de saldo;
- recomendações de compra.

Esse painel já é um bom ponto de integração para mostrar o impacto de recebimentos via boleto e parcelas.

### 5.2. Lançamentos financeiros

Atualmente, o sistema permite:

- criação manual de lançamentos;
- associação a categoria e forma de pagamento;
- filtro por empresa, tipo e período;
- visualização e relatório.

Essa funcionalidade servirá como base para o lançamento de boletos emitidos e de juros/multa aplicados.

### 5.3. Fechamento de caixa

O fechamento de caixa compara:

- valor inicial;
- entradas e saídas do dia;
- saldo esperado;
- valor final informado.

A implementação de boletos deve levar em conta que recebimentos financeiros podem ser registrados em datas diferentes do vencimento, o que impacta o fluxo de caixa.

### 5.4. Integração com o PDV

O PDV já cria lançamentos financeiros automaticamente para vendas finalizadas. Esse fluxo é crucial porque qualquer boleto emitido a partir de uma venda deverá respeitar a mesma lógica de geração de entradas e possíveis estornos.

---

## 6. Como o fluxo atual já se encaixa no cenário de boletos

### 6.1. Ponto atual de entrada

A implementação de boletos pode ser iniciada a partir de um fluxo semelhante ao já usado para pagamentos de venda:

1. Uma venda é finalizada no PDV.
2. O sistema cria pagamentos vinculados à venda.
3. O financeiro registra lançamentos correspondentes.
4. Se o pagamento for por boleto, esse mesmo fluxo deve criar um título financeiro aguardando cobrança.

### 6.2. Diferença estratégica entre pagamento e título

Hoje, o sistema trata o pagamento como um evento financeiro imediato. Boleto exige um ciclo mais longo:

- emissão do título;
- vencimento;
- pagamento parcial ou total;
- atraso;
- juros e multa;
- baixa ou estorno.

Ou seja, o módulo precisa evoluir de “lançamento” para “título com ciclo de vida”.

---

## 7. Requisitos de negócio para emissão de boletos

### 7.1. Regras básicas de emissão

Para emitir boletos, o sistema precisa suportar:

- cadastro do beneficiário e da empresa emissora;
- definição do cliente pagador;
- definição do valor nominal;
- cálculo do vencimento;
- geração de identificador único do boleto;
- geração de arquivo de impressão ou PDF;
- persistência do status do título.

### 7.2. Regras de parcelamento em boleto

Para parcelamento, o sistema deve permitir:

- definir número total de parcelas;
- distribuir o valor total de forma proporcional ou manual;
- gerar uma data de vencimento por parcela;
- identificar a parcela ativa, vencida, paga ou cancelada;
- permitir pagamento parcial de uma parcela;
- recalcular saldo remanescente.

### 7.3. Regras de juros e multa

A correção financeira deve ter regras claras:

- multa fixa ou percentual;
- juros diários ou periódico;
- carência ou prazo de graça;
- aplicação somente após vencimento;
- cálculo sobre o valor restante ou sobre o valor nominal;
- histórico de recalculo e auditoria.

---

## 8. Pontos importantes para implementação

### 8.1. Status do título

O fluxo de boleto precisa de um lifecycle bem definido, por exemplo:

- PENDENTE
- EMITIDO
- VENCIDO
- PARCIALMENTE_PAGO
- PAGO
- CANCELADO
- ESTORNADO
- BAIXA_MANUAL

Esses estados devem ser persistidos e usados por relatórios e telas.

### 8.2. Auditoria e rastreabilidade

Toda mudança de status, valor, vencimento ou regra aplicada deve gerar um evento de auditoria. Isso é essencial para:

- evitar divergência contábil;
- permitir revisão do cálculo de juros;
- apoiar cobrança e contabilidade.

### 8.3. Segurança e permissões

O módulo precisa de permissões específicas, por exemplo:

- emitir_boleto;
- visualizar_boletos;
- editar_boleto;
- cancelar_boleto;
- aplicar_juros_multa;
- reprocessar_boleto;

Essas permissões devem seguir o modelo atual de roles e permissions do sistema.

### 8.4. Multi-tenant e escopo por empresa

Todas as novas entidades devem respeitar:

- tenant_id;
- empresa_id;
- filtro de acesso por funcionário;
- consistência com o modelo já existente de escopo operacional.

### 8.5. Integração com contas a receber

O fluxo de boleto deve impactar tanto o módulo financeiro quanto o módulo contábil/relatório. Em termos práticos, ele deve:

- gerar um lançamento financeiro de entrada quando houver pagamento;
- gerar um lançamento de baixa ou estorno quando houver cancelamento;
- não duplicar o impacto financeiro em vendas já consolidadas.

---

## 9. Recomendação de arquitetura para a nova implementação

### 9.1. Nova camada de serviço

Criar um serviço dedicado, por exemplo:

- BoletoService

Responsabilidades:

- criar título;
- gerar parcelamento;
- calcular vencimentos;
- aplicar multa e juros;
- atualizar status;
- registrar eventos;
- integrar com o financeiro atual.

### 9.2. Nova camada de repositório

Criar um repositório específico, por exemplo:

- BoletoRepository

Responsabilidades:

- buscar por tenant/empresa;
- listar títulos vencidos;
- listar títulos por status;
- recuperar parcelas por boleto;
- consultar títulos em atraso.

### 9.3. Nova camada de controller

Criar endpoints como:

- POST /api/financeiro/boletos
- GET /api/financeiro/boletos
- GET /api/financeiro/boletos/<id>
- POST /api/financeiro/boletos/<id>/parcelar
- POST /api/financeiro/boletos/<id>/baixar
- POST /api/financeiro/boletos/<id>/estornar
- POST /api/financeiro/boletos/<id>/recalcular-juros

### 9.4. Interface de usuário

A tela do financeiro pode ganhar:

- aba de boletos emitidos;
- tela de detalhe do boleto;
- tela de parcelamento;
- painel de boletos vencidos;
- módulo para recalcular juros e multa.

---

## 10. Estratégia de cálculo de juros e multa

### 10.1. Regras recomendadas

O cálculo de juros e multa deve ser configurável por tenant/empresa e por tipo de título. Exemplo:

- multa: 2% sobre o valor total em caso de atraso;
- juros: 0,033% ao dia após o vencimento;
- carência: 3 dias;
- aplicação somente sobre o saldo remanescente.

### 10.2. Ponto de atenção

Não basta aplicar juros apenas pelo valor nominal. O sistema deve considerar:

- pagamentos parciais;
- descontos ou abatimentos;
- títulos parcelados;
- estornos já aplicados;
- eventual diferença entre valor original e valor atualizado.

### 10.3. Recomendação prática

Criar um serviço de cálculo isolado, por exemplo:

- CalculoJurosMultaService

Esse serviço deve ser puro e testável, recebendo inputs como:

- valor nominal;
- valor pago;
- data de vencimento;
- data de referência;
- configuração da empresa;
- saldo restante.

---

## 11. Fluxo recomendado para implementação incremental

### Fase 1 - Estrutura base

- criar modelos para boleto, parcelas e eventos;
- criar migrations;
- adicionar permissões e bootstrap inicial;
- criar endpoints básicos de CRUD.

### Fase 2 - Emissão de boletos

- gerar título único;
- associar cliente, empresa e valor;
- gerar data de vencimento;
- salvar PDF/HTML da cobrança;
- exibir status no módulo financeiro.

### Fase 3 - Parcelamento

- permitir criação de múltiplas parcelas;
- distribuir o valor total;
- gerar vencimentos e status independentes;
- permitir baixa parcial.

### Fase 4 - Juros e multa

- implementar cálculo automático por atraso;
- permitir recalculo manual;
- registrar histórico de correção.

### Fase 5 - Integração operacional

- integrar com o fluxo do PDV;
- gerar relatórios de cobrança e inadimplência;
- integrar com e-mail/SMS/WhatsApp conforme o sistema já possui infraestrutura de comunicação.

---

## 12. Pontos de risco e cuidados

- duplicidade de lançamentos financeiros;
- inconsistência entre valor nominal e valor pago;
- cálculo incorreto de multa e juros em pagamentos parciais;
- falhas de auditoria em alterações manuais;
- conflitos entre status de venda, status de pagamento e status de boleto;
- problemas de timezone e datas de vencimento;
- falta de consistência entre tenant e empresa no cadastro de boleto.

---

## 13. Recomendações finais

A base atual do OceanBlue já está preparada para evoluir em direção a um módulo de cobranças mais robusto. O que falta não é uma revolução arquitetural, mas uma extensão consistente do domínio financeiro para suportar títulos com ciclo de vida.

As recomendações principais são:

1. manter o padrão atual de service/repository/controller;
2. introduzir modelos explícitos de boleto e parcela;
3. manter a lógica de juros/multa isolada e testável;
4. garantir rastreabilidade completa de cada alteração;
5. preservar a compatibilidade com o fluxo já existente de vendas e lançamentos financeiros.

Com isso, o sistema passará a tratar boletos, parcelamentos e cobrança em atraso como parte nativa do módulo financeiro, e não como uma extensão ad hoc.
