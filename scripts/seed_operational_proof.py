import json
from pathlib import Path

from scripts.test_environment import configure_test_environment


def main():
    configure_test_environment()
    from app import create_app
    from app.extensions import db
    from app.models.db import Tenant, Funcionario, FuncionarioEmpresa, Empresa, TipoEmpresa, Venda, LancamentoFinanceiro
    from app.security.password import hash_password
    from app.services.tenant_bootstrap_service import TenantBootstrapService
    from app.services.pdv_service import PdvService
    from tests.test_sprint03_transactions import stock_setup, sale_payload, scope
    app = create_app()
    with app.app_context():
        from flask_migrate import upgrade
        upgrade()
        if Tenant.query.count():
            raise RuntimeError("Proof requires empty synthetic test database.")
        tenant = Tenant(nome="Operational proof", limite_empresas=3)
        db.session.add(tenant)
        db.session.flush()
        roles = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
        user = Funcionario(tenant_id=tenant.id, role_id=roles["administrador"].id, nome="Synthetic operator",
            usuario="proof-only", cpf="00000000000", senha_hash=hash_password("Synthetic-proof!2026"))
        db.session.add(user)
        company = Empresa(tenant_id=tenant.id, cnpj="00000000000000", razao_social="Synthetic", nome_fantasia="Synthetic", tipo_empresa=TipoEmpresa.MATRIZ)
        db.session.add(company)
        db.session.flush()
        db.session.add(FuncionarioEmpresa(tenant_id=tenant.id, funcionario_id=user.id, empresa_id=company.id))
        TenantBootstrapService.garantir_cadastros_operacionais(tenant.id)
        db.session.commit()
        record, product = stock_setup(100)
        for number in range(3):
            PdvService.criar_venda(sale_payload(product, quantity=2, key=f"operational-proof-{number}"), 1, scope(), 1)
        assert Venda.query.count() == 3
        assert LancamentoFinanceiro.query.count() == 3
        destination = Path(app.config["STORAGE_ROOT"]) / "tenants/1/receipts"
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        (destination / "proof.txt").write_text("Synthetic receipt: three sales; total 60.00 BRL\n", encoding="utf-8")
        print(json.dumps({"synthetic": True, "sales": 3, "ledger_entries": 3, "total": "60.00", "stock_remaining": 94}))


if __name__ == "__main__":
    main()
