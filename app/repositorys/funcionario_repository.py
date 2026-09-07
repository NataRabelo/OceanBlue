from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import Empresa, Funcionario, FuncionarioEmpresa, Permission, Role, RolePermission


def _digits_only_expression(column):
    expression = column
    for token in (".", "-", "/", "(", ")", " ", "+"):
        expression = db.func.replace(expression, token, "")
    return expression


class FuncionarioRepository:

    @staticmethod
    def listar_por_tenant(tenant_id):
        return (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario)
                .joinedload(Funcionario.role)
                .joinedload(Role.permissions_links)
                .joinedload(RolePermission.permission),
                joinedload(FuncionarioEmpresa.empresa)
            )
            .filter(FuncionarioEmpresa.tenant_id == tenant_id)
            .order_by(FuncionarioEmpresa.id.desc())
            .all()
        )

    @staticmethod
    def listar_empresas_por_tenant(tenant_id):
        return (
            Empresa.query
            .filter(
                Empresa.tenant_id == tenant_id,
                Empresa.ativo.is_(True)
            )
            .order_by(Empresa.nome_fantasia.asc())
            .all()
        )

    @staticmethod
    def listar_roles_por_tenant(tenant_id):
        return (
            Role.query
            .filter(
                Role.tenant_id == tenant_id,
                Role.ativo.is_(True)
            )
            .order_by(Role.nome.asc())
            .all()
        )

    @staticmethod
    def listar_ids_empresas_por_funcionario(funcionario_id, tenant_id):
        return [
            empresa_id
            for (empresa_id,) in (
                db.session.query(FuncionarioEmpresa.empresa_id)
                .join(Empresa, Empresa.id == FuncionarioEmpresa.empresa_id)
                .filter(
                    Empresa.tenant_id == tenant_id,
                    Empresa.ativo.is_(True),
                    FuncionarioEmpresa.funcionario_id == funcionario_id,
                    FuncionarioEmpresa.tenant_id == tenant_id,
                    FuncionarioEmpresa.ativo.is_(True)
                )
                .all()
            )
        ]

    @staticmethod
    def buscar_funcionario_empresa_por_id(funcionario_empresa_id, tenant_id):
        return (
            FuncionarioEmpresa.query
            .options(
                joinedload(FuncionarioEmpresa.funcionario)
                .joinedload(Funcionario.role)
                .joinedload(Role.permissions_links)
                .joinedload(RolePermission.permission),
                joinedload(FuncionarioEmpresa.empresa)
            )
            .filter(
                FuncionarioEmpresa.id == funcionario_empresa_id,
                FuncionarioEmpresa.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_empresa_por_id(empresa_id, tenant_id):
        return (
            Empresa.query
            .filter(
                Empresa.id == empresa_id,
                Empresa.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_role_por_id(role_id, tenant_id):
        return (
            Role.query
            .options(
                joinedload(Role.permissions_links).joinedload(RolePermission.permission)
            )
            .filter(
                Role.id == role_id,
                Role.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_role_por_codigo(codigo, tenant_id):
        return (
            Role.query
            .filter(
                Role.codigo == codigo,
                Role.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_permission_por_codigo(codigo, tenant_id):
        return (
            Permission.query
            .filter(
                Permission.codigo == codigo,
                Permission.tenant_id == tenant_id
            )
            .first()
        )

    @staticmethod
    def buscar_cpf_duplicado(cpf, tenant_id, ignorar_funcionario_id=None):
        cpf_normalizado = "".join(char for char in str(cpf) if char.isdigit())
        query = Funcionario.query.filter(
            _digits_only_expression(Funcionario.cpf) == cpf_normalizado,
            Funcionario.tenant_id == tenant_id
        )

        if ignorar_funcionario_id is not None:
            query = query.filter(Funcionario.id != ignorar_funcionario_id)

        return query.first()

    @staticmethod
    def buscar_funcionario_duplicado(usuario, tenant_id, ignorar_funcionario_id=None):
        query = Funcionario.query.filter(
            Funcionario.usuario == usuario,
            Funcionario.tenant_id == tenant_id
        )

        if ignorar_funcionario_id is not None:
            query = query.filter(Funcionario.id != ignorar_funcionario_id)

        return query.first()

    @staticmethod
    def contar_vinculos_funcionario(funcionario_id, tenant_id):
        return (
            FuncionarioEmpresa.query
            .filter(
                FuncionarioEmpresa.funcionario_id == funcionario_id,
                FuncionarioEmpresa.tenant_id == tenant_id
            )
            .count()
        )

    @staticmethod
    def busca_funcionario_por_id(funcionario_id: int, tenant_id=None):
        query = (
            Funcionario.query
            .options(
                joinedload(Funcionario.role)
                .joinedload(Role.permissions_links)
                .joinedload(RolePermission.permission)
            )
            .filter(Funcionario.id == funcionario_id)
        )

        if tenant_id is not None:
            query = query.filter(Funcionario.tenant_id == tenant_id)

        return query.first()

    @staticmethod
    def busca_funcionario_por_usuario(usuario: str, tenant_id=None):
        if tenant_id is None:
            raise ValueError("Tenant obrigatorio para localizar usuario.")
        query = (
            Funcionario.query
            .options(
                joinedload(Funcionario.role)
                .joinedload(Role.permissions_links)
                .joinedload(RolePermission.permission)
            )
            .filter(Funcionario.usuario == usuario)
        )

        if tenant_id is not None:
            query = query.filter(Funcionario.tenant_id == tenant_id)

        return query.first()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def deletar(obj):
        db.session.delete(obj)

    @staticmethod
    def salvar():
        save()

    @staticmethod
    def rollback():
        db.session.rollback()
