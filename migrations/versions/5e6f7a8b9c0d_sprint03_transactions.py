from alembic import op
import sqlalchemy as sa


revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_mov_estoque_saida_item", "movimentos_estoque", ["tenant_id", "item_venda_id"],
                    unique=True, postgresql_where=sa.text("item_venda_id IS NOT NULL AND tipo_movimento = 'SAIDA' AND motivo = 'VENDA'"))
    op.create_table(
        "operacoes_idempotentes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("funcionario_id", sa.Integer(), sa.ForeignKey("funcionarios.id"), nullable=False),
        sa.Column("operacao", sa.String(80), nullable=False),
        sa.Column("chave", sa.String(128), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("resposta", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "funcionario_id", "operacao", "chave", name="uq_operacao_idempotente"),
    )
    op.create_index("ix_operacoes_idempotentes_tenant_id", "operacoes_idempotentes", ["tenant_id"])
    op.execute("""CREATE TRIGGER security_integrity BEFORE INSERT OR UPDATE ON operacoes_idempotentes
               FOR EACH ROW EXECUTE FUNCTION ocean_integrity('[["empresa_id","empresas"],["funcionario_id","funcionarios"]]')""")


def downgrade():
    op.drop_table("operacoes_idempotentes")
    op.drop_index("uq_mov_estoque_saida_item", table_name="movimentos_estoque")
