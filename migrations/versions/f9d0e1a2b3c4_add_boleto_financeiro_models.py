"""add boleto financeiro models

Revision ID: f9d0e1a2b3c4
Revises: 8f6e4c2a1b9d
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f9d0e1a2b3c4'
down_revision = '8f6e4c2a1b9d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'bancos_emissores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('banco_codigo', sa.String(length=20), nullable=False),
        sa.Column('banco_nome', sa.String(length=120), nullable=False),
        sa.Column('convenio', sa.String(length=80), nullable=True),
        sa.Column('carteira', sa.String(length=30), nullable=False),
        sa.Column('variacao_carteira', sa.String(length=30), nullable=True),
        sa.Column('agencia', sa.String(length=30), nullable=False),
        sa.Column('agencia_dv', sa.String(length=5), nullable=True),
        sa.Column('conta', sa.String(length=30), nullable=False),
        sa.Column('conta_dv', sa.String(length=5), nullable=True),
        sa.Column('codigo_cedente', sa.String(length=60), nullable=False),
        sa.Column('especie_documento', sa.String(length=10), nullable=False, server_default='DM'),
        sa.Column('layout_arquivo', sa.String(length=20), nullable=False, server_default='CNAB400'),
        sa.Column('ambiente', sa.String(length=20), nullable=False, server_default='sandbox'),
        sa.Column('credenciais_api_ref', sa.String(length=255), nullable=True),
        sa.Column('is_padrao', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_banco_emissor_tenant_empresa'), 'bancos_emissores', ['tenant_id', 'empresa_id'], unique=False)

    op.create_table(
        'configuracoes_parcelamento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('banco_emissor_id', sa.Integer(), nullable=True),
        sa.Column('numero_min_parcelas', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('numero_max_parcelas', sa.Integer(), nullable=False),
        sa.Column('intervalo_dias_padrao', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('permite_intervalo_customizado', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('dia_fixo_vencimento', sa.Integer(), nullable=True),
        sa.Column('valor_minimo_por_parcela', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('regra_distribuicao', sa.String(length=20), nullable=False, server_default='proporcional'),
        sa.Column('arredondamento_ultima_parcela', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['banco_emissor_id'], ['bancos_emissores.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_config_parcelamento_tenant_empresa'), 'configuracoes_parcelamento', ['tenant_id', 'empresa_id'], unique=False)

    op.create_table(
        'regras_juros_multa',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('banco_emissor_id', sa.Integer(), nullable=True),
        sa.Column('tipo_multa', sa.String(length=20), nullable=False, server_default='nenhum'),
        sa.Column('percentual_multa', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('valor_fixo_multa', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tipo_juros', sa.String(length=20), nullable=False, server_default='nenhum'),
        sa.Column('percentual_juros', sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column('dias_carencia', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('base_calculo', sa.String(length=30), nullable=False, server_default='valor_restante'),
        sa.Column('percentual_maximo_teto', sa.Numeric(precision=8, scale=4), nullable=False),
        sa.Column('vigente_desde', sa.DateTime(), nullable=False),
        sa.Column('vigente_ate', sa.DateTime(), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['banco_emissor_id'], ['bancos_emissores.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_regra_juros_tenant_empresa_vigencia'), 'regras_juros_multa', ['tenant_id', 'empresa_id', 'banco_emissor_id', 'vigente_desde', 'vigente_ate'], unique=False)

    op.create_table(
        'boletos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.Column('atualizado_em', sa.DateTime(), nullable=False),
        sa.Column('empresa_id', sa.Integer(), nullable=False),
        sa.Column('cliente_id', sa.Integer(), nullable=False),
        sa.Column('venda_id', sa.Integer(), nullable=True),
        sa.Column('banco_emissor_id', sa.Integer(), nullable=False),
        sa.Column('configuracao_parcelamento_id', sa.Integer(), nullable=True),
        sa.Column('numero_boleto', sa.String(length=60), nullable=False),
        sa.Column('nosso_numero', sa.String(length=80), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDENTE'),
        sa.Column('valor_nominal', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('valor_pago', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('valor_restante', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('data_emissao', sa.DateTime(), nullable=False),
        sa.Column('data_vencimento', sa.Date(), nullable=False),
        sa.Column('data_pagamento', sa.DateTime(), nullable=True),
        sa.Column('data_baixa', sa.DateTime(), nullable=True),
        sa.Column('forma_pagamento_id', sa.Integer(), nullable=False),
        sa.Column('categoria_id', sa.Integer(), nullable=False),
        sa.Column('codigo_barras', sa.String(length=140), nullable=True),
        sa.Column('linha_digitavel', sa.String(length=160), nullable=True),
        sa.Column('arquivo_pdf_path', sa.String(length=255), nullable=True),
        sa.Column('arquivo_html_path', sa.String(length=255), nullable=True),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['banco_emissor_id'], ['bancos_emissores.id']),
        sa.ForeignKeyConstraint(['categoria_id'], ['categorias_financeiras.id']),
        sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id']),
        sa.ForeignKeyConstraint(['empresa_id'], ['empresas.id']),
        sa.ForeignKeyConstraint(['forma_pagamento_id'], ['formas_pagamento.id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['venda_id'], ['vendas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'numero_boleto', name='uq_boleto_tenant_numero'),
    )
    op.create_index(op.f('ix_boleto_tenant_empresa_status'), 'boletos', ['tenant_id', 'empresa_id', 'status'], unique=False)
    op.create_index(op.f('ix_boleto_tenant_empresa_vencimento'), 'boletos', ['tenant_id', 'empresa_id', 'data_vencimento'], unique=False)

    op.create_table(
        'parcelas_boleto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('boleto_id', sa.Integer(), nullable=False),
        sa.Column('numero_parcela', sa.Integer(), nullable=False),
        sa.Column('valor_parcela', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('valor_pago', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('valor_restante', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('data_vencimento', sa.Date(), nullable=False),
        sa.Column('data_pagamento', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDENTE'),
        sa.Column('juros_calculados', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('multa_calculada', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('desconto_aplicado', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('observacao', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['boleto_id'], ['boletos.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('boleto_id', 'numero_parcela', name='uq_parcela_boleto_numero'),
    )
    op.create_index(op.f('ix_parcela_boleto_status_vencimento'), 'parcelas_boleto', ['status', 'data_vencimento'], unique=False)

    op.add_column('lancamentos_financeiros', sa.Column('boleto_id', sa.Integer(), nullable=True))
    op.add_column('lancamentos_financeiros', sa.Column('parcela_boleto_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'lancamentos_financeiros', 'boletos', ['boleto_id'], ['id'])
    op.create_foreign_key(None, 'lancamentos_financeiros', 'parcelas_boleto', ['parcela_boleto_id'], ['id'])
    op.create_index(op.f('ix_financeiro_tenant_boleto_parcela'), 'lancamentos_financeiros', ['tenant_id', 'boleto_id', 'parcela_boleto_id'], unique=False)

    op.create_table(
        'eventos_boleto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('boleto_id', sa.Integer(), nullable=False),
        sa.Column('parcela_id', sa.Integer(), nullable=True),
        sa.Column('tipo_evento', sa.String(length=30), nullable=False),
        sa.Column('descricao', sa.Text(), nullable=False),
        sa.Column('valor', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('regra_juros_multa_id', sa.Integer(), nullable=True),
        sa.Column('criado_por_funcionario_id', sa.Integer(), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['boleto_id'], ['boletos.id']),
        sa.ForeignKeyConstraint(['parcela_id'], ['parcelas_boleto.id']),
        sa.ForeignKeyConstraint(['regra_juros_multa_id'], ['regras_juros_multa.id']),
        sa.ForeignKeyConstraint(['criado_por_funcionario_id'], ['funcionarios.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_evento_boleto_boleto_tipo_data'), 'eventos_boleto', ['boleto_id', 'tipo_evento', 'criado_em'], unique=False)


def downgrade():
    op.drop_table('eventos_boleto')

    op.drop_index(op.f('ix_financeiro_tenant_boleto_parcela'), table_name='lancamentos_financeiros')
    for constraint in sa.inspect(op.get_bind()).get_foreign_keys('lancamentos_financeiros'):
        if constraint['constrained_columns'] in [['boleto_id'], ['parcela_boleto_id']]:
            op.drop_constraint(constraint['name'], 'lancamentos_financeiros', type_='foreignkey')
    op.drop_column('lancamentos_financeiros', 'parcela_boleto_id')
    op.drop_column('lancamentos_financeiros', 'boleto_id')

    op.drop_index(op.f('ix_parcela_boleto_status_vencimento'), table_name='parcelas_boleto')
    op.drop_table('parcelas_boleto')

    op.drop_index(op.f('ix_boleto_tenant_empresa_vencimento'), table_name='boletos')
    op.drop_index(op.f('ix_boleto_tenant_empresa_status'), table_name='boletos')
    op.drop_table('boletos')

    op.drop_index(op.f('ix_regra_juros_tenant_empresa_vigencia'), table_name='regras_juros_multa')
    op.drop_table('regras_juros_multa')

    op.drop_index(op.f('ix_config_parcelamento_tenant_empresa'), table_name='configuracoes_parcelamento')
    op.drop_table('configuracoes_parcelamento')

    op.drop_index(op.f('ix_banco_emissor_tenant_empresa'), table_name='bancos_emissores')
    op.drop_table('bancos_emissores')
