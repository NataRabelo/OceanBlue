"""add sprint3 boleto and fiscal external status

Revision ID: 1a2b3c4d5e6f
Revises: ea3d60221646
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "1a2b3c4d5e6f"
down_revision = "ea3d60221646"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for value in ("XML_GERADO", "XML_ASSINADO", "ENVIADA_AUTORIZACAO", "INUTILIZADA", "CONTINGENCIA"):
            op.execute(
                f"ALTER TYPE statusnotafiscal ADD VALUE IF NOT EXISTS '{value}'"
            )

    with op.batch_alter_table("boletos") as batch_op:
        batch_op.add_column(sa.Column("status_bancario", sa.String(length=30), nullable=False, server_default="NAO_REGISTRADO"))
        batch_op.add_column(sa.Column("provider_codigo", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("ambiente_bancario", sa.String(length=30), nullable=False, server_default="HOMOLOGACAO"))
        batch_op.add_column(sa.Column("idempotency_key_registro", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("registro_bancario_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("protocolo_registro", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("mensagem_retorno_banco", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("registrado_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("ultimo_retorno_bancario_em", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("origem_baixa", sa.String(length=40), nullable=True))
        batch_op.create_index("ix_boleto_tenant_empresa_status_bancario", ["tenant_id", "empresa_id", "status_bancario"])

    op.create_table(
        "arquivos_boleto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("boleto_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=30), nullable=False),
        sa.Column("ambiente", sa.String(length=30), nullable=False, server_default="HOMOLOGACAO"),
        sa.Column("path", sa.String(length=255), nullable=False),
        sa.Column("provider_codigo", sa.String(length=80), nullable=True),
        sa.Column("identificador_externo", sa.String(length=120), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["boleto_id"], ["boletos.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_arquivo_boleto_tenant_boleto_tipo", "arquivos_boleto", ["tenant_id", "boleto_id", "tipo"])

    op.create_table(
        "retornos_bancarios_boleto",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("boleto_id", sa.Integer(), nullable=False),
        sa.Column("provider_codigo", sa.String(length=80), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("tipo_evento", sa.String(length=60), nullable=False),
        sa.Column("status_processamento", sa.String(length=30), nullable=False, server_default="PROCESSADO"),
        sa.Column("payload_resumido", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["boleto_id"], ["boletos.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_codigo", "event_id", name="uq_retorno_bancario_evento"),
    )
    op.create_index("ix_retorno_bancario_tenant_boleto", "retornos_bancarios_boleto", ["tenant_id", "boleto_id"])

    with op.batch_alter_table("configuracoes_fiscais_empresa") as batch_op:
        batch_op.add_column(sa.Column("integrador_provider", sa.String(length=80), nullable=False, server_default="mock_nfce"))
        batch_op.add_column(sa.Column("integrador_credencial_env", sa.String(length=120), nullable=True))

    with op.batch_alter_table("notas_fiscais_venda") as batch_op:
        batch_op.add_column(sa.Column("status_oficial", sa.String(length=30), nullable=False, server_default="NAO_ENVIADA"))
        batch_op.add_column(sa.Column("modelo", sa.String(length=10), nullable=False, server_default="NFC-e"))
        batch_op.add_column(sa.Column("provider_codigo", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key_envio", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("protocolo_oficial", sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column("xml_assinado_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("xml_autorizado_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("danfe_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("codigo_retorno", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("autorizada_em", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_nota_fiscal_tenant_empresa_status_oficial", ["tenant_id", "empresa_id", "status_oficial"])

    op.create_table(
        "eventos_fiscais_nota",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("nota_id", sa.Integer(), nullable=False),
        sa.Column("provider_codigo", sa.String(length=80), nullable=False),
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("tipo_evento", sa.String(length=60), nullable=False),
        sa.Column("status_processamento", sa.String(length=30), nullable=False, server_default="PROCESSADO"),
        sa.Column("codigo_retorno", sa.String(length=20), nullable=True),
        sa.Column("mensagem", sa.Text(), nullable=True),
        sa.Column("payload_resumido", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["nota_id"], ["notas_fiscais_venda.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "provider_codigo", "event_id", name="uq_evento_fiscal_provider_evento"),
    )
    op.create_index("ix_evento_fiscal_tenant_nota", "eventos_fiscais_nota", ["tenant_id", "nota_id"])


def downgrade():
    op.drop_index("ix_evento_fiscal_tenant_nota", table_name="eventos_fiscais_nota")
    op.drop_table("eventos_fiscais_nota")

    with op.batch_alter_table("notas_fiscais_venda") as batch_op:
        batch_op.drop_index("ix_nota_fiscal_tenant_empresa_status_oficial")
        batch_op.drop_column("autorizada_em")
        batch_op.drop_column("codigo_retorno")
        batch_op.drop_column("danfe_path")
        batch_op.drop_column("xml_autorizado_path")
        batch_op.drop_column("xml_assinado_path")
        batch_op.drop_column("protocolo_oficial")
        batch_op.drop_column("idempotency_key_envio")
        batch_op.drop_column("provider_codigo")
        batch_op.drop_column("modelo")
        batch_op.drop_column("status_oficial")

    with op.batch_alter_table("configuracoes_fiscais_empresa") as batch_op:
        batch_op.drop_column("integrador_credencial_env")
        batch_op.drop_column("integrador_provider")

    op.drop_index("ix_retorno_bancario_tenant_boleto", table_name="retornos_bancarios_boleto")
    op.drop_table("retornos_bancarios_boleto")
    op.drop_index("ix_arquivo_boleto_tenant_boleto_tipo", table_name="arquivos_boleto")
    op.drop_table("arquivos_boleto")

    with op.batch_alter_table("boletos") as batch_op:
        batch_op.drop_index("ix_boleto_tenant_empresa_status_bancario")
        batch_op.drop_column("origem_baixa")
        batch_op.drop_column("ultimo_retorno_bancario_em")
        batch_op.drop_column("registrado_em")
        batch_op.drop_column("mensagem_retorno_banco")
        batch_op.drop_column("protocolo_registro")
        batch_op.drop_column("registro_bancario_id")
        batch_op.drop_column("idempotency_key_registro")
        batch_op.drop_column("ambiente_bancario")
        batch_op.drop_column("provider_codigo")
        batch_op.drop_column("status_bancario")
