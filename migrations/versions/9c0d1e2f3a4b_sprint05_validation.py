from alembic import op


revision = "9c0d1e2f3a4b"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE FUNCTION ocean_validate_reversal_marker() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE reversed_total numeric;
        BEGIN
            IF TG_OP = 'UPDATE' AND OLD.revertido AND NOT NEW.revertido THEN
                RAISE EXCEPTION 'Reversao financeira nao pode ser desfeita' USING ERRCODE = '23514';
            END IF;
            IF NEW.revertido THEN
                SELECT coalesce(sum(valor), 0) INTO reversed_total FROM lancamentos_financeiros
                WHERE lancamento_origem_id = NEW.id AND tenant_id = NEW.tenant_id
                  AND empresa_id = NEW.empresa_id AND tipo <> NEW.tipo
                  AND forma_pagamento_id IS NOT DISTINCT FROM NEW.forma_pagamento_id;
                IF reversed_total <> NEW.valor THEN
                    RAISE EXCEPTION 'Reversao exige contrapartida integral' USING ERRCODE = '23514';
                END IF;
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE CONSTRAINT TRIGGER validate_reversal_marker
        AFTER INSERT OR UPDATE ON lancamentos_financeiros DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION ocean_validate_reversal_marker()""")


def downgrade():
    op.execute("DROP TRIGGER validate_reversal_marker ON lancamentos_financeiros")
    op.execute("DROP FUNCTION ocean_validate_reversal_marker()")
