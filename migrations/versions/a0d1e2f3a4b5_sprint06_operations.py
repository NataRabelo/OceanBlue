from alembic import op
import sqlalchemy as sa


revision = "a0d1e2f3a4b5"
down_revision = "9c0d1e2f3a4b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("audit_logs", sa.Column("request_id", sa.String(32), server_default=sa.text("NULLIF(current_setting('ocean.request_id', true), '')")))
    op.create_index("ix_audit_logs_scope_cursor", "audit_logs", ["tenant_id", "empresa_id", "id"])
    op.execute("""INSERT INTO permissions (tenant_id, codigo, nome, ativo, criado_em, atualizado_em)
        SELECT id, 'visualizar_auditoria', 'Consultar auditoria operacional', true, now(), now() FROM tenants
        ON CONFLICT (tenant_id, codigo) DO NOTHING""")
    op.execute("""INSERT INTO role_permission (tenant_id, role_id, permission_id, criado_em, atualizado_em)
        SELECT roles.tenant_id, roles.id, permissions.id, now(), now() FROM role roles
        JOIN permissions ON permissions.tenant_id = roles.tenant_id AND permissions.codigo = 'visualizar_auditoria'
        WHERE roles.codigo = 'administrador' ON CONFLICT DO NOTHING""")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM audit_logs WHERE request_id IS NOT NULL)")).scalar():
        raise RuntimeError("Downgrade perderia rastreabilidade; restaure backup em banco novo e reconcilie escritas.")
    op.execute("DELETE FROM role_permission WHERE permission_id IN (SELECT id FROM permissions WHERE codigo = 'visualizar_auditoria')")
    op.execute("DELETE FROM permissions WHERE codigo = 'visualizar_auditoria'")
    op.drop_index("ix_audit_logs_scope_cursor", table_name="audit_logs")
    op.drop_column("audit_logs", "request_id")
