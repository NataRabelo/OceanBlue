from alembic import op
import sqlalchemy as sa


revision = "7a8b9c0d1e2f"
down_revision = "6f7a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cupons", sa.Column("data_inicio", sa.Date()))
    for field, parent in (("empresa_id", "empresas"), ("cliente_id", "clientes")):
        op.add_column("cupons", sa.Column(field, sa.Integer()))
        op.create_foreign_key(f"fk_cupons_{field}", "cupons", parent, [field], ["id"])
    for field in ("limite_usos", "limite_por_cliente"):
        op.add_column("cupons", sa.Column(field, sa.Integer()))
    op.add_column("cupons", sa.Column("valor_minimo", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("cupons", sa.Column("desconto_maximo", sa.Numeric(12, 2)))
    op.drop_constraint("ck_cupons_finite", "cupons", type_="check")
    op.create_check_constraint("ck_cupons_finite", "cupons", "valor_desconto NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) AND valor_minimo NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric) AND desconto_maximo NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)")
    op.create_check_constraint("ck_cupom_periodo", "cupons", "data_inicio IS NULL OR data_inicio <= data_validade")
    op.create_check_constraint("ck_cupom_usos", "cupons", "limite_usos IS NULL OR limite_usos > 0")
    op.create_check_constraint("ck_cupom_cliente_usos", "cupons", "limite_por_cliente IS NULL OR limite_por_cliente > 0")
    op.create_check_constraint("ck_cupom_valores", "cupons", "valor_minimo >= 0 AND valor_minimo < 10000000000 AND (desconto_maximo IS NULL OR (desconto_maximo > 0 AND desconto_maximo < 10000000000)) AND valor_desconto > 0 AND (tipo_desconto <> 'PERCENTUAL' OR valor_desconto <= 100)")
    op.execute("DROP TRIGGER security_integrity ON cupons")
    op.execute('''CREATE TRIGGER security_integrity BEFORE INSERT OR UPDATE ON cupons
        FOR EACH ROW EXECUTE FUNCTION ocean_integrity('[["criado_por_funcionario_id","funcionarios"],["empresa_id","empresas"],["cliente_id","clientes"]]')''')
    op.create_table("entregas_alerta",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False),
        sa.Column("empresa_id", sa.Integer(), sa.ForeignKey("empresas.id"), nullable=False),
        sa.Column("chave", sa.String(180), nullable=False),
        sa.Column("destinatario", sa.String(160), nullable=False),
        sa.Column("assunto", sa.String(160), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("erro", sa.String(200)),
        sa.Column("enviado_em", sa.DateTime()),
        sa.UniqueConstraint("tenant_id", "empresa_id", "chave", "destinatario", name="uq_entrega_alerta_destino"),
        sa.CheckConstraint("status IN ('PENDENTE', 'ENVIADO', 'FALHOU', 'INCERTO')", name="ck_entrega_alerta_status"),
        sa.CheckConstraint("tentativas >= 0", name="ck_entrega_alerta_tentativas"))
    op.create_index("ix_entregas_alerta_tenant_id", "entregas_alerta", ["tenant_id"])
    op.execute('''CREATE TRIGGER security_integrity BEFORE INSERT OR UPDATE ON entregas_alerta
        FOR EACH ROW EXECUTE FUNCTION ocean_integrity('[["empresa_id","empresas"]]')''')
    for code, name in (("aplicar_desconto", "Aplicar desconto manual ate 10%"), ("autorizar_desconto", "Autorizar desconto manual ate 100%")):
        op.execute(sa.text("""INSERT INTO permissions (tenant_id, codigo, nome, ativo, criado_em, atualizado_em)
            SELECT id, :code, :name, true, now(), now() FROM tenants
            ON CONFLICT (tenant_id, codigo) DO NOTHING""").bindparams(code=code, name=name))
        op.execute(sa.text("""INSERT INTO role_permission (tenant_id, role_id, permission_id, criado_em, atualizado_em)
            SELECT roles.tenant_id, roles.id, permissions.id, now(), now() FROM role roles
            JOIN permissions ON permissions.tenant_id = roles.tenant_id AND permissions.codigo = :code
            WHERE roles.codigo = 'administrador' ON CONFLICT DO NOTHING""").bindparams(code=code))


def downgrade():
    op.drop_constraint("ck_cupons_finite", "cupons", type_="check")
    op.create_check_constraint("ck_cupons_finite", "cupons", "valor_desconto NOT IN ('NaN'::numeric, 'Infinity'::numeric, '-Infinity'::numeric)")
    op.execute("DELETE FROM role_permission WHERE permission_id IN (SELECT id FROM permissions WHERE codigo IN ('aplicar_desconto', 'autorizar_desconto'))")
    op.execute("DELETE FROM permissions WHERE codigo IN ('aplicar_desconto', 'autorizar_desconto')")
    op.drop_table("entregas_alerta")
    op.execute("DROP TRIGGER security_integrity ON cupons")
    op.execute('''CREATE TRIGGER security_integrity BEFORE INSERT OR UPDATE ON cupons
        FOR EACH ROW EXECUTE FUNCTION ocean_integrity('[["criado_por_funcionario_id","funcionarios"]]')''')
    for constraint in ("ck_cupom_periodo", "ck_cupom_usos", "ck_cupom_cliente_usos", "ck_cupom_valores"):
        op.drop_constraint(constraint, "cupons", type_="check")
    for field in ("data_inicio", "empresa_id", "cliente_id", "limite_usos", "limite_por_cliente", "valor_minimo", "desconto_maximo"):
        op.drop_column("cupons", field)
