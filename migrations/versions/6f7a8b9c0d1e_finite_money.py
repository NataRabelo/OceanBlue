from alembic import op


revision = "6f7a8b9c0d1e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


NUMERIC_COLUMNS = {
    "funcionarios": ["salario","meta"],
    "carteiras_cliente": ["saldo_disponivel"],
    "creditos_cashback_cliente": ["valor_original","saldo_disponivel"],
    "movimentos_carteira_cliente": ["valor"],
    "produtos_empresa": ["valor_compra","valor_venda","valor_varejo","valor_atacado"],
    "cupons": ["valor_desconto"],
    "adiantamentos_funcionario": ["valor_unitario","valor_total"],
    "movimentos_estoque": ["valor_unitario","valor_total"],
    "vendas": ["subtotal","desconto","cashback_utilizado","cashback_gerado","cashback_percentual_aplicado","valor_cancelado","total"],
    "itens_venda": ["valor_unitario","valor_total","valor_cancelado"],
    "pagamentos_venda": ["valor"],
    "lancamentos_financeiros": ["valor"],
    "configuracoes_parcelamento": ["valor_minimo_por_parcela"],
    "regras_juros_multa": ["percentual_multa","valor_fixo_multa","percentual_juros","percentual_maximo_teto"],
    "boletos": ["valor_nominal","valor_pago","valor_restante"],
    "parcelas_boleto": ["valor_parcela","valor_pago","valor_restante","juros_calculados","multa_calculada","desconto_aplicado"],
    "eventos_boleto": ["valor"],
    "fechamentos_caixa": ["valor_inicial","valor_final"],
    "configuracoes_cliente_empresa": ["cashback_percentual","cashback_percentual_limite_resgate_venda","cashback_valor_minimo_resgate"],
}


def upgrade():
    for table, columns in NUMERIC_COLUMNS.items():
        expression = " AND ".join(
            f"{column} NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)"
            for column in columns
        )
        op.create_check_constraint(f"ck_{table}_finite", table, expression)


def downgrade():
    for table in reversed(NUMERIC_COLUMNS):
        op.drop_constraint(f"ck_{table}_finite", table, type_="check")
