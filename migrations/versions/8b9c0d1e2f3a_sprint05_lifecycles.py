from alembic import op
import sqlalchemy as sa


revision = "8b9c0d1e2f3a"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade():
    for code, name in [["estornar_financeiro","Estornar lancamentos financeiros"], ["reabrir_caixa","Reabrir e ajustar caixa"], ["autorizar_adiantamento","Autorizar e baixar adiantamentos"], ["gerenciar_privacidade_cliente","Exportar e anonimizar clientes"]]:
        op.execute(sa.text("""INSERT INTO permissions (tenant_id, codigo, nome, ativo, criado_em, atualizado_em)
            SELECT id, :code, :name, true, now(), now() FROM tenants
            ON CONFLICT (tenant_id, codigo) DO NOTHING""").bindparams(code=code, name=name))
        op.execute(sa.text("""INSERT INTO role_permission (tenant_id, role_id, permission_id, criado_em, atualizado_em)
            SELECT roles.tenant_id, roles.id, permissions.id, now(), now() FROM role roles
            JOIN permissions ON permissions.tenant_id = roles.tenant_id AND permissions.codigo = :code
            WHERE roles.codigo = 'administrador' ON CONFLICT DO NOTHING""").bindparams(code=code))
    op.add_column("vendas", sa.Column("cashback_processado", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("vendas", sa.Column("cashback_payload", sa.String(64)))
    op.execute("UPDATE vendas SET cashback_processado = true")
    op.add_column("clientes", sa.Column("anonimizado_em", sa.DateTime()))
    for table, default in (("adiantamentos_funcionario", "AUTORIZADO"), ("fechamentos_caixa", "FECHADO")):
        op.add_column(table, sa.Column("status", sa.String(20), nullable=False, server_default=default))
        op.add_column(table, sa.Column("revisao", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("fechamentos_caixa", sa.Column("conciliacao", sa.JSON()))
    op.create_check_constraint("ck_fechamento_estado", "fechamentos_caixa", "status IN ('FECHADO', 'REABERTO') AND revisao > 0")
    op.create_check_constraint("ck_adiantamento_estado", "adiantamentos_funcionario", "status IN ('PENDENTE', 'AUTORIZADO', 'BAIXADO', 'CANCELADO', 'ESTORNADO') AND revisao > 0")
    for column in (sa.Column("chave", sa.String(128)), sa.Column("payload_hash", sa.String(64)),
                   sa.Column("estado", sa.String(20), nullable=False, server_default="PENDENTE"),
                   sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
                   sa.Column("proxima_tentativa", sa.DateTime())):
        op.add_column("mensagens_cliente", column)
    op.execute("UPDATE mensagens_cliente SET estado = CASE WHEN status = 'ENVIADO' THEN 'ENVIADO' ELSE 'INCERTO' END")
    op.create_unique_constraint("uq_mensagem_chave", "mensagens_cliente", ["tenant_id", "empresa_id", "cliente_id", "chave"])
    op.create_check_constraint("ck_mensagem_estado", "mensagens_cliente", "estado IN ('PENDENTE', 'ENVIADO', 'FALHOU', 'INCERTO', 'CANCELADO', 'ESGOTADO')")
    op.create_check_constraint("ck_mensagem_tentativas", "mensagens_cliente", "tentativas >= 0 AND tentativas <= 5")
    op.execute("""CREATE FUNCTION ocean_preserve_ledger() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'Historico financeiro nao pode ser excluido' USING ERRCODE = '23514'; END IF;
            IF (to_jsonb(NEW) - 'revertido' - 'atualizado_em') IS DISTINCT FROM
               (to_jsonb(OLD) - 'revertido' - 'atualizado_em') THEN
                RAISE EXCEPTION 'Use reversao formal para ajustar lancamentos' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("CREATE TRIGGER preserve_ledger BEFORE UPDATE OR DELETE ON lancamentos_financeiros FOR EACH ROW EXECUTE FUNCTION ocean_preserve_ledger()")


def downgrade():
    op.execute("DELETE FROM role_permission WHERE permission_id IN (SELECT id FROM permissions WHERE codigo IN ('estornar_financeiro', 'reabrir_caixa', 'autorizar_adiantamento', 'gerenciar_privacidade_cliente'))")
    op.execute("DELETE FROM permissions WHERE codigo IN ('estornar_financeiro', 'reabrir_caixa', 'autorizar_adiantamento', 'gerenciar_privacidade_cliente')")
    op.drop_column("vendas", "cashback_payload")
    op.drop_column("vendas", "cashback_processado")
    op.execute("DROP TRIGGER preserve_ledger ON lancamentos_financeiros")
    op.execute("DROP FUNCTION ocean_preserve_ledger()")
    for constraint in ("uq_mensagem_chave", "ck_mensagem_estado", "ck_mensagem_tentativas"):
        op.drop_constraint(constraint, "mensagens_cliente")
    for field in ("chave", "payload_hash", "estado", "tentativas", "proxima_tentativa"):
        op.drop_column("mensagens_cliente", field)
    op.drop_constraint("ck_fechamento_estado", "fechamentos_caixa")
    op.drop_constraint("ck_adiantamento_estado", "adiantamentos_funcionario")
    op.drop_column("fechamentos_caixa", "conciliacao")
    for table in ("adiantamentos_funcionario", "fechamentos_caixa"):
        op.drop_column(table, "status")
        op.drop_column(table, "revisao")
    op.drop_column("clientes", "anonimizado_em")
