from datetime import timedelta

from app.services.time_service import TimeService


class SaasPlanService:
    PLANS = {
        "starter": {
            "codigo": "starter",
            "nome": "Starter",
            "preco_mensal": "149.00",
            "limite_empresas": 1,
            "limite_funcionarios": 5,
            "limite_produtos": 500,
            "limite_vendas_mes": 1500,
        },
        "business": {
            "codigo": "business",
            "nome": "Business",
            "preco_mensal": "399.00",
            "limite_empresas": 5,
            "limite_funcionarios": 25,
            "limite_produtos": 5000,
            "limite_vendas_mes": 20000,
        },
        "scale": {
            "codigo": "scale",
            "nome": "Scale",
            "preco_mensal": "899.00",
            "limite_empresas": 20,
            "limite_funcionarios": 100,
            "limite_produtos": 50000,
            "limite_vendas_mes": 100000,
        },
    }

    @classmethod
    def get_plan(cls, codigo):
        plan_code = (codigo or "starter").strip().lower()
        if plan_code not in cls.PLANS:
            raise ValueError("Plano comercial invalido.")
        return cls.PLANS[plan_code]

    @classmethod
    def apply_plan(cls, tenant, codigo=None, status=None, trial_days=14):
        plan = cls.get_plan(codigo or tenant.plano_codigo)
        status = (status or getattr(tenant, "assinatura_status", None) or "trial").strip().lower()
        if status not in {"active", "trial", "past_due", "suspended", "canceled"}:
            raise ValueError("Status de assinatura invalido.")
        if not 1 <= trial_days <= 30:
            raise ValueError("Duracao de trial invalida.")
        tenant.plano_codigo = plan["codigo"]
        tenant.assinatura_status = status
        tenant.limite_empresas = plan["limite_empresas"]
        tenant.limite_funcionarios = plan["limite_funcionarios"]
        tenant.limite_produtos = plan["limite_produtos"]
        tenant.limite_vendas_mes = plan["limite_vendas_mes"]

        if tenant.assinatura_status == "trial" and not tenant.trial_ate:
            created_at = TimeService.to_brasilia(tenant.criado_em)
            tenant.trial_ate = (created_at.date() if created_at else TimeService.today_br()) + timedelta(days=trial_days)

        return tenant

    @classmethod
    def serializar_plano(cls, codigo):
        plan = cls.get_plan(codigo)
        return dict(plan)
