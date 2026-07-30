# Plano SaaS Comercial - OceanBlue

## Posicionamento

O OceanBlue e um SaaS de gestao operacional para varejos que precisam de PDV, estoque, financeiro, clientes, cashback, mensageria e controle multiempresa em um unico ambiente.

## Planos iniciais

### Starter - R$ 149,00/mes

- 1 empresa
- 5 funcionarios
- 500 produtos
- 1.500 vendas/mes
- PDV, estoque, financeiro, clientes e importacao/exportacao

### Business - R$ 399,00/mes

- 5 empresas
- 25 funcionarios
- 5.000 produtos
- 20.000 vendas/mes
- Recursos do Starter
- Operacao multiempresa
- Cashback e mensageria operacional

### Scale - R$ 899,00/mes

- 20 empresas
- 100 funcionarios
- 50.000 produtos
- 100.000 vendas/mes
- Recursos do Business
- Base para suporte premium e integracoes dedicadas

## Implantacao

- Implantacao simples: R$ 1.500,00
- Implantacao com migracao de planilhas e treinamento: R$ 3.500,00 a R$ 8.000,00
- Customizacoes devem ser cobradas fora da mensalidade.

## Controles SaaS implementados

- O tenant possui plano, status de assinatura, data de trial e limites comerciais.
- O painel de plataforma expõe os planos em `/api/platform/planos`.
- O painel de plataforma permite atualizar assinatura em `PUT /api/platform/tenants/<tenant_id>/assinatura`.
- Os modulos operacionais do tenant bloqueiam uso quando a assinatura esta inativa ou o trial expirou.
- A criacao de novas empresas e administradores respeita os limites do plano.
- O cadastro de produtos respeita o limite do plano.
- A criacao de vendas respeita o limite mensal do plano.
- Credenciais sensiveis de SMTP, WhatsApp, SMS e CSC sao criptografadas em repouso.
- A estrutura suporta evolucao para billing recorrente, bloqueio por inadimplencia e upgrade automatico.

## Proximos controles recomendados

- Integracao com gateway de pagamento para assinatura recorrente.
- Tela de upgrade/downgrade no painel de plataforma.
- Notificacoes automaticas de limite proximo.
- Worker assíncrono para importacoes, mensageria e fiscal.
- Cofre externo de segredos em ambiente gerenciado.
