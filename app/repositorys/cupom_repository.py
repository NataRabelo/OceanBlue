from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.db import Cupom, Funcionario, TipoDesconto


class CupomRepository:

    @staticmethod
    def listar(tenant_id):
        return (
            Cupom.query
            .options(joinedload(Cupom.criado_por))
            .filter(Cupom.tenant_id == tenant_id)
            .order_by(Cupom.data_validade.asc(), Cupom.id.desc())
            .all()
        )

    @staticmethod
    def buscar_por_id(cupom_id, tenant_id):
        return (
            Cupom.query
            .options(joinedload(Cupom.criado_por))
            .filter(
                Cupom.id == cupom_id,
                Cupom.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_por_codigo(codigo, tenant_id, ignorar_id=None):
        query = Cupom.query.filter(
            Cupom.codigo == codigo,
            Cupom.tenant_id == tenant_id,
        )

        if ignorar_id is not None:
            query = query.filter(Cupom.id != ignorar_id)

        return query.first()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def deletar(obj):
        db.session.delete(obj)

    @staticmethod
    def salvar():
        from app.services.transaction_service import save
        save()

    @staticmethod
    def rollback():
        db.session.rollback()
