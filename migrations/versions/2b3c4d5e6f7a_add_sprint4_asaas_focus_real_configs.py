"""add sprint4 asaas and focus real configs

Revision ID: 2b3c4d5e6f7a
Revises: 1a2b3c4d5e6f
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "2b3c4d5e6f7a"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "configuracoes_asaas_empresa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.String(length=20), nullable=False, server_default="sandbox"),
        sa.Column("api_key", sa.String(length=500), nullable=True),
        sa.Column("wallet_id", sa.String(length=120), nullable=True),
        sa.Column("provider_codigo", sa.String(length=80), nullable=False, server_default="asaas"),
        sa.Column("status_configuracao", sa.String(length=30), nullable=False, server_default="PENDENTE"),
        sa.Column("ultima_validacao_em", sa.DateTime(), nullable=True),
        sa.Column("ultima_validacao_status", sa.String(length=30), nullable=True),
        sa.Column("ultima_validacao_mensagem", sa.Text(), nullable=True),
        sa.Column("webhook_url", sa.String(length=255), nullable=True),
        sa.Column("webhook_auth_token", sa.String(length=500), nullable=True),
        sa.Column("webhook_ativo", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dias_apos_vencimento_cancelamento", sa.Integer(), nullable=True),
        sa.Column("notificacoes_desabilitadas", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("ambiente IN ('sandbox', 'producao')", name="ck_config_asaas_ambiente"),
        sa.ForeignKeyConstraint(["empresa_id"], ["empresas.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "empresa_id", name="uq_config_asaas_empresa_tenant"),
    )
    op.create_index("ix_config_asaas_tenant_empresa", "configuracoes_asaas_empresa", ["tenant_id", "empresa_id"])

    with op.batch_alter_table("boletos") as batch_op:
        batch_op.add_column(sa.Column("cliente_externo_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("boleto_url", sa.String(length=500), nullable=True))

    with op.batch_alter_table("configuracoes_fiscais_empresa") as batch_op:
        batch_op.add_column(sa.Column("focus_token_homologacao", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("focus_token_producao", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("focus_cnpj_emitente", sa.String(length=14), nullable=True))
        batch_op.add_column(sa.Column("focus_status_configuracao", sa.String(length=30), nullable=False, server_default="PENDENTE"))
        batch_op.add_column(sa.Column("focus_ultima_validacao_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("focus_ultima_validacao_status", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("focus_ultima_validacao_mensagem", sa.Text(), nullable=True))

    with op.batch_alter_table("notas_fiscais_venda") as batch_op:
        batch_op.add_column(sa.Column("referencia_externa", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("danfe_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("xml_url", sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table("notas_fiscais_venda") as batch_op:
        batch_op.drop_column("xml_url")
        batch_op.drop_column("danfe_url")
        batch_op.drop_column("referencia_externa")

    with op.batch_alter_table("configuracoes_fiscais_empresa") as batch_op:
        batch_op.drop_column("focus_ultima_validacao_mensagem")
        batch_op.drop_column("focus_ultima_validacao_status")
        batch_op.drop_column("focus_ultima_validacao_em")
        batch_op.drop_column("focus_status_configuracao")
        batch_op.drop_column("focus_cnpj_emitente")
        batch_op.drop_column("focus_token_producao")
        batch_op.drop_column("focus_token_homologacao")

    with op.batch_alter_table("boletos") as batch_op:
        batch_op.drop_column("boleto_url")
        batch_op.drop_column("cliente_externo_id")

    op.drop_index("ix_config_asaas_tenant_empresa", table_name="configuracoes_asaas_empresa")
    op.drop_table("configuracoes_asaas_empresa")
