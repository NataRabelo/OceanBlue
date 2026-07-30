from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.db import (
    BancoEmissor,
    Boleto,
    ConfiguracaoParcelamento,
    EventoBoleto,
    LancamentoFinanceiro,
    ParcelaBoleto,
    RegraJurosMulta,
    StatusBoleto,
    TipoFinanceiro,
)


class BoletoRepository:
    @staticmethod
    def listar_bancos_emissores(tenant_id, empresa_ids=None, empresa_id=None, ativo=None):
        query = BancoEmissor.query.filter(BancoEmissor.tenant_id == tenant_id)
        if empresa_ids is not None:
            query = query.filter(BancoEmissor.empresa_id.in_(empresa_ids))
        if empresa_id is not None:
            query = query.filter(BancoEmissor.empresa_id == empresa_id)
        if ativo is not None:
            query = query.filter(BancoEmissor.ativo.is_(ativo))
        return query.order_by(BancoEmissor.is_padrao.desc(), BancoEmissor.banco_nome.asc()).all()

    @staticmethod
    def buscar_banco_emissor(banco_id, tenant_id, empresa_id=None):
        query = BancoEmissor.query.filter(BancoEmissor.id == banco_id, BancoEmissor.tenant_id == tenant_id)
        if empresa_id is not None:
            query = query.filter(BancoEmissor.empresa_id == empresa_id)
        return query.first()

    @staticmethod
    def buscar_banco_padrao(tenant_id, empresa_id):
        return BancoEmissor.query.filter(
            BancoEmissor.tenant_id == tenant_id,
            BancoEmissor.empresa_id == empresa_id,
            BancoEmissor.is_padrao.is_(True),
            BancoEmissor.ativo.is_(True),
        ).first()

    @staticmethod
    def listar_configuracoes_parcelamento(tenant_id, empresa_ids=None, empresa_id=None, ativo=None):
        query = ConfiguracaoParcelamento.query.filter(ConfiguracaoParcelamento.tenant_id == tenant_id)
        if empresa_ids is not None:
            query = query.filter(ConfiguracaoParcelamento.empresa_id.in_(empresa_ids))
        if empresa_id is not None:
            query = query.filter(ConfiguracaoParcelamento.empresa_id == empresa_id)
        if ativo is not None:
            query = query.filter(ConfiguracaoParcelamento.ativo.is_(ativo))
        return query.order_by(ConfiguracaoParcelamento.id.desc()).all()

    @staticmethod
    def buscar_configuracao_parcelamento(config_id, tenant_id, empresa_id=None):
        query = ConfiguracaoParcelamento.query.filter(
            ConfiguracaoParcelamento.id == config_id,
            ConfiguracaoParcelamento.tenant_id == tenant_id,
        )
        if empresa_id is not None:
            query = query.filter(ConfiguracaoParcelamento.empresa_id == empresa_id)
        return query.first()

    @staticmethod
    def listar_regras_juros_multa(tenant_id, empresa_ids=None, empresa_id=None):
        query = RegraJurosMulta.query.filter(RegraJurosMulta.tenant_id == tenant_id)
        if empresa_ids is not None:
            query = query.filter(RegraJurosMulta.empresa_id.in_(empresa_ids))
        if empresa_id is not None:
            query = query.filter(RegraJurosMulta.empresa_id == empresa_id)
        return query.order_by(RegraJurosMulta.empresa_id.asc(), RegraJurosMulta.vigente_desde.desc()).all()

    @staticmethod
    def buscar_regra_vigente_atual(tenant_id, empresa_id, banco_emissor_id=None):
        query = RegraJurosMulta.query.filter(
            RegraJurosMulta.tenant_id == tenant_id,
            RegraJurosMulta.empresa_id == empresa_id,
            RegraJurosMulta.banco_emissor_id == banco_emissor_id,
            RegraJurosMulta.ativo.is_(True),
            RegraJurosMulta.vigente_ate.is_(None),
        )
        return query.order_by(RegraJurosMulta.vigente_desde.desc()).first()

    @staticmethod
    def buscar_regra_vigente_em(tenant_id, empresa_id, data_referencia, banco_emissor_id=None):
        return RegraJurosMulta.query.filter(
            RegraJurosMulta.tenant_id == tenant_id,
            RegraJurosMulta.empresa_id == empresa_id,
            RegraJurosMulta.banco_emissor_id == banco_emissor_id,
            RegraJurosMulta.ativo.is_(True),
            RegraJurosMulta.vigente_desde <= data_referencia,
            db.or_(RegraJurosMulta.vigente_ate.is_(None), RegraJurosMulta.vigente_ate > data_referencia),
        ).order_by(RegraJurosMulta.vigente_desde.desc()).first()

    @staticmethod
    def listar_boletos(tenant_id, empresa_ids=None, empresa_id=None, status=None, banco_emissor_id=None, limite=100):
        query = Boleto.query.options(
            joinedload(Boleto.cliente),
            joinedload(Boleto.empresa),
            joinedload(Boleto.banco_emissor),
        ).filter(Boleto.tenant_id == tenant_id)
        if empresa_ids is not None:
            query = query.filter(Boleto.empresa_id.in_(empresa_ids))
        if empresa_id is not None:
            query = query.filter(Boleto.empresa_id == empresa_id)
        if status is not None:
            status_enum = StatusBoleto(status) if isinstance(status, str) else status
            query = query.filter(Boleto.status == status_enum)
        if banco_emissor_id is not None:
            query = query.filter(Boleto.banco_emissor_id == banco_emissor_id)
        return query.order_by(Boleto.criado_em.desc(), Boleto.id.desc()).limit(max(int(limite or 100), 1)).all()

    @staticmethod
    def buscar_boleto(boleto_id, tenant_id, empresa_id=None):
        query = Boleto.query.options(
            joinedload(Boleto.parcelas),
            joinedload(Boleto.eventos),
            joinedload(Boleto.cliente),
            joinedload(Boleto.empresa),
            joinedload(Boleto.banco_emissor),
        ).filter(Boleto.id == boleto_id, Boleto.tenant_id == tenant_id)
        if empresa_id is not None:
            query = query.filter(Boleto.empresa_id == empresa_id)
        return query.first()

    @staticmethod
    def existe_numero_boleto(tenant_id, numero_boleto):
        return Boleto.query.filter(Boleto.tenant_id == tenant_id, Boleto.numero_boleto == numero_boleto).first() is not None

    @staticmethod
    def listar_boletos_vencidos(tenant_id, data_referencia, empresa_ids=None):
        query = Boleto.query.filter(
            Boleto.tenant_id == tenant_id,
            Boleto.data_vencimento < data_referencia,
            Boleto.status.in_([StatusBoleto.EMITIDO, StatusBoleto.PARCIALMENTE_PAGO]),
        )
        if empresa_ids is not None:
            query = query.filter(Boleto.empresa_id.in_(empresa_ids))
        return query.all()

    @staticmethod
    def listar_parcelas_vencidas(tenant_id, data_referencia, empresa_ids=None):
        query = ParcelaBoleto.query.join(Boleto, Boleto.id == ParcelaBoleto.boleto_id).filter(
            Boleto.tenant_id == tenant_id,
            ParcelaBoleto.data_vencimento < data_referencia,
            ParcelaBoleto.status.in_([StatusBoleto.EMITIDO, StatusBoleto.PARCIALMENTE_PAGO]),
        )
        if empresa_ids is not None:
            query = query.filter(Boleto.empresa_id.in_(empresa_ids))
        return query.all()

    @staticmethod
    def buscar_lancamento_boleto(tenant_id, boleto_id, parcela_boleto_id=None, tipo=TipoFinanceiro.ENTRADA):
        query = LancamentoFinanceiro.query.filter(
            LancamentoFinanceiro.tenant_id == tenant_id,
            LancamentoFinanceiro.boleto_id == boleto_id,
            LancamentoFinanceiro.tipo == tipo,
        )
        if parcela_boleto_id is None:
            query = query.filter(LancamentoFinanceiro.parcela_boleto_id.is_(None))
        else:
            query = query.filter(LancamentoFinanceiro.parcela_boleto_id == parcela_boleto_id)
        return query.first()

    @staticmethod
    def buscar_evento_recalculo_na_data(boleto_id, parcela_id, data_referencia):
        query = EventoBoleto.query.filter(
            EventoBoleto.boleto_id == boleto_id,
            db.func.date(EventoBoleto.criado_em) == data_referencia,
        )
        if parcela_id is None:
            query = query.filter(EventoBoleto.parcela_id.is_(None))
        else:
            query = query.filter(EventoBoleto.parcela_id == parcela_id)
        return query.first()

    @staticmethod
    def adicionar(obj):
        db.session.add(obj)

    @staticmethod
    def flush():
        db.session.flush()

    @staticmethod
    def salvar():
        db.session.commit()

    @staticmethod
    def rollback():
        db.session.rollback()
