import click
from sqlalchemy import delete

from app.extensions import db
from app.models.db import ConfiguracaoAsaasEmpresa, ConfiguracaoClienteEmpresa, ConfiguracaoFiscalEmpresa, PlatformOwner
from app.models.security import LoginAttempt, PasswordReset, RevokedToken
from app.security.field_crypto import FieldCrypto
from app.services.auth_service import AuthService


FIELDS = {
    ConfiguracaoAsaasEmpresa: ("api_key", "webhook_auth_token"),
    ConfiguracaoClienteEmpresa: ("smtp_senha", "whatsapp_token", "sms_token"),
    ConfiguracaoFiscalEmpresa: ("focus_token_homologacao", "focus_token_producao", "csc_token"),
}


def register_security_commands(app):
    @app.cli.command("rotate-field-keys")
    @click.option("--apply", is_flag=True, help="Recriptografa em uma unica transacao. Sem a opcao, apenas valida.")
    def rotate_fields(apply):
        count = 0
        try:
            for model, fields in FIELDS.items():
                for record in db.session.execute(db.select(model).with_for_update()).scalars():
                    for field in fields:
                        value = getattr(record, field)
                        if value:
                            rotated = FieldCrypto.encrypt(value)
                            count += 1
                            if apply:
                                setattr(record, field, rotated)
            if apply:
                db.session.commit()
            else:
                db.session.rollback()
        except Exception:
            db.session.rollback()
            raise click.ClickException("Rotacao cancelada; confira as chaves e a integridade dos campos.") from None
        click.echo(f"Campos {'rotacionados' if apply else 'validados'}: {count}")

    @app.cli.command("reset-platform-password")
    @click.option("--usuario", required=True)
    def reset_platform_password(usuario):
        user = PlatformOwner.query.filter_by(usuario=usuario, ativo=True).first()
        if not user:
            raise click.ClickException("Usuario indisponivel.")
        token = AuthService.emitir_redefinicao(user, "platform")
        click.echo("Codigo de uso unico, valido por 15 minutos. Entregue por canal seguro:")
        click.echo(token)

    @app.cli.command("cleanup-auth-state")
    def cleanup_auth_state():
        for model in (LoginAttempt, PasswordReset, RevokedToken):
            db.session.execute(delete(model).where(model.expires_at < db.func.now()))
        db.session.commit()
        click.echo("Estado de autenticacao expirado removido.")
