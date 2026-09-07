import click

from app.extensions import db
from app.models.db import Empresa, EntregaAlerta
from app.services.alerta_service import AlertaService


def register_alert_commands(app):
    @app.cli.command("processar-alertas")
    @click.option("--tenant-id", type=int, required=True)
    def processar_alertas(tenant_id):
        empresas = Empresa.query.filter_by(tenant_id=tenant_id, ativo=True).all()
        empresa_ids = [empresa.id for empresa in empresas]
        escopo = {"tenant_id": tenant_id, "empresa_ids": empresa_ids, "permission_codes": set()}
        for empresa_id in empresa_ids:
            AlertaService.rotina(tenant_id, empresa_id, escopo)
        pendentes = EntregaAlerta.query.filter(EntregaAlerta.tenant_id == tenant_id,
            EntregaAlerta.empresa_id.in_(empresa_ids), EntregaAlerta.status.in_(["PENDENTE", "FALHOU"])).all()
        ids = [record.id for record in pendentes]
        db.session.remove()
        for record_id in ids:
            AlertaService.entregar(record_id, tenant_id, retentar=True)
        click.echo(f"Rotina concluida para {len(empresa_ids)} empresas; {len(ids)} pendencias processadas.")
