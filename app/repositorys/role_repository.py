from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import Funcionario, Permission, Role, RolePermission


class RoleRepository:

    @staticmethod
    def listar(tenant_id):
        return (
            Role.query
            .options(
                joinedload(Role.permissions_links).joinedload(RolePermission.permission)
            )
            .filter(Role.tenant_id == tenant_id)
            .order_by(Role.nome.asc())
            .all()
        )

    @staticmethod
    def buscar_por_id(role_id, tenant_id):
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
    def buscar_por_codigo(codigo, tenant_id, ignorar_role_id=None):
        query = Role.query.filter(
            Role.codigo == codigo,
            Role.tenant_id == tenant_id
        )

        if ignorar_role_id is not None:
            query = query.filter(Role.id != ignorar_role_id)

        return query.first()

    @staticmethod
    def buscar_por_nome(nome, tenant_id, ignorar_role_id=None):
        query = Role.query.filter(
            Role.nome == nome,
            Role.tenant_id == tenant_id
        )

        if ignorar_role_id is not None:
            query = query.filter(Role.id != ignorar_role_id)

        return query.first()

    @staticmethod
    def listar_permissions_por_ids(permission_ids, tenant_id):
        if not permission_ids:
            return []

        return (
            Permission.query
            .filter(
                Permission.tenant_id == tenant_id,
                Permission.id.in_(permission_ids)
            )
            .all()
        )

    @staticmethod
    def contar_funcionarios_por_role(role_id, tenant_id):
        return (
            Funcionario.query
            .filter(
                Funcionario.role_id == role_id,
                Funcionario.tenant_id == tenant_id
            )
            .count()
        )

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
