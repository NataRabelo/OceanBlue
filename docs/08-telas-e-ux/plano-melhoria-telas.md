# Plano de melhoria de telas - Sprint 2

## Telas prioritarias

- PDV: fluxo de venda, finalizacao, cancelamento e feedback de erros.
- Financeiro: dashboard, lancamentos, fechamentos e boletos.
- Fiscal: configuracao, prevalidacao e XML interno.
- Estoque: alertas, movimentos e indicadores.

## Achados

- O sistema possui padrao visual consistente com Tailwind, cards/painels escuros, botoes com icones Lucide e JS por modulo.
- Antes da Sprint 2 nao havia tela propria de boletos.
- A tela fiscal tinha textos que poderiam ser lidos como emissao fiscal oficial.
- Algumas telas ainda usam termos sem acento por padrao ASCII; isso e aceitavel tecnicamente, mas deve ser padronizado depois.

## Melhorias aplicadas

- Criada tela inicial de boletos em `/api/financeiro/boletos/view`.
- Adicionado link "Boletos" no painel financeiro.
- A tela de boletos lista registros internos, filtra por status, cliente, vencimento e venda, e mostra aviso de que nao ha registro bancario real.
- Textos fiscais foram ajustados para "XML interno" e "sem autorizacao SEFAZ".

## Recomendacoes futuras

- Adicionar modal real de detalhe do boleto com parcelas e eventos.
- Conectar acoes de baixa/recalculo da tela de boletos com confirmacao e controle de permissao.
- Criar estados vazios mais informativos em financeiro/fiscal/estoque.
- Revisar responsividade das tabelas em mobile.
- Padronizar mensagens de sucesso/erro entre modulos.
- Fazer inventario visual com screenshots em desktop e mobile antes de grandes mudancas.
