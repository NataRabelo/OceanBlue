from app.models.db import Role, RolePermission
from app.extensions import db
from app.repositorys.role_repository import RoleRepository
from app.security.permissions import get_permission_dependency_codes, normalize_permission_codes


class RoleService:

    @staticmethod
    def listar(tenant_id):
        return RoleRepository.listar(tenant_id)

    @staticmethod
    def criar(data, tenant_id):
        try:
            nome = (data.get("nome") or "").strip()
            codigo = (data.get("codigo") or "").strip()
            descricao = (data.get("descricao") or "").strip() or None
            permission_ids = RoleService._normalizar_ids(data.get("permission_ids"))
            ativo = RoleService._to_bool(data.get("ativo", True))

            if not nome:
                raise ValueError("Nome da role e obrigatorio.")
            if not codigo:
                raise ValueError("Codigo da role e obrigatorio.")

            if RoleRepository.buscar_por_nome(nome, tenant_id):
                raise ValueError("Ja existe uma role com esse nome.")
            if RoleRepository.buscar_por_codigo(codigo, tenant_id):
                raise ValueError("Ja existe uma role com esse codigo.")

            permissions = RoleService._resolver_permissions_validas(permission_ids, tenant_id)

            role = Role(
                tenant_id=tenant_id,
                nome=nome,
                codigo=codigo,
                descricao=descricao,
                ativo=ativo
            )
            RoleRepository.adicionar(role)
            db.session.flush()

            for permission in permissions:
                RoleRepository.adicionar(RolePermission(
                    tenant_id=tenant_id,
                    role_id=role.id,
                    permission_id=permission.id
                ))

            RoleRepository.salvar()
            return RoleRepository.buscar_por_id(role.id, tenant_id)
        except Exception:
            RoleRepository.rollback()
            raise

    @staticmethod
    def atualizar(role_id, data, tenant_id):
        try:
            role = RoleRepository.buscar_por_id(role_id, tenant_id)
            if not role:
                raise ValueError("Role nao encontrada.")

            nome = (data.get("nome") or "").strip()
            codigo = (data.get("codigo") or "").strip()
            descricao = (data.get("descricao") or "").strip() or None
            permission_ids = RoleService._normalizar_ids(data.get("permission_ids"))
            ativo = RoleService._to_bool(data.get("ativo", True))

            if not nome:
                raise ValueError("Nome da role e obrigatorio.")
            if not codigo:
                raise ValueError("Codigo da role e obrigatorio.")

            if RoleRepository.buscar_por_nome(nome, tenant_id, ignorar_role_id=role.id):
                raise ValueError("Ja existe uma role com esse nome.")
            if RoleRepository.buscar_por_codigo(codigo, tenant_id, ignorar_role_id=role.id):
                raise ValueError("Ja existe uma role com esse codigo.")

            permissions = RoleService._resolver_permissions_validas(permission_ids, tenant_id)

            role.nome = nome
            role.codigo = codigo
            role.descricao = descricao
            role.ativo = ativo

            for link in list(role.permissions_links):
                RoleRepository.deletar(link)

            db.session.flush()

            for permission in permissions:
                RoleRepository.adicionar(RolePermission(
                    tenant_id=tenant_id,
                    role_id=role.id,
                    permission_id=permission.id
                ))

            RoleRepository.salvar()
            return RoleRepository.buscar_por_id(role.id, tenant_id)
        except Exception:
            RoleRepository.rollback()
            raise

    @staticmethod
    def deletar(role_id, tenant_id):
        try:
            role = RoleRepository.buscar_por_id(role_id, tenant_id)
            if not role:
                raise ValueError("Role nao encontrada.")

            if RoleRepository.contar_funcionarios_por_role(role.id, tenant_id) > 0:
                raise ValueError("Nao e possivel excluir uma role vinculada a funcionarios.")

            RoleRepository.deletar(role)
            RoleRepository.salvar()
        except Exception:
            RoleRepository.rollback()
            raise

    @staticmethod
    def _normalizar_ids(values):
        if values in (None, ""):
            return []

        if not isinstance(values, list):
            values = [values]

        ids = []
        for value in values:
            if value in (None, ""):
                continue
            ids.append(int(value))

        return list(dict.fromkeys(ids))

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in ["1", "true", "on", "sim", "yes"]

    @staticmethod
    def _resolver_permissions_validas(permission_ids, tenant_id):
        permissions = RoleRepository.listar_permissions_por_ids(permission_ids, tenant_id)
        if len(permissions) != len(permission_ids):
            raise ValueError("Uma ou mais permissions informadas nao existem.")

        permissions_by_id = {permission.id: permission for permission in permissions}
        selected_codes = {permission.codigo for permission in permissions}
        effective_codes = normalize_permission_codes(selected_codes)

        valid_permissions = []
        for permission_id in permission_ids:
            permission = permissions_by_id.get(permission_id)
            if not permission:
                continue

            dependency_codes = get_permission_dependency_codes(permission.codigo)
            if dependency_codes and permission.codigo not in effective_codes:
                continue

            valid_permissions.append(permission)

        return valid_permissions
