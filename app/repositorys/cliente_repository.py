from datetime import date

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.services.transaction_service import save
from app.models.db import (
    CarteiraCliente,
    Cliente,
    ConfiguracaoClienteEmpresa,
    CreditoCashbackCliente,
    Empresa,
    ItemVenda,
    MensagemCliente,
    MovimentoCarteiraCliente,
    MovimentoEstoque,
    StatusVenda,
    Venda,
)


def _digits_only_expression(column):
    expression = column
    for token in (".", "-", "/", "(", ")", " ", "+"):
        expression = db.func.replace(expression, token, "")
    return expression


class ClienteRepository:

    @staticmethod
    def listar_empresas(tenant_id, empresa_ids=None):
        query = (
            Empresa.query
            .filter(
                Empresa.tenant_id == tenant_id,
                Empresa.ativo.is_(True),
            )
            .order_by(Empresa.nome_fantasia.asc())
        )

        if empresa_ids is not None:
            query = query.filter(Empresa.id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def buscar_empresa_por_id(empresa_id, tenant_id):
        return (
            Empresa.query
            .filter(
                Empresa.id == empresa_id,
                Empresa.tenant_id == tenant_id,
                Empresa.ativo.is_(True),
            )
            .first()
        )

    @staticmethod
    def listar_clientes(tenant_id, busca=None):
        query = (
            Cliente.query
            .options(
                joinedload(Cliente.carteira),
                joinedload(Cliente.vendas).joinedload(Venda.empresa),
            )
            .filter(
                Cliente.tenant_id == tenant_id,
                Cliente.ativo.is_(True),
            )
            .order_by(Cliente.nome.asc(), Cliente.id.asc())
        )

        termo = (busca or "").strip()
        if termo:
            like = f"%{termo}%"
            termo_numerico = "".join(char for char in termo if char.isdigit())
            filtros = [
                Cliente.nome.ilike(like),
                Cliente.documento.ilike(like),
                Cliente.email.ilike(like),
                Cliente.telefone.ilike(like),
                Cliente.whatsapp.ilike(like),
            ]
            if termo_numerico:
                like_numerico = f"%{termo_numerico}%"
                filtros.extend([
                    _digits_only_expression(Cliente.documento).ilike(like_numerico),
                    _digits_only_expression(Cliente.telefone).ilike(like_numerico),
                    _digits_only_expression(Cliente.whatsapp).ilike(like_numerico),
                ])
            query = query.filter(
                db.or_(*filtros)
            )

        return query.all()

    @staticmethod
    def listar_clientes_para_pdv(tenant_id, limite=200):
        return (
            Cliente.query
            .options(joinedload(Cliente.carteira))
            .filter(
                Cliente.tenant_id == tenant_id,
                Cliente.ativo.is_(True),
            )
            .order_by(Cliente.nome.asc(), Cliente.id.asc())
            .limit(max(int(limite or 200), 1))
            .all()
        )

    @staticmethod
    def listar_clientes_para_mensagem(tenant_id, cliente_ids=None):
        query = (
            Cliente.query
            .filter(
                Cliente.tenant_id == tenant_id,
                Cliente.ativo.is_(True),
            )
            .order_by(Cliente.nome.asc(), Cliente.id.asc())
        )

        if cliente_ids is not None:
            query = query.filter(Cliente.id.in_(cliente_ids))

        return query.all()

    @staticmethod
    def buscar_cliente_por_id(cliente_id, tenant_id):
        return (
            Cliente.query
            .options(
                joinedload(Cliente.carteira),
                joinedload(Cliente.creditos_cashback),
                joinedload(Cliente.vendas).joinedload(Venda.empresa),
                joinedload(Cliente.mensagens),
            )
            .filter(
                Cliente.id == cliente_id,
                Cliente.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def buscar_cliente_por_documento(documento, tenant_id, ignorar_cliente_id=None):
        if not documento:
            return None

        documento_normalizado = "".join(char for char in str(documento) if char.isdigit())

        query = Cliente.query.filter(
            Cliente.tenant_id == tenant_id,
            _digits_only_expression(Cliente.documento) == documento_normalizado,
        )
        if ignorar_cliente_id is not None:
            query = query.filter(Cliente.id != ignorar_cliente_id)
        return query.first()

    @staticmethod
    def obter_carteira_por_cliente(cliente_id, tenant_id):
        return (
            CarteiraCliente.query
            .options(joinedload(CarteiraCliente.cliente))
            .filter(
                CarteiraCliente.tenant_id == tenant_id,
                CarteiraCliente.cliente_id == cliente_id,
            )
            .first()
        )

    @staticmethod
    def listar_creditos_disponiveis(cliente_id, tenant_id, data_referencia=None):
        data_ref = data_referencia or date.today()
        return (
            CreditoCashbackCliente.query
            .options(
                joinedload(CreditoCashbackCliente.carteira),
                joinedload(CreditoCashbackCliente.empresa),
                joinedload(CreditoCashbackCliente.venda_origem),
            )
            .filter(
                CreditoCashbackCliente.tenant_id == tenant_id,
                CreditoCashbackCliente.cliente_id == cliente_id,
                CreditoCashbackCliente.saldo_disponivel > 0,
                CreditoCashbackCliente.cancelado_em.is_(None),
                CreditoCashbackCliente.data_expiracao >= data_ref,
            )
            .order_by(
                CreditoCashbackCliente.data_expiracao.asc(),
                CreditoCashbackCliente.id.asc(),
            )
            .all()
        )

    @staticmethod
    def listar_creditos_vencidos(cliente_id, tenant_id, data_referencia=None):
        data_ref = data_referencia or date.today()
        return (
            CreditoCashbackCliente.query
            .filter(
                CreditoCashbackCliente.tenant_id == tenant_id,
                CreditoCashbackCliente.cliente_id == cliente_id,
                CreditoCashbackCliente.saldo_disponivel > 0,
                CreditoCashbackCliente.cancelado_em.is_(None),
                CreditoCashbackCliente.data_expiracao < data_ref,
            )
            .order_by(CreditoCashbackCliente.data_expiracao.asc(), CreditoCashbackCliente.id.asc())
            .all()
        )

    @staticmethod
    def buscar_credito_por_venda_origem(venda_id, tenant_id):
        return (
            CreditoCashbackCliente.query
            .options(
                joinedload(CreditoCashbackCliente.carteira),
                joinedload(CreditoCashbackCliente.cliente),
            )
            .filter(
                CreditoCashbackCliente.tenant_id == tenant_id,
                CreditoCashbackCliente.venda_origem_id == venda_id,
            )
            .first()
        )

    @staticmethod
    def listar_movimentos_carteira(cliente_id, tenant_id, limite=100):
        return (
            MovimentoCarteiraCliente.query
            .options(
                joinedload(MovimentoCarteiraCliente.credito),
                joinedload(MovimentoCarteiraCliente.venda),
                joinedload(MovimentoCarteiraCliente.funcionario),
            )
            .filter(
                MovimentoCarteiraCliente.tenant_id == tenant_id,
                MovimentoCarteiraCliente.cliente_id == cliente_id,
            )
            .order_by(MovimentoCarteiraCliente.data_movimento.desc(), MovimentoCarteiraCliente.id.desc())
            .limit(max(int(limite or 100), 1))
            .all()
        )

    @staticmethod
    def listar_movimentos_carteira_por_venda(venda_id, tenant_id, tipo=None):
        query = (
            MovimentoCarteiraCliente.query
            .options(joinedload(MovimentoCarteiraCliente.credito))
            .filter(
                MovimentoCarteiraCliente.tenant_id == tenant_id,
                MovimentoCarteiraCliente.venda_id == venda_id,
            )
            .order_by(MovimentoCarteiraCliente.id.asc())
        )
        if tipo is not None:
            query = query.filter(MovimentoCarteiraCliente.tipo == tipo)
        return query.all()

    @staticmethod
    def listar_vendas_cliente(cliente_id, tenant_id, empresa_ids=None, limite=100):
        query = (
            Venda.query
            .options(
                joinedload(Venda.empresa),
                joinedload(Venda.funcionario),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
            )
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.cliente_id == cliente_id,
            )
            .order_by(Venda.data_venda.desc(), Venda.id.desc())
        )

        if empresa_ids is not None:
            query = query.filter(Venda.empresa_id.in_(empresa_ids))

        return query.limit(max(int(limite or 100), 1)).all()

    @staticmethod
    def listar_configuracoes(tenant_id, empresa_ids=None):
        query = (
            ConfiguracaoClienteEmpresa.query
            .options(joinedload(ConfiguracaoClienteEmpresa.empresa))
            .filter(ConfiguracaoClienteEmpresa.tenant_id == tenant_id)
            .order_by(ConfiguracaoClienteEmpresa.empresa_id.asc())
        )

        if empresa_ids is not None:
            query = query.filter(ConfiguracaoClienteEmpresa.empresa_id.in_(empresa_ids))

        return query.all()

    @staticmethod
    def buscar_configuracao_empresa(empresa_id, tenant_id):
        return (
            ConfiguracaoClienteEmpresa.query
            .options(joinedload(ConfiguracaoClienteEmpresa.empresa))
            .filter(
                ConfiguracaoClienteEmpresa.tenant_id == tenant_id,
                ConfiguracaoClienteEmpresa.empresa_id == empresa_id,
            )
            .first()
        )

    @staticmethod
    def listar_mensagens_cliente(cliente_id, tenant_id, limite=30):
        return (
            MensagemCliente.query
            .options(
                joinedload(MensagemCliente.empresa),
                joinedload(MensagemCliente.funcionario),
            )
            .filter(
                MensagemCliente.tenant_id == tenant_id,
                MensagemCliente.cliente_id == cliente_id,
            )
            .order_by(MensagemCliente.criado_em.desc(), MensagemCliente.id.desc())
            .limit(max(int(limite or 30), 1))
            .all()
        )

    @staticmethod
    def listar_vendas_por_cliente_ids(cliente_ids, tenant_id):
        if not cliente_ids:
            return []

        return (
            Venda.query
            .filter(
                Venda.tenant_id == tenant_id,
                Venda.cliente_id.in_(cliente_ids),
                Venda.status != StatusVenda.ABERTA,
            )
            .all()
        )

    @staticmethod
    def listar_movimentos_estoque_reversiveis(tenant_id, empresa_ids=None):
        query = (
            MovimentoEstoque.query
            .filter(
                MovimentoEstoque.tenant_id == tenant_id,
                MovimentoEstoque.revertido.is_(False),
            )
        )
        if empresa_ids is not None:
            query = query.filter(MovimentoEstoque.empresa_id.in_(empresa_ids))
        return query.all()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def flush():
        db.session.flush()

    @staticmethod
    def salvar():
        save()

    @staticmethod
    def rollback():
        db.session.rollback()
