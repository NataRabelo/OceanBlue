from app.extensions import db
import os

from app.models.db import Empresa, Funcionario, FuncionarioEmpresa, PlatformOwner, Tenant, TipoEmpresa
from app.security.password import hash_password
from app.security.password import validate_password
from flask import current_app
from app.services.tenant_bootstrap_service import TenantBootstrapService


def _garantir_platform_owner():
    owner_name = os.getenv("PLATFORM_OWNER_NAME", "Owner Plataforma")
    owner_user = os.getenv("PLATFORM_OWNER_USER", "platform")
    owner_password = os.getenv("PLATFORM_OWNER_PASSWORD")

    owner = PlatformOwner.query.filter_by(usuario=owner_user).first()
    if not owner:
        validate_password(owner_password)
        owner = PlatformOwner(
            nome=owner_name,
            usuario=owner_user,
            senha_hash=hash_password(owner_password),
            ativo=True,
        )
        db.session.add(owner)
        db.session.commit()
        print("Platform owner criado")
        print(f"Usuario plataforma: {owner_user}")
    else:
        print("Platform owner ja existe")


def run_seed():
    print("Iniciando seed...")
    _garantir_platform_owner()
    if not current_app.debug or os.getenv("SEED_DEMO", "").lower() != "true":
        return
    demo_password = os.getenv("SEED_DEMO_PASSWORD")
    validate_password(demo_password)

    tenant_nome = "BlueOcean"
    tenant = Tenant.query.filter_by(nome=tenant_nome).first()

    if not tenant:
        tenant = Tenant(nome=tenant_nome, limite_empresas=3)
        db.session.add(tenant)
        db.session.commit()
        print("Tenant criado")
    else:
        print("Tenant ja existe")

    roles_por_codigo = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
    TenantBootstrapService.garantir_cadastros_operacionais(tenant.id)
    db.session.commit()

    empresas_seed = [
        {
            "cnpj": "12.345.678/0001-99",
            "razao_social": "BlueOcean Matriz LTDA",
            "nome_fantasia": "BlueOcean Matriz",
            "tipo_empresa": TipoEmpresa.MATRIZ,
        },
        {
            "cnpj": "12.345.678/0002-70",
            "razao_social": "BlueOcean Filial Centro LTDA",
            "nome_fantasia": "BlueOcean Centro",
            "tipo_empresa": TipoEmpresa.FILIAL,
        },
        {
            "cnpj": "12.345.678/0003-50",
            "razao_social": "BlueOcean Filial Shopping LTDA",
            "nome_fantasia": "BlueOcean Shopping",
            "tipo_empresa": TipoEmpresa.FILIAL,
        },
    ]

    empresas_criadas = []

    for dados_empresa in empresas_seed:
        empresa = Empresa.query.filter_by(
            tenant_id=tenant.id,
            cnpj=dados_empresa["cnpj"]
        ).first()

        if not empresa:
            empresa = Empresa(
                tenant_id=tenant.id,
                cnpj=dados_empresa["cnpj"],
                razao_social=dados_empresa["razao_social"],
                nome_fantasia=dados_empresa["nome_fantasia"],
                tipo_empresa=dados_empresa["tipo_empresa"],
                ativo=True
            )
            db.session.add(empresa)
            db.session.commit()
            print(f"Empresa criada: {empresa.nome_fantasia}")
        else:
            print(f"Empresa ja existe: {empresa.nome_fantasia}")

        empresas_criadas.append(empresa)

    usuario_admin = "admin"
    role_admin = roles_por_codigo["administrador"]

    funcionario = Funcionario.query.filter_by(
        tenant_id=tenant.id,
        usuario=usuario_admin
    ).first()

    if not funcionario:
        funcionario = Funcionario(
            tenant_id=tenant.id,
            role_id=role_admin.id,
            nome="Administrador",
            cpf="123.456.789-00",
            usuario=usuario_admin,
            senha_hash=hash_password(demo_password),
            ativo=True
        )
        db.session.add(funcionario)
        db.session.commit()

        print("Funcionario admin criado")
        print("Usuario: admin")
    else:
        if funcionario.role_id != role_admin.id:
            funcionario.role_id = role_admin.id
            db.session.commit()
        print("Funcionario admin ja existe")

    for empresa in empresas_criadas:
        vinculo = FuncionarioEmpresa.query.filter_by(
            tenant_id=tenant.id,
            funcionario_id=funcionario.id,
            empresa_id=empresa.id
        ).first()

        if not vinculo:
            vinculo = FuncionarioEmpresa(
                tenant_id=tenant.id,
                funcionario_id=funcionario.id,
                empresa_id=empresa.id,
                ativo=True
            )
            db.session.add(vinculo)
            db.session.commit()
            print(f"Vinculo criado: admin -> {empresa.nome_fantasia}")
        else:
            print(f"Vinculo ja existe: admin -> {empresa.nome_fantasia}")

    print("Seed finalizada com sucesso")
