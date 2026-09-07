"""Shared authentication state, tenant integrity, SaaS quotas and access audit."""

from alembic import op
import sqlalchemy as sa
import json

revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None

FIELD_COLUMNS = {
    "configuracoes_asaas_empresa": {"api_key": 500, "webhook_auth_token": 500},
    "configuracoes_cliente_empresa": {"smtp_senha": 255, "whatsapp_token": 255, "sms_token": 255},
    "configuracoes_fiscais_empresa": {"csc_token": 255, "focus_token_homologacao": 500, "focus_token_producao": 500},
}


def upgrade():
    for table, fields in FIELD_COLUMNS.items():
        for field, length in fields.items():
            op.alter_column(table, field, existing_type=sa.String(length), type_=sa.Text())
    for table in ("funcionarios", "platform_owners"):
        op.add_column(table, sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table("login_attempts",
                    sa.Column("key", sa.String(64), primary_key=True),
                    sa.Column("attempts", sa.Integer(), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("revoked_tokens",
                    sa.Column("jti", sa.String(64), primary_key=True),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("password_resets",
                    sa.Column("token_hash", sa.String(64), primary_key=True),
                    sa.Column("scope", sa.String(20), nullable=False),
                    sa.Column("user_id", sa.Integer(), nullable=False),
                    sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id")),
                    sa.Column("session_version", sa.Integer(), nullable=False),
                    sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
                    sa.Column("used_at", sa.DateTime(timezone=True)))
    for table in ("login_attempts", "revoked_tokens", "password_resets"):
        op.create_index(f"ix_{table}_expires_at", table, ["expires_at"])
    op.execute("UPDATE tenants SET trial_ate = (criado_em AT TIME ZONE 'UTC' AT TIME ZONE 'America/Sao_Paulo')::date + 14 WHERE assinatura_status = 'trial' AND trial_ate IS NULL")
    op.execute("""
        CREATE FUNCTION ocean_session_version() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.senha_hash IS DISTINCT FROM OLD.senha_hash OR NEW.ativo IS DISTINCT FROM OLD.ativo THEN
                NEW.session_version := OLD.session_version + 1;
            END IF;
            RETURN NEW;
        END $$;
    """)
    for table in ("funcionarios", "platform_owners"):
        op.execute(f'CREATE TRIGGER security_session BEFORE UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION ocean_session_version()')
    op.execute("""
        CREATE FUNCTION ocean_scope(row_data jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
        DECLARE parent_data jsonb;
        BEGIN
            IF row_data->>'boleto_id' IS NOT NULL THEN
                SELECT to_jsonb(parent) INTO parent_data FROM boletos parent WHERE id = (row_data->>'boleto_id')::int;
            ELSIF row_data->>'venda_id' IS NOT NULL THEN
                SELECT to_jsonb(parent) INTO parent_data FROM vendas parent WHERE id = (row_data->>'venda_id')::int;
            ELSIF row_data->>'nota_id' IS NOT NULL THEN
                SELECT to_jsonb(parent) INTO parent_data FROM notas_fiscais_venda parent WHERE id = (row_data->>'nota_id')::int;
            END IF;
            RETURN jsonb_build_object(
                'tenant_id', COALESCE(row_data->>'tenant_id', parent_data->>'tenant_id'),
                'empresa_id', COALESCE(row_data->>'empresa_id', parent_data->>'empresa_id'));
        END $$;
        CREATE FUNCTION ocean_integrity() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE row_data jsonb := to_jsonb(NEW); own_scope jsonb; target_scope jsonb;
                target_data jsonb; reference jsonb; column_name text; target_name text;
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF row_data->>'tenant_id' IS DISTINCT FROM to_jsonb(OLD)->>'tenant_id'
                   OR row_data->>'empresa_id' IS DISTINCT FROM to_jsonb(OLD)->>'empresa_id'
                   OR row_data->>'boleto_id' IS DISTINCT FROM to_jsonb(OLD)->>'boleto_id'
                   OR row_data->>'venda_id' IS DISTINCT FROM to_jsonb(OLD)->>'venda_id' THEN
                    RAISE EXCEPTION 'Escopo imutavel' USING ERRCODE = '23514';
                END IF;
            END IF;
            own_scope := ocean_scope(row_data);
            FOR reference IN SELECT value FROM jsonb_array_elements(TG_ARGV[0]::jsonb) LOOP
                column_name := reference->>0;
                target_name := reference->>1;
                IF row_data->>column_name IS NULL THEN CONTINUE; END IF;
                EXECUTE format('SELECT to_jsonb(parent) FROM %I parent WHERE id = $1 FOR KEY SHARE', target_name)
                    INTO target_data USING (row_data->>column_name)::int;
                IF target_data IS NULL THEN
                    RAISE EXCEPTION 'Referencia indisponivel' USING ERRCODE = '23503';
                END IF;
                target_scope := ocean_scope(target_data);
                IF own_scope->>'tenant_id' IS NOT NULL AND target_scope->>'tenant_id' IS NOT NULL
                   AND own_scope->>'tenant_id' <> target_scope->>'tenant_id' THEN
                    RAISE EXCEPTION 'Referencia de outro tenant' USING ERRCODE = '23514';
                END IF;
                IF own_scope->>'empresa_id' IS NOT NULL AND target_scope->>'empresa_id' IS NOT NULL
                   AND own_scope->>'empresa_id' <> target_scope->>'empresa_id' THEN
                    RAISE EXCEPTION 'Referencia de outra empresa' USING ERRCODE = '23514';
                END IF;
                IF row_data->>'boleto_id' IS NOT NULL AND target_data->>'boleto_id' IS NOT NULL
                   AND row_data->>'boleto_id' <> target_data->>'boleto_id' THEN
                    RAISE EXCEPTION 'Parcela de outro boleto' USING ERRCODE = '23514';
                END IF;
                IF row_data->>'venda_id' IS NOT NULL AND target_data->>'venda_id' IS NOT NULL
                   AND row_data->>'venda_id' <> target_data->>'venda_id' THEN
                    RAISE EXCEPTION 'Item de outra venda' USING ERRCODE = '23514';
                END IF;
            END LOOP;
            RETURN NEW;
        END $$;
        CREATE FUNCTION ocean_quota() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE plan tenants%ROWTYPE; total bigint; maximum integer; month_start timestamp; month_end timestamp;
        BEGIN
            PERFORM pg_advisory_xact_lock(7202, NEW.tenant_id);
            SELECT * INTO plan FROM tenants WHERE id = NEW.tenant_id;
            IF plan.assinatura_status NOT IN ('active', 'trial') OR
               (plan.assinatura_status = 'trial' AND (plan.trial_ate IS NULL OR plan.trial_ate < (CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo')::date)) THEN
                RAISE EXCEPTION 'Assinatura indisponivel' USING ERRCODE = '23514';
            END IF;
            maximum := (to_jsonb(plan)->>TG_ARGV[0])::int;
            IF maximum IS NULL OR maximum <= 0 THEN
                RAISE EXCEPTION 'saas_quota invalida' USING ERRCODE = '23514';
            END IF;
            IF TG_TABLE_NAME = 'vendas' THEN
                month_start := date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo') AT TIME ZONE 'America/Sao_Paulo' AT TIME ZONE 'UTC';
                month_end := (date_trunc('month', CURRENT_TIMESTAMP AT TIME ZONE 'America/Sao_Paulo') + interval '1 month') AT TIME ZONE 'America/Sao_Paulo' AT TIME ZONE 'UTC';
                IF NEW.data_venda < month_start OR NEW.data_venda >= month_end THEN
                    RAISE EXCEPTION 'Data da venda fora do mes corrente' USING ERRCODE = '23514';
                END IF;
                SELECT count(*) INTO total FROM vendas WHERE tenant_id = NEW.tenant_id AND data_venda >= month_start AND data_venda < month_end;
            ELSE
                EXECUTE format('SELECT count(*) FROM %I WHERE tenant_id = $1', TG_TABLE_NAME) INTO total USING NEW.tenant_id;
            END IF;
            IF total >= maximum THEN
                RAISE EXCEPTION 'saas_quota atingida' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END $$;
        CREATE FUNCTION ocean_access_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE row_data jsonb := COALESCE(to_jsonb(NEW), to_jsonb(OLD)); before_data jsonb; after_data jsonb;
        BEGIN
            before_data := to_jsonb(OLD) - ARRAY['senha_hash', 'cpf', 'nome', 'salario', 'meta'];
            after_data := to_jsonb(NEW) - ARRAY['senha_hash', 'cpf', 'nome', 'salario', 'meta'];
            INSERT INTO audit_logs(tenant_id, actor_scope, actor_id, action, entity_type, entity_id, status, details, criado_em)
            VALUES ((row_data->>'tenant_id')::int, NULLIF(current_setting('ocean.actor_scope', true), ''),
                    NULLIF(current_setting('ocean.actor_id', true), '')::int,
                    'access.' || TG_TABLE_NAME || '.' || lower(TG_OP), TG_TABLE_NAME, row_data->>'id',
                    'SUCCESS', jsonb_build_object('before', before_data, 'after', after_data)::text, CURRENT_TIMESTAMP AT TIME ZONE 'UTC');
            RETURN COALESCE(NEW, OLD);
        END $$;
    """)
    inspector = sa.inspect(op.get_bind())
    for table in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "tenant_id" not in columns and table not in ("parcelas_boleto", "eventos_boleto"):
            continue
        references = []
        for foreign_key in inspector.get_foreign_keys(table):
            if foreign_key["referred_table"] == "tenants":
                continue
            references.append([foreign_key["constrained_columns"][0], foreign_key["referred_table"]])
        payload = json.dumps(references).replace("'", "''")
        op.execute(f"""CREATE TRIGGER security_integrity BEFORE INSERT OR UPDATE ON "{table}" FOR EACH ROW EXECUTE FUNCTION ocean_integrity('{payload}')""")
        if references:
            op.execute(f'UPDATE "{table}" SET id = id') if "id" in columns else None
    for table, limit in (("empresas", "limite_empresas"), ("funcionarios", "limite_funcionarios"),
                         ("produtos", "limite_produtos"), ("vendas", "limite_vendas_mes")):
        op.execute(f"""CREATE TRIGGER security_quota BEFORE INSERT ON "{table}" FOR EACH ROW EXECUTE FUNCTION ocean_quota('{limit}')""")
    for table in ("role", "permissions", "role_permission", "funcionarios", "funcionarios_empresa"):
        op.execute(f'CREATE TRIGGER security_audit AFTER INSERT OR UPDATE OR DELETE ON "{table}" FOR EACH ROW EXECUTE FUNCTION ocean_access_audit()')


def downgrade():
    for function in ("ocean_access_audit", "ocean_quota", "ocean_integrity", "ocean_session_version"):
        op.execute(f"DROP FUNCTION {function}() CASCADE")
    op.execute("DROP FUNCTION ocean_scope(jsonb)")
    for table in ("password_resets", "revoked_tokens", "login_attempts"):
        op.drop_table(table)
    for table in ("funcionarios", "platform_owners"):
        op.drop_column(table, "session_version")
    for table, fields in FIELD_COLUMNS.items():
        for field, length in fields.items():
            op.alter_column(table, field, existing_type=sa.Text(), type_=sa.String(length))
