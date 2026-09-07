from datetime import date

from app.extensions import db
from app.models.db import Tenant, Venda
from app.services.time_service import TimeService


class TenantEntitlementService:
    ACTIVE_STATUSES = {"active", "trial"}

    @staticmethod
    def obter_tenant(tenant_id):
        tenant = db.session.get(Tenant, int(tenant_id)) if tenant_id else None
        if not tenant:
            raise PermissionError("Tenant nao encontrado.")
        return tenant

    @staticmethod
    def validar_assinatura(tenant_id):
        tenant = TenantEntitlementService.obter_tenant(tenant_id)
        status = (tenant.assinatura_status or "").strip().lower()

        if status not in TenantEntitlementService.ACTIVE_STATUSES:
            raise PermissionError("Assinatura inativa. Regularize o plano para continuar usando o sistema.")

        if status == "trial" and (not tenant.trial_ate or tenant.trial_ate < TimeService.today_br()):
            raise PermissionError("Periodo de teste expirado. Ative uma assinatura para continuar.")

        return tenant

    @staticmethod
    def validar_limite_produtos(tenant_id, quantidade_atual):
        tenant = TenantEntitlementService.validar_assinatura(tenant_id)
        limite = int(tenant.limite_produtos or 0)
        if limite > 0 and int(quantidade_atual or 0) >= limite:
            raise ValueError("Limite de produtos do plano atingido. Atualize o plano para cadastrar novos itens.")

    @staticmethod
    def validar_limite_vendas_mes(tenant_id):
        tenant = TenantEntitlementService.validar_assinatura(tenant_id)
        limite = int(tenant.limite_vendas_mes or 0)
        if limite <= 0:
            return

        hoje = TimeService.today_br()
        inicio = date(hoje.year, hoje.month, 1)
        fim = date(hoje.year + (1 if hoje.month == 12 else 0), 1 if hoje.month == 12 else hoje.month + 1, 1)
        inicio_utc = TimeService.local_date_start_to_utc_naive(inicio)
        fim_utc = TimeService.local_date_start_to_utc_naive(fim)

        total = (
            Venda.query
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.data_venda >= inicio_utc,
                Venda.data_venda < fim_utc,
            )
            .count()
        )
        if total >= limite:
            raise ValueError("Limite mensal de vendas do plano atingido. Atualize o plano para continuar vendendo.")
