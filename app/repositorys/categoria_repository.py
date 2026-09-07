from app.extensions import db
from app.services.transaction_service import save
from app.models.db import CategoriaProduto


class CategoriaRepository:

    @staticmethod
    def listar_por_tenant(tenant_id, empresa_ids=None):
        return (
            CategoriaProduto.query
            .filter_by(tenant_id=tenant_id)
            .order_by(CategoriaProduto.id.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(categoria_id, tenant_id, empresa_ids=None):
        return CategoriaProduto.query.filter_by(
            id=categoria_id,
            tenant_id=tenant_id
        ).first()

    @staticmethod
    def criar(categoria):
        db.session.add(categoria)
        save()
        return categoria

    @staticmethod
    def atualizar():
        save()

    @staticmethod
    def deletar(categoria):
        db.session.delete(categoria)
        save()
