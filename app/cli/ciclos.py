import json
import click

from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.cliente_privacidade_service import ClientePrivacidadeService
from app.services.mensagem_fila_service import MensagemFilaService


def register_cycle_commands(app):
    @app.cli.command("processar-ciclos")
    @click.option("--tenant-id", type=int, required=True)
    @click.option("--funcionario-id", type=int, required=True)
    def processar(tenant_id, funcionario_id):
        scope = AcessoEmpresaService.obter_escopo(funcionario_id, tenant_id)
        if not {"gerenciar_configuracao_cliente", "enviar_mensagem_cliente", "visualizar_todas_empresas"}.issubset(scope["permission_codes"]):
            raise click.ClickException("Permissoes insuficientes para rotina global.")
        expiration = ClientePrivacidadeService.expirar(tenant_id)
        deliveries = MensagemFilaService.processar(tenant_id, scope, funcionario_id)
        click.echo(json.dumps({"cashback": expiration, "mensagens": [{"id": record["id"], "status": record["status"]} for record in deliveries]}))
