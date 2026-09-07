from datetime import date, timedelta
import enum

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlalchemy.orm import validates

from app.extensions import db
from app.services.time_service import TimeService


class TipoEmpresa(enum.Enum):
    MATRIZ = "MATRIZ"
    FILIAL = "FILIAL"


class ModoVisualEmpresa(enum.Enum):
    MODERNO = "MODERNO"
    LEGADO = "LEGADO"


class TipoFinanceiro(enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class TipoCategoriaFinanceira(enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class TipoMovimentoEstoque(enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class MotivoMovimentoEstoque(enum.Enum):
    COMPRA = "COMPRA"
    VENDA = "VENDA"
    AJUSTE = "AJUSTE"
    PERDA = "PERDA"
    DEVOLUCAO = "DEVOLUCAO"
    TRANSFERENCIA = "TRANSFERENCIA"


class TipoOperacaoEnum(enum.Enum):
    VENDA = "VENDA"
    ENTRADA_ESTOQUE = "ENTRADA_ESTOQUE"
    AJUSTE_ESTOQUE = "AJUSTE_ESTOQUE"
    TRANSFERENCIA = "TRANSFERENCIA"


class TipoDesconto(enum.Enum):
    PERCENTUAL = "PERCENTUAL"
    VALOR = "VALOR"


class ModalidadePrecoVenda(enum.Enum):
    VAREJO = "VAREJO"
    ATACADO = "ATACADO"
    AUTOMATICO = "AUTOMATICO"


class StatusVenda(enum.Enum):
    ABERTA = "ABERTA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class TipoAdiantamentoFuncionario(enum.Enum):
    DINHEIRO = "DINHEIRO"
    PRODUTO = "PRODUTO"


class TipoPessoa(enum.Enum):
    FISICA = "FISICA"
    JURIDICA = "JURIDICA"


class CanalMensagemCliente(enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class AmbienteFiscal(enum.Enum):
    HOMOLOGACAO = "HOMOLOGACAO"
    PRODUCAO = "PRODUCAO"


class RegimeTributarioFiscal(enum.Enum):
    SIMPLES_NACIONAL = "SIMPLES_NACIONAL"
    LUCRO_PRESUMIDO = "LUCRO_PRESUMIDO"
    LUCRO_REAL = "LUCRO_REAL"


class StatusMensagemCliente(enum.Enum):
    PENDENTE = "PENDENTE"
    ENVIADO = "ENVIADO"
    ERRO = "ERRO"


class StatusNotaFiscal(enum.Enum):
    PENDENTE = "PENDENTE"
    VALIDACAO_ERRO = "VALIDACAO_ERRO"
    PRONTA_PARA_EMISSAO = "PRONTA_PARA_EMISSAO"
    XML_GERADO = "XML_GERADO"
    XML_ASSINADO = "XML_ASSINADO"
    ENVIADA_AUTORIZACAO = "ENVIADA_AUTORIZACAO"
    EMITIDA = "EMITIDA"
    REJEITADA = "REJEITADA"
    CANCELADA = "CANCELADA"
    INUTILIZADA = "INUTILIZADA"
    CONTINGENCIA = "CONTINGENCIA"


class StatusOficialNotaFiscal(enum.Enum):
    NAO_ENVIADA = "NAO_ENVIADA"
    EM_PROCESSAMENTO = "EM_PROCESSAMENTO"
    AUTORIZADA = "AUTORIZADA"
    REJEITADA = "REJEITADA"
    CANCELADA = "CANCELADA"
    INUTILIZADA = "INUTILIZADA"
    CONTINGENCIA = "CONTINGENCIA"


class LayoutArquivoBoleto(enum.Enum):
    CNAB240 = "CNAB240"
    CNAB240_API = "CNAB240_API"
    CNAB400 = "CNAB400"


class AmbienteBoleto(enum.Enum):
    sandbox = "sandbox"
    producao = "producao"


class RegraDistribuicaoParcelamento(enum.Enum):
    proporcional = "proporcional"
    manual = "manual"


class TipoMultaBoleto(enum.Enum):
    percentual = "percentual"
    fixo = "fixo"
    nenhum = "nenhum"


class TipoJurosBoleto(enum.Enum):
    diario = "diario"
    mensal = "mensal"
    nenhum = "nenhum"


class BaseCalculoJurosMulta(enum.Enum):
    valor_nominal = "valor_nominal"
    valor_restante = "valor_restante"


class StatusBoleto(enum.Enum):
    PENDENTE = "PENDENTE"
    EMITIDO = "EMITIDO"
    VENCIDO = "VENCIDO"
    PARCIALMENTE_PAGO = "PARCIALMENTE_PAGO"
    PAGO = "PAGO"
    CANCELADO = "CANCELADO"
    ESTORNADO = "ESTORNADO"
    BAIXA_MANUAL = "BAIXA_MANUAL"


class StatusBancarioBoleto(enum.Enum):
    NAO_REGISTRADO = "NAO_REGISTRADO"
    REGISTRO_SOLICITADO = "REGISTRO_SOLICITADO"
    REGISTRADO = "REGISTRADO"
    REJEITADO = "REJEITADO"
    PAGO = "PAGO"
    BAIXADO = "BAIXADO"
    CANCELADO = "CANCELADO"


class TipoEventoBoleto(enum.Enum):
    EMISSAO = "EMISSAO"
    REGISTRO_SOLICITADO = "REGISTRO_SOLICITADO"
    REGISTRO_BANCARIO = "REGISTRO_BANCARIO"
    REGISTRO_REJEITADO = "REGISTRO_REJEITADO"
    WEBHOOK_BANCARIO = "WEBHOOK_BANCARIO"
    VENCIMENTO = "VENCIMENTO"
    PAGAMENTO = "PAGAMENTO"
    PAGAMENTO_PARCIAL = "PAGAMENTO_PARCIAL"
    ESTORNO = "ESTORNO"
    BAIXA_MANUAL = "BAIXA_MANUAL"
    RECALCULO_JUROS = "RECALCULO_JUROS"
    ALTERACAO_REGRA = "ALTERACAO_REGRA"


class TipoMovimentoCarteiraCliente(enum.Enum):
    CREDITO = "CREDITO"
    DEBITO = "DEBITO"
    ESTORNO = "ESTORNO"
    EXPIRACAO = "EXPIRACAO"
    AJUSTE = "AJUSTE"


class ModeloBase(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive, onupdate=TimeService.now_utc_naive)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)


class Tenant(db.Model):
    __tablename__ = "tenants"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False, unique=True)
    plano_codigo = db.Column(db.String(40), nullable=False, default="starter")
    assinatura_status = db.Column(db.String(30), nullable=False, default="trial")
    limite_empresas = db.Column(db.Integer, nullable=False, default=1)
    limite_funcionarios = db.Column(db.Integer, nullable=False, default=5)
    limite_produtos = db.Column(db.Integer, nullable=False, default=500)
    limite_vendas_mes = db.Column(db.Integer, nullable=False, default=1500)
    trial_ate = db.Column(db.Date, nullable=True, default=lambda: TimeService.today_br() + timedelta(days=14))
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive, onupdate=TimeService.now_utc_naive)

    empresas = db.relationship("Empresa", backref="tenant", lazy=True, cascade="all, delete-orphan")
    funcionarios = db.relationship("Funcionario", backref="tenant", lazy=True, cascade="all, delete-orphan")
    produtos = db.relationship("Produto", backref="tenant", lazy=True, cascade="all, delete-orphan")
    roles = db.relationship("Role", backref="tenant", lazy=True, cascade="all, delete-orphan")
    permissions = db.relationship("Permission", backref="tenant", lazy=True, cascade="all, delete-orphan")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=True, index=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=True, index=True)
    actor_scope = db.Column(db.String(30), nullable=True)
    actor_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(80), nullable=False)
    entity_type = db.Column(db.String(80), nullable=True)
    entity_id = db.Column(db.String(80), nullable=True)
    status = db.Column(db.String(30), nullable=False, default="SUCCESS")
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(80), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    request_path = db.Column(db.String(255), nullable=True)
    request_method = db.Column(db.String(10), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    tenant = db.relationship("Tenant", backref=db.backref("audit_logs", lazy=True))

    __table_args__ = (
        Index("ix_audit_logs_tenant_action_created", "tenant_id", "action", "criado_em"),
        Index("ix_audit_logs_tenant_entity", "tenant_id", "entity_type", "entity_id"),
    )


class PlatformOwner(db.Model):
    __tablename__ = "platform_owners"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    usuario = db.Column(db.String(80), nullable=False, unique=True)
    senha_hash = db.Column(db.String(255), nullable=False)
    session_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    ativo = db.Column(db.Boolean, nullable=False, default=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    atualizado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive, onupdate=TimeService.now_utc_naive)


class Empresa(ModeloBase):
    __tablename__ = "empresas"

    cnpj = db.Column(db.String(18), nullable=False)
    razao_social = db.Column(db.String(180), nullable=False)
    nome_fantasia = db.Column(db.String(180), nullable=False)
    tipo_empresa = db.Column(db.Enum(TipoEmpresa), nullable=False)
    visual_modo = db.Column(db.Enum(ModoVisualEmpresa), nullable=False, default=ModoVisualEmpresa.MODERNO)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "cnpj", name="uq_empresa_tenant_cnpj"),
        UniqueConstraint("tenant_id", "nome_fantasia", name="uq_empresa_tenant_nome_fantasia"),
    )


class Role(ModeloBase):
    __tablename__ = "role"

    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(80), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "nome", name="uq_role_tenant_nome"),
        UniqueConstraint("tenant_id", "codigo", name="uq_role_tenant_codigo"),
    )


class Permission(ModeloBase):
    __tablename__ = "permissions"

    nome = db.Column(db.String(120), nullable=False)
    codigo = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_permission_tenant_codigo"),
    )


class RolePermission(ModeloBase):
    __tablename__ = "role_permission"

    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey("permissions.id"), nullable=False)

    role = db.relationship(
        "Role",
        backref=db.backref("permissions_links", lazy=True, cascade="all, delete-orphan")
    )
    permission = db.relationship(
        "Permission",
        backref=db.backref("roles_links", lazy=True, cascade="all, delete-orphan")
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "role_id", "permission_id", name="uq_role_permission"),
    )


class Funcionario(ModeloBase):
    __tablename__ = "funcionarios"

    role_id = db.Column(db.Integer, db.ForeignKey("role.id"), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    cpf = db.Column(db.String(14), nullable=False)
    usuario = db.Column(db.String(80), nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    session_version = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    salario = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    meta = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    role = db.relationship("Role", backref=db.backref("funcionarios", lazy=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "cpf", name="uq_funcionario_tenant_cpf"),
        UniqueConstraint("tenant_id", "usuario", name="uq_funcionario_tenant_usuario"),
    )


class FuncionarioEmpresa(ModeloBase):
    __tablename__ = "funcionarios_empresa"

    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    funcionario = db.relationship(
        "Funcionario",
        backref=db.backref("empresas_vinculadas", lazy=True, cascade="all, delete-orphan")
    )
    empresa = db.relationship(
        "Empresa",
        backref=db.backref("funcionarios_vinculados", lazy=True, cascade="all, delete-orphan")
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "funcionario_id", "empresa_id", name="uq_funcionario_empresa"),
    )


class Cliente(ModeloBase):
    __tablename__ = "clientes"

    nome = db.Column(db.String(150), nullable=False)
    documento = db.Column(db.String(20), nullable=True)
    tipo_pessoa = db.Column(db.Enum(TipoPessoa), nullable=False, default=TipoPessoa.FISICA)
    email = db.Column(db.String(150), nullable=True)
    telefone = db.Column(db.String(20), nullable=True)
    whatsapp = db.Column(db.String(20), nullable=True)
    data_nascimento = db.Column(db.Date, nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    aceita_email = db.Column(db.Boolean, nullable=False, default=False)
    aceita_sms = db.Column(db.Boolean, nullable=False, default=False)
    aceita_whatsapp = db.Column(db.Boolean, nullable=False, default=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "documento", name="uq_cliente_tenant_documento"),
        Index("ix_cliente_tenant_nome", "tenant_id", "nome"),
    )


class CarteiraCliente(ModeloBase):
    __tablename__ = "carteiras_cliente"

    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    saldo_disponivel = db.Column(db.Numeric(12, 2), nullable=False, default=0)

    cliente = db.relationship(
        "Cliente",
        backref=db.backref("carteira", uselist=False, lazy=True, cascade="all, delete-orphan"),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "cliente_id", name="uq_carteira_cliente_tenant"),
        CheckConstraint("saldo_disponivel >= 0", name="ck_carteira_cliente_saldo_non_negative"),
    )


class CreditoCashbackCliente(ModeloBase):
    __tablename__ = "creditos_cashback_cliente"

    carteira_id = db.Column(db.Integer, db.ForeignKey("carteiras_cliente.id"), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    venda_origem_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    valor_original = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    saldo_disponivel = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    data_expiracao = db.Column(db.Date, nullable=False)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    expirado_em = db.Column(db.DateTime, nullable=True)
    observacao = db.Column(db.Text, nullable=True)

    carteira = db.relationship("CarteiraCliente", backref=db.backref("creditos", lazy=True, cascade="all, delete-orphan"))
    cliente = db.relationship("Cliente", backref=db.backref("creditos_cashback", lazy=True))
    empresa = db.relationship("Empresa", backref=db.backref("creditos_cashback", lazy=True))
    venda_origem = db.relationship("Venda", foreign_keys=[venda_origem_id], backref=db.backref("creditos_cashback", lazy=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "venda_origem_id", name="uq_credito_cashback_tenant_venda_origem"),
        CheckConstraint("valor_original >= 0", name="ck_credito_cashback_valor_original_non_negative"),
        CheckConstraint("saldo_disponivel >= 0", name="ck_credito_cashback_saldo_non_negative"),
        CheckConstraint("saldo_disponivel <= valor_original", name="ck_credito_cashback_saldo_lte_original"),
        Index("ix_credito_cashback_tenant_cliente_expiracao", "tenant_id", "cliente_id", "data_expiracao"),
    )


class MovimentoCarteiraCliente(ModeloBase):
    __tablename__ = "movimentos_carteira_cliente"

    carteira_id = db.Column(db.Integer, db.ForeignKey("carteiras_cliente.id"), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    credito_id = db.Column(db.Integer, db.ForeignKey("creditos_cashback_cliente.id"), nullable=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=True)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    tipo = db.Column(db.Enum(TipoMovimentoCarteiraCliente), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    data_movimento = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    carteira = db.relationship("CarteiraCliente", backref=db.backref("movimentos", lazy=True, cascade="all, delete-orphan"))
    cliente = db.relationship("Cliente", backref=db.backref("movimentos_carteira", lazy=True))
    credito = db.relationship("CreditoCashbackCliente", backref=db.backref("movimentos", lazy=True))
    venda = db.relationship("Venda", backref=db.backref("movimentos_carteira", lazy=True))
    funcionario = db.relationship("Funcionario", backref=db.backref("movimentos_carteira", lazy=True))

    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_movimento_carteira_valor_positive"),
        Index("ix_movimento_carteira_tenant_cliente_data", "tenant_id", "cliente_id", "data_movimento"),
    )


class CategoriaProduto(ModeloBase):
    __tablename__ = "categorias_produto"

    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "nome", name="uq_categoria_produto_tenant_nome"),
    )


class Produto(ModeloBase):
    __tablename__ = "produtos"

    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias_produto.id"), nullable=True)
    criado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.Text, nullable=True)
    possui_ncm = db.Column(db.Boolean, nullable=False, default=False)
    ncm = db.Column(db.String(20), nullable=True)
    codigo_barras = db.Column(db.String(60), nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    categoria = db.relationship("CategoriaProduto", backref=db.backref("produtos", lazy=True))
    criado_por = db.relationship("Funcionario", backref=db.backref("produtos_criados", lazy=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "nome", name="uq_produto_tenant_nome"),
        UniqueConstraint("tenant_id", "codigo_barras", name="uq_produto_tenant_codigo_barras"),
        CheckConstraint("possui_ncm = FALSE OR ncm IS NOT NULL", name="ck_produto_ncm_flag"),
    )

    @validates("ncm")
    def validar_ncm(self, key, value):
        if self.possui_ncm and not value:
            raise ValueError("Produto com possui_ncm=True deve ter NCM.")
        return value


class ProdutoEmpresa(ModeloBase):
    __tablename__ = "produtos_empresa"

    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    estoque_atual = db.Column(db.Integer, nullable=False, default=0)
    estoque_minimo = db.Column(db.Integer, nullable=False, default=0)
    valor_compra = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_venda = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_varejo = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_atacado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    quantidade_minima_atacado = db.Column(db.Integer, nullable=False, default=1)
    data_validade = db.Column(db.Date, nullable=True)
    ultimo_alerta_estoque_status = db.Column(db.String(30), nullable=True)
    ultimo_alerta_estoque_em = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    produto = db.relationship("Produto", backref=db.backref("dados_por_empresa", lazy=True, cascade="all, delete-orphan"))
    empresa = db.relationship("Empresa", backref=db.backref("produtos_empresa", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        UniqueConstraint("tenant_id", "produto_id", "empresa_id", name="uq_produto_empresa"),
        CheckConstraint("estoque_atual >= 0", name="ck_produto_empresa_estoque_atual_non_negative"),
        CheckConstraint("estoque_minimo >= 0", name="ck_produto_empresa_estoque_minimo_non_negative"),
        CheckConstraint("valor_compra >= 0", name="ck_produto_empresa_valor_compra_non_negative"),
        CheckConstraint("valor_venda >= 0", name="ck_produto_empresa_valor_venda_non_negative"),
        CheckConstraint("valor_varejo >= 0", name="ck_produto_empresa_valor_varejo_non_negative"),
        CheckConstraint("valor_atacado >= 0", name="ck_produto_empresa_valor_atacado_non_negative"),
        CheckConstraint("quantidade_minima_atacado >= 1", name="ck_produto_empresa_qtd_min_atacado_positive"),
    )


class FormaPagamento(ModeloBase):
    __tablename__ = "formas_pagamento"

    nome = db.Column(db.String(80), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "nome", name="uq_forma_pagamento_tenant_nome"),
    )


class CategoriaFinanceira(ModeloBase):
    __tablename__ = "categorias_financeiras"

    nome = db.Column(db.String(100), nullable=False)
    tipo_categoria = db.Column(db.Enum(TipoCategoriaFinanceira), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "nome", "tipo_categoria", name="uq_categoria_financeira_tenant_nome_tipo"),
    )


class TipoOperacao(ModeloBase):
    __tablename__ = "tipos_operacao"

    nome = db.Column(db.String(80), nullable=False)
    codigo = db.Column(db.String(30), nullable=False)
    tipo_operacao = db.Column(db.Enum(TipoOperacaoEnum), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_tipo_operacao_tenant_codigo"),
        UniqueConstraint("tenant_id", "nome", name="uq_tipo_operacao_tenant_nome"),
    )


class Cupom(ModeloBase):
    __tablename__ = "cupons"

    criado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    nome = db.Column(db.String(100), nullable=False)
    codigo = db.Column(db.String(60), nullable=False)
    data_validade = db.Column(db.Date, nullable=False)
    tipo_desconto = db.Column(db.Enum(TipoDesconto), nullable=False)
    valor_desconto = db.Column(db.Numeric(12, 2), nullable=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    criado_por = db.relationship("Funcionario", backref=db.backref("cupons_criados", lazy=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "codigo", name="uq_cupom_tenant_codigo"),
    )


class AdiantamentoFuncionario(ModeloBase):
    __tablename__ = "adiantamentos_funcionario"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=True)
    forma_pagamento_id = db.Column(db.Integer, db.ForeignKey("formas_pagamento.id"), nullable=False)
    lancamento_financeiro_id = db.Column(db.Integer, db.ForeignKey("lancamentos_financeiros.id"), nullable=True)
    movimento_estoque_id = db.Column(db.Integer, db.ForeignKey("movimentos_estoque.id"), nullable=True)
    tipo_adiantamento = db.Column(db.Enum(TipoAdiantamentoFuncionario), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    quantidade = db.Column(db.Integer, nullable=True)
    valor_unitario = db.Column(db.Numeric(12, 2), nullable=True)
    valor_total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    data_adiantamento = db.Column(db.Date, nullable=False, default=date.today)
    competencia = db.Column(db.Date, nullable=False, default=date.today)
    observacao = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("adiantamentos_funcionario", lazy=True))
    funcionario = db.relationship("Funcionario", backref=db.backref("adiantamentos", lazy=True))
    produto = db.relationship("Produto", backref=db.backref("adiantamentos", lazy=True))
    forma_pagamento = db.relationship("FormaPagamento", backref=db.backref("adiantamentos", lazy=True))
    lancamento_financeiro = db.relationship("LancamentoFinanceiro", backref=db.backref("adiantamentos", lazy=True))
    movimento_estoque = db.relationship("MovimentoEstoque", backref=db.backref("adiantamentos", lazy=True))

    __table_args__ = (
        CheckConstraint("quantidade IS NULL OR quantidade > 0", name="ck_adiantamento_quantidade_positive"),
        CheckConstraint("valor_unitario IS NULL OR valor_unitario >= 0", name="ck_adiantamento_valor_unitario_non_negative"),
        CheckConstraint("valor_total >= 0", name="ck_adiantamento_valor_total_non_negative"),
        Index("ix_adiantamento_tenant_funcionario_competencia", "tenant_id", "funcionario_id", "competencia"),
    )


class MovimentoEstoque(ModeloBase):
    __tablename__ = "movimentos_estoque"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=True)
    item_venda_id = db.Column(db.Integer, db.ForeignKey("itens_venda.id"), nullable=True)
    movimento_origem_id = db.Column(db.Integer, db.ForeignKey("movimentos_estoque.id"), nullable=True)
    tipo_movimento = db.Column(db.Enum(TipoMovimentoEstoque), nullable=False)
    motivo = db.Column(db.Enum(MotivoMovimentoEstoque), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Numeric(12, 2), nullable=True)
    valor_total = db.Column(db.Numeric(12, 2), nullable=True)
    revertido = db.Column(db.Boolean, nullable=False, default=False)
    cancelado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    motivo_cancelamento = db.Column(db.Text, nullable=True)
    observacao = db.Column(db.Text, nullable=True)
    data_movimento = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    empresa = db.relationship("Empresa", backref=db.backref("movimentos_estoque", lazy=True))
    produto = db.relationship("Produto", backref=db.backref("movimentos_estoque", lazy=True))
    funcionario = db.relationship("Funcionario", foreign_keys=[funcionario_id], backref=db.backref("movimentos_estoque", lazy=True))
    cancelado_por = db.relationship(
        "Funcionario",
        foreign_keys=[cancelado_por_funcionario_id],
        backref=db.backref("movimentos_estoque_cancelados", lazy=True),
    )
    venda = db.relationship("Venda", backref=db.backref("movimentos_estoque", lazy=True))
    item_venda = db.relationship("ItemVenda", backref=db.backref("movimentos_estoque", lazy=True))

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_movimento_estoque_quantidade_positive"),
        CheckConstraint("valor_unitario IS NULL OR valor_unitario >= 0", name="ck_movimento_estoque_valor_unitario_non_negative"),
        CheckConstraint("valor_total IS NULL OR valor_total >= 0", name="ck_movimento_estoque_valor_total_non_negative"),
        Index("ix_mov_estoque_tenant_empresa_produto", "tenant_id", "empresa_id", "produto_id"),
    )


class Venda(ModeloBase):
    __tablename__ = "vendas"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=True)
    tipo_operacao_id = db.Column(db.Integer, db.ForeignKey("tipos_operacao.id"), nullable=False)
    cupom_id = db.Column(db.Integer, db.ForeignKey("cupons.id"), nullable=True)
    cancelado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    numero_unico = db.Column(db.String(50), nullable=False)
    status = db.Column(db.Enum(StatusVenda), nullable=False, default=StatusVenda.ABERTA)
    modalidade_preco = db.Column(
        db.Enum(ModalidadePrecoVenda),
        nullable=False,
        default=ModalidadePrecoVenda.VAREJO,
    )
    subtotal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    desconto = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cashback_ativado = db.Column(db.Boolean, nullable=False, default=True)
    cashback_utilizado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cashback_gerado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cashback_percentual_aplicado = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    valor_cancelado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    total = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    data_venda = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    observacao = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("vendas", lazy=True))
    funcionario = db.relationship("Funcionario", foreign_keys=[funcionario_id], backref=db.backref("vendas", lazy=True))
    cliente = db.relationship("Cliente", backref=db.backref("vendas", lazy=True))
    tipo_operacao = db.relationship("TipoOperacao", backref=db.backref("vendas", lazy=True))
    cupom = db.relationship("Cupom", backref=db.backref("vendas", lazy=True))
    cancelado_por = db.relationship(
        "Funcionario",
        foreign_keys=[cancelado_por_funcionario_id],
        backref=db.backref("vendas_canceladas", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "empresa_id", "numero_unico", name="uq_venda_tenant_empresa_numero_unico"),
        CheckConstraint("subtotal >= 0", name="ck_venda_subtotal_non_negative"),
        CheckConstraint("desconto >= 0", name="ck_venda_desconto_non_negative"),
        CheckConstraint("cashback_utilizado >= 0", name="ck_venda_cashback_utilizado_non_negative"),
        CheckConstraint("cashback_gerado >= 0", name="ck_venda_cashback_gerado_non_negative"),
        CheckConstraint("cashback_percentual_aplicado >= 0 AND cashback_percentual_aplicado <= 100", name="ck_venda_cashback_percentual_range"),
        CheckConstraint("valor_cancelado >= 0", name="ck_venda_valor_cancelado_non_negative"),
        CheckConstraint("total >= 0", name="ck_venda_total_non_negative"),
        Index("ix_venda_tenant_empresa_data", "tenant_id", "empresa_id", "data_venda"),
    )


class ItemVenda(ModeloBase):
    __tablename__ = "itens_venda"

    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)
    cancelado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    modalidade_preco_aplicada = db.Column(
        db.Enum(ModalidadePrecoVenda),
        nullable=False,
        default=ModalidadePrecoVenda.VAREJO,
    )
    quantidade = db.Column(db.Integer, nullable=False)
    quantidade_cancelada = db.Column(db.Integer, nullable=False, default=0)
    valor_unitario = db.Column(db.Numeric(12, 2), nullable=False)
    valor_total = db.Column(db.Numeric(12, 2), nullable=False)
    valor_cancelado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cancelado_em = db.Column(db.DateTime, nullable=True)
    motivo_cancelamento = db.Column(db.Text, nullable=True)

    venda = db.relationship("Venda", backref=db.backref("itens", lazy=True, cascade="all, delete-orphan"))
    produto = db.relationship("Produto", backref=db.backref("itens_venda", lazy=True))
    cancelado_por = db.relationship(
        "Funcionario",
        foreign_keys=[cancelado_por_funcionario_id],
        backref=db.backref("itens_venda_cancelados", lazy=True),
    )

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="ck_item_venda_quantidade_positive"),
        CheckConstraint("quantidade_cancelada >= 0", name="ck_item_venda_quantidade_cancelada_non_negative"),
        CheckConstraint("quantidade_cancelada <= quantidade", name="ck_item_venda_quantidade_cancelada_lte_quantidade"),
        CheckConstraint("valor_unitario >= 0", name="ck_item_venda_valor_unitario_non_negative"),
        CheckConstraint("valor_total >= 0", name="ck_item_venda_valor_total_non_negative"),
        CheckConstraint("valor_cancelado >= 0", name="ck_item_venda_valor_cancelado_non_negative"),
        CheckConstraint("valor_cancelado <= valor_total", name="ck_item_venda_valor_cancelado_lte_total"),
    )


class PagamentoVenda(ModeloBase):
    __tablename__ = "pagamentos_venda"

    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    forma_pagamento_id = db.Column(db.Integer, db.ForeignKey("formas_pagamento.id"), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    comprovante = db.Column(db.String(120), nullable=True)

    venda = db.relationship("Venda", backref=db.backref("pagamentos", lazy=True, cascade="all, delete-orphan"))
    forma_pagamento = db.relationship("FormaPagamento", backref=db.backref("pagamentos_venda", lazy=True))

    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_pagamento_venda_valor_non_negative"),
    )


class LancamentoFinanceiro(ModeloBase):
    __tablename__ = "lancamentos_financeiros"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias_financeiras.id"), nullable=False)
    forma_pagamento_id = db.Column(db.Integer, db.ForeignKey("formas_pagamento.id"), nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=True)
    item_venda_id = db.Column(db.Integer, db.ForeignKey("itens_venda.id"), nullable=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey("boletos.id"), nullable=True)
    parcela_boleto_id = db.Column(db.Integer, db.ForeignKey("parcelas_boleto.id"), nullable=True)
    lancamento_origem_id = db.Column(db.Integer, db.ForeignKey("lancamentos_financeiros.id"), nullable=True)
    tipo = db.Column(db.Enum(TipoFinanceiro), nullable=False)
    descricao = db.Column(db.String(255), nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=False)
    revertido = db.Column(db.Boolean, nullable=False, default=False)
    data_lancamento = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    data_competencia = db.Column(db.Date, nullable=True)
    observacao = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("lancamentos_financeiros", lazy=True))
    funcionario = db.relationship("Funcionario", backref=db.backref("lancamentos_financeiros", lazy=True))
    categoria = db.relationship("CategoriaFinanceira", backref=db.backref("lancamentos_financeiros", lazy=True))
    forma_pagamento = db.relationship("FormaPagamento", backref=db.backref("lancamentos_financeiros", lazy=True))
    venda = db.relationship("Venda", backref=db.backref("lancamentos_financeiros", lazy=True))
    item_venda = db.relationship("ItemVenda", backref=db.backref("lancamentos_financeiros", lazy=True))
    boleto = db.relationship("Boleto", backref=db.backref("lancamentos_financeiros", lazy=True), foreign_keys=[boleto_id])
    parcela_boleto = db.relationship("ParcelaBoleto", backref=db.backref("lancamentos_financeiros", lazy=True), foreign_keys=[parcela_boleto_id])

    __table_args__ = (
        CheckConstraint("valor >= 0", name="ck_lancamento_financeiro_valor_non_negative"),
        Index("ix_financeiro_tenant_empresa_data", "tenant_id", "empresa_id", "data_lancamento"),
        Index("ix_financeiro_tenant_boleto_parcela", "tenant_id", "boleto_id", "parcela_boleto_id"),
    )


class BancoEmissor(ModeloBase):
    __tablename__ = "bancos_emissores"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    banco_codigo = db.Column(db.String(20), nullable=False)
    banco_nome = db.Column(db.String(120), nullable=False)
    convenio = db.Column(db.String(80), nullable=True)
    carteira = db.Column(db.String(30), nullable=False)
    variacao_carteira = db.Column(db.String(30), nullable=True)
    agencia = db.Column(db.String(30), nullable=False)
    agencia_dv = db.Column(db.String(5), nullable=True)
    conta = db.Column(db.String(30), nullable=False)
    conta_dv = db.Column(db.String(5), nullable=True)
    codigo_cedente = db.Column(db.String(60), nullable=False)
    especie_documento = db.Column(db.String(10), nullable=False, default="DM")
    layout_arquivo = db.Column(db.Enum(LayoutArquivoBoleto), nullable=False, default=LayoutArquivoBoleto.CNAB400)
    ambiente = db.Column(db.Enum(AmbienteBoleto), nullable=False, default=AmbienteBoleto.sandbox)
    credenciais_api_ref = db.Column(db.String(255), nullable=True)
    is_padrao = db.Column(db.Boolean, nullable=False, default=False)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship("Empresa", backref=db.backref("bancos_emissores", lazy=True))

    __table_args__ = (
        Index("ix_banco_emissor_tenant_empresa", "tenant_id", "empresa_id"),
    )


class ConfiguracaoParcelamento(ModeloBase):
    __tablename__ = "configuracoes_parcelamento"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    banco_emissor_id = db.Column(db.Integer, db.ForeignKey("bancos_emissores.id"), nullable=True)
    numero_min_parcelas = db.Column(db.Integer, nullable=False, default=1)
    numero_max_parcelas = db.Column(db.Integer, nullable=False)
    intervalo_dias_padrao = db.Column(db.Integer, nullable=False, default=30)
    permite_intervalo_customizado = db.Column(db.Boolean, nullable=False, default=False)
    dia_fixo_vencimento = db.Column(db.Integer, nullable=True)
    valor_minimo_por_parcela = db.Column(db.Numeric(12, 2), nullable=False)
    regra_distribuicao = db.Column(
        db.Enum(RegraDistribuicaoParcelamento),
        nullable=False,
        default=RegraDistribuicaoParcelamento.proporcional,
    )
    arredondamento_ultima_parcela = db.Column(db.Boolean, nullable=False, default=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship("Empresa", backref=db.backref("configuracoes_parcelamento", lazy=True))
    banco_emissor = db.relationship("BancoEmissor", backref=db.backref("configuracoes_parcelamento", lazy=True))

    __table_args__ = (
        CheckConstraint("numero_min_parcelas >= 1", name="ck_config_parcelamento_min_positive"),
        CheckConstraint("numero_max_parcelas >= numero_min_parcelas", name="ck_config_parcelamento_max_gte_min"),
        CheckConstraint("intervalo_dias_padrao >= 1", name="ck_config_parcelamento_intervalo_positive"),
        CheckConstraint("dia_fixo_vencimento IS NULL OR (dia_fixo_vencimento >= 1 AND dia_fixo_vencimento <= 28)", name="ck_config_parcelamento_dia_fixo_range"),
        CheckConstraint("valor_minimo_por_parcela >= 0", name="ck_config_parcelamento_valor_minimo_non_negative"),
        Index("ix_config_parcelamento_tenant_empresa", "tenant_id", "empresa_id"),
    )


class RegraJurosMulta(ModeloBase):
    __tablename__ = "regras_juros_multa"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    banco_emissor_id = db.Column(db.Integer, db.ForeignKey("bancos_emissores.id"), nullable=True)
    tipo_multa = db.Column(db.Enum(TipoMultaBoleto), nullable=False, default=TipoMultaBoleto.nenhum)
    percentual_multa = db.Column(db.Numeric(8, 4), nullable=True)
    valor_fixo_multa = db.Column(db.Numeric(12, 2), nullable=True)
    tipo_juros = db.Column(db.Enum(TipoJurosBoleto), nullable=False, default=TipoJurosBoleto.nenhum)
    percentual_juros = db.Column(db.Numeric(8, 4), nullable=True)
    dias_carencia = db.Column(db.Integer, nullable=False, default=0)
    base_calculo = db.Column(db.Enum(BaseCalculoJurosMulta), nullable=False, default=BaseCalculoJurosMulta.valor_restante)
    percentual_maximo_teto = db.Column(db.Numeric(8, 4), nullable=False)
    vigente_desde = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    vigente_ate = db.Column(db.DateTime, nullable=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship("Empresa", backref=db.backref("regras_juros_multa", lazy=True))
    banco_emissor = db.relationship("BancoEmissor", backref=db.backref("regras_juros_multa", lazy=True))

    __table_args__ = (
        CheckConstraint("dias_carencia >= 0", name="ck_regra_juros_carencia_non_negative"),
        CheckConstraint("percentual_maximo_teto >= 0", name="ck_regra_juros_teto_non_negative"),
        Index("ix_regra_juros_tenant_empresa_vigencia", "tenant_id", "empresa_id", "banco_emissor_id", "vigente_desde", "vigente_ate"),
    )


class ConfiguracaoAsaasEmpresa(ModeloBase):
    __tablename__ = "configuracoes_asaas_empresa"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    ambiente = db.Column(db.String(20), nullable=False, default="sandbox")
    api_key = db.Column(db.Text, nullable=True)
    wallet_id = db.Column(db.String(120), nullable=True)
    provider_codigo = db.Column(db.String(80), nullable=False, default="asaas")
    status_configuracao = db.Column(db.String(30), nullable=False, default="PENDENTE")
    ultima_validacao_em = db.Column(db.DateTime, nullable=True)
    ultima_validacao_status = db.Column(db.String(30), nullable=True)
    ultima_validacao_mensagem = db.Column(db.Text, nullable=True)
    webhook_url = db.Column(db.String(255), nullable=True)
    webhook_auth_token = db.Column(db.Text, nullable=True)
    webhook_ativo = db.Column(db.Boolean, nullable=False, default=False)
    dias_apos_vencimento_cancelamento = db.Column(db.Integer, nullable=True)
    notificacoes_desabilitadas = db.Column(db.Boolean, nullable=False, default=True)
    ativo = db.Column(db.Boolean, nullable=False, default=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("configuracao_asaas", uselist=False, lazy=True, cascade="all, delete-orphan"),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "empresa_id", name="uq_config_asaas_empresa_tenant"),
        CheckConstraint("ambiente IN ('sandbox', 'producao')", name="ck_config_asaas_ambiente"),
        Index("ix_config_asaas_tenant_empresa", "tenant_id", "empresa_id"),
    )


class Boleto(ModeloBase):
    __tablename__ = "boletos"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=True)
    banco_emissor_id = db.Column(db.Integer, db.ForeignKey("bancos_emissores.id"), nullable=False)
    configuracao_parcelamento_id = db.Column(db.Integer, db.ForeignKey("configuracoes_parcelamento.id"), nullable=True)
    numero_boleto = db.Column(db.String(60), nullable=False)
    nosso_numero = db.Column(db.String(80), nullable=True)
    status = db.Column(db.Enum(StatusBoleto), nullable=False, default=StatusBoleto.PENDENTE)
    status_bancario = db.Column(db.Enum(StatusBancarioBoleto), nullable=False, default=StatusBancarioBoleto.NAO_REGISTRADO)
    provider_codigo = db.Column(db.String(80), nullable=True)
    ambiente_bancario = db.Column(db.String(30), nullable=False, default="HOMOLOGACAO")
    idempotency_key_registro = db.Column(db.String(120), nullable=True)
    registro_bancario_id = db.Column(db.String(120), nullable=True)
    cliente_externo_id = db.Column(db.String(120), nullable=True)
    protocolo_registro = db.Column(db.String(120), nullable=True)
    mensagem_retorno_banco = db.Column(db.Text, nullable=True)
    registrado_em = db.Column(db.DateTime, nullable=True)
    ultimo_retorno_bancario_em = db.Column(db.DateTime, nullable=True)
    origem_baixa = db.Column(db.String(40), nullable=True)
    valor_nominal = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_pago = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_restante = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    data_emissao = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.DateTime, nullable=True)
    data_baixa = db.Column(db.DateTime, nullable=True)
    forma_pagamento_id = db.Column(db.Integer, db.ForeignKey("formas_pagamento.id"), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias_financeiras.id"), nullable=False)
    codigo_barras = db.Column(db.String(140), nullable=True)
    linha_digitavel = db.Column(db.String(160), nullable=True)
    arquivo_pdf_path = db.Column(db.String(255), nullable=True)
    arquivo_html_path = db.Column(db.String(255), nullable=True)
    boleto_url = db.Column(db.String(500), nullable=True)
    observacao = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("boletos", lazy=True))
    cliente = db.relationship("Cliente", backref=db.backref("boletos", lazy=True))
    venda = db.relationship("Venda", backref=db.backref("boletos", lazy=True))
    banco_emissor = db.relationship("BancoEmissor", backref=db.backref("boletos", lazy=True))
    configuracao_parcelamento = db.relationship("ConfiguracaoParcelamento", backref=db.backref("boletos", lazy=True))
    forma_pagamento = db.relationship("FormaPagamento", backref=db.backref("boletos", lazy=True))
    categoria = db.relationship("CategoriaFinanceira", backref=db.backref("boletos", lazy=True))

    __table_args__ = (
        UniqueConstraint("tenant_id", "numero_boleto", name="uq_boleto_tenant_numero"),
        CheckConstraint("valor_nominal >= 0", name="ck_boleto_valor_nominal_non_negative"),
        CheckConstraint("valor_pago >= 0", name="ck_boleto_valor_pago_non_negative"),
        CheckConstraint("valor_restante >= 0", name="ck_boleto_valor_restante_non_negative"),
        Index("ix_boleto_tenant_empresa_status", "tenant_id", "empresa_id", "status"),
        Index("ix_boleto_tenant_empresa_status_bancario", "tenant_id", "empresa_id", "status_bancario"),
        Index("ix_boleto_tenant_empresa_vencimento", "tenant_id", "empresa_id", "data_vencimento"),
    )


class ParcelaBoleto(db.Model):
    __tablename__ = "parcelas_boleto"

    id = db.Column(db.Integer, primary_key=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey("boletos.id"), nullable=False)
    numero_parcela = db.Column(db.Integer, nullable=False)
    valor_parcela = db.Column(db.Numeric(12, 2), nullable=False)
    valor_pago = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_restante = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.Enum(StatusBoleto), nullable=False, default=StatusBoleto.PENDENTE)
    juros_calculados = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    multa_calculada = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    desconto_aplicado = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    observacao = db.Column(db.Text, nullable=True)

    boleto = db.relationship("Boleto", backref=db.backref("parcelas", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        UniqueConstraint("boleto_id", "numero_parcela", name="uq_parcela_boleto_numero"),
        CheckConstraint("numero_parcela >= 1", name="ck_parcela_boleto_numero_positive"),
        CheckConstraint("valor_parcela >= 0", name="ck_parcela_boleto_valor_non_negative"),
        CheckConstraint("valor_pago >= 0", name="ck_parcela_boleto_pago_non_negative"),
        CheckConstraint("valor_restante >= 0", name="ck_parcela_boleto_restante_non_negative"),
        Index("ix_parcela_boleto_status_vencimento", "status", "data_vencimento"),
    )


class EventoBoleto(db.Model):
    __tablename__ = "eventos_boleto"

    id = db.Column(db.Integer, primary_key=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey("boletos.id"), nullable=False)
    parcela_id = db.Column(db.Integer, db.ForeignKey("parcelas_boleto.id"), nullable=True)
    tipo_evento = db.Column(db.Enum(TipoEventoBoleto), nullable=False)
    descricao = db.Column(db.Text, nullable=False)
    valor = db.Column(db.Numeric(12, 2), nullable=True)
    regra_juros_multa_id = db.Column(db.Integer, db.ForeignKey("regras_juros_multa.id"), nullable=True)
    criado_por_funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    boleto = db.relationship("Boleto", backref=db.backref("eventos", lazy=True, cascade="all, delete-orphan"))
    parcela = db.relationship("ParcelaBoleto", backref=db.backref("eventos", lazy=True))
    regra_juros_multa = db.relationship("RegraJurosMulta", backref=db.backref("eventos_boleto", lazy=True))
    criado_por = db.relationship("Funcionario", backref=db.backref("eventos_boleto", lazy=True))

    __table_args__ = (
        Index("ix_evento_boleto_boleto_tipo_data", "boleto_id", "tipo_evento", "criado_em"),
    )


class ArquivoBoleto(db.Model):
    __tablename__ = "arquivos_boleto"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey("boletos.id"), nullable=False)
    tipo = db.Column(db.String(30), nullable=False)
    ambiente = db.Column(db.String(30), nullable=False, default="HOMOLOGACAO")
    path = db.Column(db.String(255), nullable=False)
    provider_codigo = db.Column(db.String(80), nullable=True)
    identificador_externo = db.Column(db.String(120), nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    boleto = db.relationship("Boleto", backref=db.backref("arquivos", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        Index("ix_arquivo_boleto_tenant_boleto_tipo", "tenant_id", "boleto_id", "tipo"),
    )


class RetornoBancarioBoleto(db.Model):
    __tablename__ = "retornos_bancarios_boleto"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    boleto_id = db.Column(db.Integer, db.ForeignKey("boletos.id"), nullable=False)
    provider_codigo = db.Column(db.String(80), nullable=False)
    event_id = db.Column(db.String(120), nullable=False)
    tipo_evento = db.Column(db.String(60), nullable=False)
    status_processamento = db.Column(db.String(30), nullable=False, default="PROCESSADO")
    payload_resumido = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    boleto = db.relationship("Boleto", backref=db.backref("retornos_bancarios", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_codigo", "event_id", name="uq_retorno_bancario_evento"),
        Index("ix_retorno_bancario_tenant_boleto", "tenant_id", "boleto_id"),
    )


class FechamentoCaixa(ModeloBase):
    __tablename__ = "fechamentos_caixa"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False)
    data_fechamento = db.Column(db.Date, nullable=False)
    valor_inicial = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    valor_final = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    observacao = db.Column(db.Text, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("fechamentos_caixa", lazy=True))
    funcionario = db.relationship("Funcionario", backref=db.backref("fechamentos_caixa", lazy=True))

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "empresa_id",
            "funcionario_id",
            "data_fechamento",
            name="uq_fechamento_caixa_tenant_empresa_funcionario_data"
        ),
    )


class ConfiguracaoClienteEmpresa(ModeloBase):
    __tablename__ = "configuracoes_cliente_empresa"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    cashback_ativo = db.Column(db.Boolean, nullable=False, default=False)
    cashback_percentual = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    cashback_percentual_limite_resgate_venda = db.Column(db.Numeric(5, 2), nullable=False, default=100)
    cashback_validade_dias = db.Column(db.Integer, nullable=False, default=30)
    cashback_valor_minimo_resgate = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    cancelamento_venda_limite_horas = db.Column(db.Integer, nullable=False, default=24)
    cancelamento_item_limite_horas = db.Column(db.Integer, nullable=False, default=24)
    cancelamento_movimento_limite_horas = db.Column(db.Integer, nullable=False, default=24)
    email_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    email_remetente = db.Column(db.String(150), nullable=True)
    email_remetente_nome = db.Column(db.String(120), nullable=True)
    smtp_host = db.Column(db.String(180), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=False, default=587)
    smtp_usuario = db.Column(db.String(150), nullable=True)
    smtp_senha = db.Column(db.Text, nullable=True)
    smtp_tls = db.Column(db.Boolean, nullable=False, default=True)
    smtp_ssl = db.Column(db.Boolean, nullable=False, default=False)
    whatsapp_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    whatsapp_api_url = db.Column(db.String(255), nullable=True)
    whatsapp_token = db.Column(db.Text, nullable=True)
    whatsapp_remetente = db.Column(db.String(80), nullable=True)
    sms_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    sms_api_url = db.Column(db.String(255), nullable=True)
    sms_token = db.Column(db.Text, nullable=True)
    sms_remetente = db.Column(db.String(80), nullable=True)
    request_timeout_segundos = db.Column(db.Integer, nullable=False, default=15)

    empresa = db.relationship("Empresa", backref=db.backref("configuracao_cliente", uselist=False, lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        UniqueConstraint("tenant_id", "empresa_id", name="uq_config_cliente_empresa_tenant"),
        CheckConstraint("cashback_percentual >= 0 AND cashback_percentual <= 100", name="ck_config_cliente_cashback_percentual_range"),
        CheckConstraint(
            "cashback_percentual_limite_resgate_venda >= 0 AND cashback_percentual_limite_resgate_venda <= 100",
            name="ck_config_cliente_cashback_limite_resgate_range",
        ),
        CheckConstraint("cashback_validade_dias >= 1", name="ck_config_cliente_cashback_validade_positive"),
        CheckConstraint("cashback_valor_minimo_resgate >= 0", name="ck_config_cliente_cashback_resgate_non_negative"),
        CheckConstraint("cancelamento_venda_limite_horas >= 0", name="ck_config_cliente_cancelamento_venda_non_negative"),
        CheckConstraint("cancelamento_item_limite_horas >= 0", name="ck_config_cliente_cancelamento_item_non_negative"),
        CheckConstraint("cancelamento_movimento_limite_horas >= 0", name="ck_config_cliente_cancelamento_movimento_non_negative"),
        CheckConstraint("smtp_port >= 1", name="ck_config_cliente_smtp_port_positive"),
        CheckConstraint("request_timeout_segundos >= 1", name="ck_config_cliente_timeout_positive"),
    )


class ConfiguracaoFiscalEmpresa(ModeloBase):
    __tablename__ = "configuracoes_fiscais_empresa"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    ambiente = db.Column(db.Enum(AmbienteFiscal), nullable=False, default=AmbienteFiscal.HOMOLOGACAO)
    regime_tributario = db.Column(
        db.Enum(RegimeTributarioFiscal),
        nullable=False,
        default=RegimeTributarioFiscal.SIMPLES_NACIONAL,
    )
    serie_nfce = db.Column(db.Integer, nullable=False, default=1)
    proximo_numero_nfce = db.Column(db.Integer, nullable=False, default=1)
    inscricao_estadual = db.Column(db.String(30), nullable=True)
    inscricao_municipal = db.Column(db.String(30), nullable=True)
    cnae = db.Column(db.String(20), nullable=True)
    uf = db.Column(db.String(2), nullable=True)
    municipio_nome = db.Column(db.String(120), nullable=True)
    municipio_codigo_ibge = db.Column(db.String(7), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    logradouro = db.Column(db.String(180), nullable=True)
    numero = db.Column(db.String(20), nullable=True)
    complemento = db.Column(db.String(120), nullable=True)
    bairro = db.Column(db.String(120), nullable=True)
    certificado_caminho = db.Column(db.String(255), nullable=True)
    certificado_senha_env = db.Column(db.String(120), nullable=True)
    csc_id = db.Column(db.String(20), nullable=True)
    csc_token = db.Column(db.Text, nullable=True)
    integrador_provider = db.Column(db.String(80), nullable=False, default="mock_nfce")
    integrador_credencial_env = db.Column(db.String(120), nullable=True)
    focus_token_homologacao = db.Column(db.Text, nullable=True)
    focus_token_producao = db.Column(db.Text, nullable=True)
    focus_cnpj_emitente = db.Column(db.String(14), nullable=True)
    focus_status_configuracao = db.Column(db.String(30), nullable=False, default="PENDENTE")
    focus_ultima_validacao_em = db.Column(db.DateTime, nullable=True)
    focus_ultima_validacao_status = db.Column(db.String(30), nullable=True)
    focus_ultima_validacao_mensagem = db.Column(db.Text, nullable=True)
    contingencia_ativa = db.Column(db.Boolean, nullable=False, default=False)
    ultimo_teste_certificado_em = db.Column(db.DateTime, nullable=True)
    ultimo_teste_certificado_status = db.Column(db.String(30), nullable=True)
    ultimo_teste_certificado_detalhe = db.Column(db.Text, nullable=True)

    empresa = db.relationship(
        "Empresa",
        backref=db.backref("configuracao_fiscal", uselist=False, lazy=True, cascade="all, delete-orphan"),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "empresa_id", name="uq_config_fiscal_empresa_tenant"),
        CheckConstraint("serie_nfce >= 1", name="ck_config_fiscal_serie_positive"),
        CheckConstraint("proximo_numero_nfce >= 1", name="ck_config_fiscal_proximo_numero_positive"),
    )


class NotaFiscalVenda(ModeloBase):
    __tablename__ = "notas_fiscais_venda"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    configuracao_fiscal_id = db.Column(db.Integer, db.ForeignKey("configuracoes_fiscais_empresa.id"), nullable=True)
    ambiente = db.Column(db.Enum(AmbienteFiscal), nullable=False, default=AmbienteFiscal.HOMOLOGACAO)
    status = db.Column(db.Enum(StatusNotaFiscal), nullable=False, default=StatusNotaFiscal.PENDENTE)
    status_oficial = db.Column(db.Enum(StatusOficialNotaFiscal), nullable=False, default=StatusOficialNotaFiscal.NAO_ENVIADA)
    modelo = db.Column(db.String(10), nullable=False, default="NFC-e")
    provider_codigo = db.Column(db.String(80), nullable=True)
    idempotency_key_envio = db.Column(db.String(120), nullable=True)
    referencia_externa = db.Column(db.String(120), nullable=True)
    serie = db.Column(db.Integer, nullable=True)
    numero = db.Column(db.Integer, nullable=True)
    chave_acesso = db.Column(db.String(60), nullable=True)
    recibo = db.Column(db.String(60), nullable=True)
    protocolo = db.Column(db.String(60), nullable=True)
    protocolo_oficial = db.Column(db.String(80), nullable=True)
    xml_path = db.Column(db.String(255), nullable=True)
    xml_assinado_path = db.Column(db.String(255), nullable=True)
    xml_autorizado_path = db.Column(db.String(255), nullable=True)
    danfe_path = db.Column(db.String(255), nullable=True)
    danfe_url = db.Column(db.String(500), nullable=True)
    xml_url = db.Column(db.String(500), nullable=True)
    codigo_retorno = db.Column(db.String(20), nullable=True)
    mensagem_retorno = db.Column(db.Text, nullable=True)
    enviado_em = db.Column(db.DateTime, nullable=True)
    emitida_em = db.Column(db.DateTime, nullable=True)
    autorizada_em = db.Column(db.DateTime, nullable=True)
    cancelada_em = db.Column(db.DateTime, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("notas_fiscais", lazy=True))
    venda = db.relationship("Venda", backref=db.backref("nota_fiscal", uselist=False, lazy=True))
    configuracao_fiscal = db.relationship(
        "ConfiguracaoFiscalEmpresa",
        backref=db.backref("notas_emitidas", lazy=True),
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "venda_id", name="uq_nota_fiscal_venda_tenant"),
        UniqueConstraint("tenant_id", "empresa_id", "serie", "numero", name="uq_nota_fiscal_tenant_empresa_serie_numero"),
        Index("ix_nota_fiscal_tenant_empresa_status", "tenant_id", "empresa_id", "status"),
        Index("ix_nota_fiscal_tenant_empresa_status_oficial", "tenant_id", "empresa_id", "status_oficial"),
    )


class EventoFiscalNota(db.Model):
    __tablename__ = "eventos_fiscais_nota"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("tenants.id"), nullable=False, index=True)
    nota_id = db.Column(db.Integer, db.ForeignKey("notas_fiscais_venda.id"), nullable=False)
    provider_codigo = db.Column(db.String(80), nullable=False)
    event_id = db.Column(db.String(120), nullable=False)
    tipo_evento = db.Column(db.String(60), nullable=False)
    status_processamento = db.Column(db.String(30), nullable=False, default="PROCESSADO")
    codigo_retorno = db.Column(db.String(20), nullable=True)
    mensagem = db.Column(db.Text, nullable=True)
    payload_resumido = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, nullable=False, default=TimeService.now_utc_naive)

    nota = db.relationship("NotaFiscalVenda", backref=db.backref("eventos_fiscais", lazy=True, cascade="all, delete-orphan"))

    __table_args__ = (
        UniqueConstraint("tenant_id", "provider_codigo", "event_id", name="uq_evento_fiscal_provider_evento"),
        Index("ix_evento_fiscal_tenant_nota", "tenant_id", "nota_id"),
    )


class MensagemCliente(ModeloBase):
    __tablename__ = "mensagens_cliente"

    empresa_id = db.Column(db.Integer, db.ForeignKey("empresas.id"), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=True)
    canal = db.Column(db.Enum(CanalMensagemCliente), nullable=False)
    destinatario = db.Column(db.String(160), nullable=False)
    assunto = db.Column(db.String(160), nullable=True)
    conteudo = db.Column(db.Text, nullable=False)
    status = db.Column(db.Enum(StatusMensagemCliente), nullable=False, default=StatusMensagemCliente.PENDENTE)
    resposta_integracao = db.Column(db.Text, nullable=True)
    erro = db.Column(db.Text, nullable=True)
    enviado_em = db.Column(db.DateTime, nullable=True)

    empresa = db.relationship("Empresa", backref=db.backref("mensagens_cliente", lazy=True))
    cliente = db.relationship("Cliente", backref=db.backref("mensagens", lazy=True))
    funcionario = db.relationship("Funcionario", backref=db.backref("mensagens_cliente", lazy=True))

    __table_args__ = (
        Index("ix_mensagem_cliente_tenant_cliente_criado", "tenant_id", "cliente_id", "criado_em"),
    )


class ConfiguracaoNotificacaoEstoque(ModeloBase):
    __tablename__ = "configuracoes_notificacao_estoque"

    popup_ao_entrar = db.Column(db.Boolean, nullable=False, default=True)
    alertar_estoque_baixo = db.Column(db.Boolean, nullable=False, default=True)
    alertar_sem_estoque = db.Column(db.Boolean, nullable=False, default=True)
    alertar_validade = db.Column(db.Boolean, nullable=False, default=True)
    dias_vencimento_alerta = db.Column(db.Integer, nullable=False, default=30)
    email_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    email_destinatarios = db.Column(db.Text, nullable=True)
    whatsapp_habilitado = db.Column(db.Boolean, nullable=False, default=False)
    whatsapp_destinatarios = db.Column(db.Text, nullable=True)
    resumo_diario = db.Column(db.Boolean, nullable=False, default=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", name="uq_config_notificacao_estoque_tenant"),
        CheckConstraint("dias_vencimento_alerta >= 1", name="ck_config_notificacao_dias_positive"),
    )
