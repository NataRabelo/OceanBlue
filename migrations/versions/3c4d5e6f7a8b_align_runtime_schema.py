"""Align migrated types, tenant indexes and installment foreign key with models."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "3c4d5e6f7a8b"
down_revision = "2b3c4d5e6f7a"
branch_labels = None
depends_on = None


ENUM_VALUES = {
    "layoutarquivoboleto": ("CNAB240", "CNAB240_API", "CNAB400"),
    "ambienteboleto": ("sandbox", "producao"),
    "regradistribuicaoparcelamento": ("proporcional", "manual"),
    "tipomultaboleto": ("percentual", "fixo", "nenhum"),
    "tipojurosboleto": ("diario", "mensal", "nenhum"),
    "basecalculojurosmulta": ("valor_nominal", "valor_restante"),
    "statusboleto": (
        "PENDENTE", "EMITIDO", "VENCIDO", "PARCIALMENTE_PAGO", "PAGO",
        "CANCELADO", "ESTORNADO", "BAIXA_MANUAL",
    ),
    "statusbancarioboleto": (
        "NAO_REGISTRADO", "REGISTRO_SOLICITADO", "REGISTRADO", "REJEITADO",
        "PAGO", "BAIXADO", "CANCELADO",
    ),
    "tipoeventoboleto": (
        "EMISSAO", "REGISTRO_SOLICITADO", "REGISTRO_BANCARIO", "REGISTRO_REJEITADO",
        "WEBHOOK_BANCARIO", "VENCIMENTO", "PAGAMENTO", "PAGAMENTO_PARCIAL",
        "ESTORNO", "BAIXA_MANUAL", "RECALCULO_JUROS", "ALTERACAO_REGRA",
    ),
    "statusoficialnotafiscal": (
        "NAO_ENVIADA", "EM_PROCESSAMENTO", "AUTORIZADA", "REJEITADA",
        "CANCELADA", "INUTILIZADA", "CONTINGENCIA",
    ),
}

ENUM_COLUMNS = (
    ("bancos_emissores", "layout_arquivo", "layoutarquivoboleto", 20, "CNAB400"),
    ("bancos_emissores", "ambiente", "ambienteboleto", 20, "sandbox"),
    ("configuracoes_parcelamento", "regra_distribuicao", "regradistribuicaoparcelamento", 20, "proporcional"),
    ("regras_juros_multa", "tipo_multa", "tipomultaboleto", 20, "nenhum"),
    ("regras_juros_multa", "tipo_juros", "tipojurosboleto", 20, "nenhum"),
    ("regras_juros_multa", "base_calculo", "basecalculojurosmulta", 30, "valor_restante"),
    ("boletos", "status", "statusboleto", 30, "PENDENTE"),
    ("boletos", "status_bancario", "statusbancarioboleto", 30, "NAO_REGISTRADO"),
    ("parcelas_boleto", "status", "statusboleto", 30, "PENDENTE"),
    ("eventos_boleto", "tipo_evento", "tipoeventoboleto", 30, None),
    ("notas_fiscais_venda", "status_oficial", "statusoficialnotafiscal", 30, "NAO_ENVIADA"),
)

TENANT_INDEX_TABLES = (
    "adiantamentos_funcionario", "arquivos_boleto", "bancos_emissores", "boletos",
    "configuracoes_asaas_empresa", "configuracoes_parcelamento", "eventos_fiscais_nota",
    "regras_juros_multa", "retornos_bancarios_boleto",
)


def upgrade():
    for enum_name, values in ENUM_VALUES.items():
        postgresql.ENUM(*values, name=enum_name).create(op.get_bind())
    for table, column, enum_name, length, default in ENUM_COLUMNS:
        op.alter_column(table, column, server_default=None)
        op.alter_column(
            table, column, existing_type=sa.String(length),
            type_=postgresql.ENUM(*ENUM_VALUES[enum_name], name=enum_name, create_type=False),
            postgresql_using=f"{column}::{enum_name}",
        )
        if default is not None:
            op.alter_column(table, column, server_default=default)
    for table in TENANT_INDEX_TABLES:
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
    op.create_foreign_key(
        "fk_boletos_configuracao_parcelamento_id", "boletos", "configuracoes_parcelamento",
        ["configuracao_parcelamento_id"], ["id"],
    )


def downgrade():
    op.drop_constraint("fk_boletos_configuracao_parcelamento_id", "boletos", type_="foreignkey")
    for table in reversed(TENANT_INDEX_TABLES):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table)
    for table, column, enum_name, length, default in reversed(ENUM_COLUMNS):
        op.alter_column(table, column, server_default=None)
        op.alter_column(
            table, column,
            existing_type=postgresql.ENUM(*ENUM_VALUES[enum_name], name=enum_name, create_type=False),
            type_=sa.String(length), postgresql_using=f"{column}::varchar({length})",
        )
        if default is not None:
            op.alter_column(table, column, server_default=default)
    for enum_name, values in reversed(list(ENUM_VALUES.items())):
        postgresql.ENUM(*values, name=enum_name).drop(op.get_bind())
