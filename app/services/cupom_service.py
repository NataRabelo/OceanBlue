from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from app.extensions import db
from app.models.db import Cupom, TipoDesconto, Empresa, Cliente, Venda
from app.repositorys.cupom_repository import CupomRepository
from app.services.time_service import TimeService
from app.services.transaction_service import atomic_operation


class CupomService:

    @staticmethod
    def listar(tenant_id):
        return [CupomService.serializar(item) for item in CupomRepository.listar(tenant_id)]

    @staticmethod
    @atomic_operation
    def criar(data, tenant_id, funcionario_id=None):
        try:
            nome = (data.get("nome") or "").strip()
            codigo = (data.get("codigo") or "").strip().upper()
            data_validade = CupomService._to_date(data.get("data_validade"), obrigatoria=True)
            tipo_desconto = CupomService._to_tipo_desconto(data.get("tipo_desconto"))
            valor_desconto = CupomService._to_decimal(data.get("valor_desconto"), "valor do desconto")
            ativo = CupomService._to_bool(data.get("ativo", True))

            CupomService._validar_dados(
                nome=nome,
                codigo=codigo,
                data_validade=data_validade,
                tipo_desconto=tipo_desconto,
                valor_desconto=valor_desconto,
                tenant_id=tenant_id,
            )

            cupom = Cupom(
                tenant_id=tenant_id,
                criado_por_funcionario_id=funcionario_id,
                nome=nome,
                codigo=codigo,
                data_validade=data_validade,
                tipo_desconto=tipo_desconto,
                valor_desconto=valor_desconto,
                ativo=ativo,
            )
            CupomService._aplicar_regras(cupom, data, tenant_id)
            CupomRepository.adicionar(cupom)
            CupomRepository.salvar()
            return CupomRepository.buscar_por_id(cupom.id, tenant_id)
        except Exception:
            CupomRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def atualizar(cupom_id, data, tenant_id):
        try:
            cupom = CupomRepository.buscar_por_id(cupom_id, tenant_id)
            if not cupom:
                raise ValueError("Cupom nao encontrado.")

            if "empresa_id" in data and str(data["empresa_id"] or "") != str(cupom.empresa_id or ""):
                raise ValueError("Empresa do cupom e imutavel; crie outro cupom.")

            nome = (data.get("nome") or "").strip()
            codigo = (data.get("codigo") or "").strip().upper()
            data_validade = CupomService._to_date(data.get("data_validade"), obrigatoria=True)
            tipo_desconto = CupomService._to_tipo_desconto(data.get("tipo_desconto"))
            valor_desconto = CupomService._to_decimal(data.get("valor_desconto"), "valor do desconto")
            ativo = CupomService._to_bool(data.get("ativo", True))

            CupomService._validar_dados(
                nome=nome,
                codigo=codigo,
                data_validade=data_validade,
                tipo_desconto=tipo_desconto,
                valor_desconto=valor_desconto,
                tenant_id=tenant_id,
                ignorar_id=cupom.id,
            )

            cupom.nome = nome
            cupom.codigo = codigo
            cupom.data_validade = data_validade
            cupom.tipo_desconto = tipo_desconto
            cupom.valor_desconto = valor_desconto
            cupom.ativo = ativo
            CupomService._aplicar_regras(cupom, data, tenant_id)

            CupomRepository.salvar()
            return CupomRepository.buscar_por_id(cupom.id, tenant_id)
        except Exception:
            CupomRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def deletar(cupom_id, tenant_id):
        try:
            cupom = CupomRepository.buscar_por_id(cupom_id, tenant_id)
            if not cupom:
                raise ValueError("Cupom nao encontrado.")

            if Venda.query.filter_by(tenant_id=tenant_id, cupom_id=cupom.id).first():
                raise ValueError("Cupom utilizado possui historico; desative-o.")
            CupomRepository.deletar(cupom)
            CupomRepository.salvar()
        except Exception:
            CupomRepository.rollback()
            raise

    @staticmethod
    def serializar(cupom):
        hoje = TimeService.today_br()
        status = "EXPIRADO" if cupom.data_validade < hoje else "ATIVO" if cupom.ativo else "INATIVO"
        if status == "ATIVO" and cupom.data_inicio and cupom.data_inicio > hoje:
            status = "AGENDADO"
        return {
            "id": cupom.id,
            "nome": cupom.nome,
            "codigo": cupom.codigo,
            "data_validade": cupom.data_validade.isoformat(),
            "tipo_desconto": cupom.tipo_desconto.value,
            "valor_desconto": str(CupomService._to_decimal_value(cupom.valor_desconto)),
            "ativo": cupom.ativo,
            "data_inicio": cupom.data_inicio.isoformat() if cupom.data_inicio else None,
            "empresa_id": cupom.empresa_id,
            "cliente_id": cupom.cliente_id,
            "limite_usos": cupom.limite_usos,
            "limite_por_cliente": cupom.limite_por_cliente,
            "valor_minimo": str(cupom.valor_minimo),
            "desconto_maximo": str(cupom.desconto_maximo) if cupom.desconto_maximo is not None else None,
            "usos": CupomService.contar_usos(cupom.id, cupom.tenant_id),
            "status": status,
            "criado_por_nome": cupom.criado_por.nome if cupom.criado_por else None,
        }

    @staticmethod
    def _validar_dados(nome, codigo, data_validade, tipo_desconto, valor_desconto, tenant_id, ignorar_id=None):
        if not nome or len(nome) > 100:
            raise ValueError("Nome do cupom e obrigatorio.")

        if not codigo or len(codigo) > 60:
            raise ValueError("Codigo do cupom e obrigatorio.")

        if CupomRepository.buscar_por_codigo(codigo, tenant_id, ignorar_id=ignorar_id):
            raise ValueError("Ja existe um cupom com esse codigo.")

        if tipo_desconto == TipoDesconto.PERCENTUAL and valor_desconto > Decimal("100.00"):
            raise ValueError("O desconto percentual nao pode ser maior que 100%.")

        if data_validade < TimeService.today_br():
            raise ValueError("A validade do cupom nao pode estar no passado.")

    @staticmethod
    def _to_tipo_desconto(value):
        try:
            return TipoDesconto[(value or "").strip().upper()]
        except KeyError:
            raise ValueError("Tipo de desconto invalido.")

    @staticmethod
    def _to_date(value, obrigatoria=False):
        if value in (None, ""):
            if obrigatoria:
                raise ValueError("Data de validade e obrigatoria.")
            return None

        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data invalida. Use o formato YYYY-MM-DD.")

    @staticmethod
    def _to_decimal(value, field_name):
        if value in (None, ""):
            raise ValueError(f"Informe {field_name}.")

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if not valor.is_finite() or valor <= 0 or valor >= Decimal("10000000000"):
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        valor = valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if valor <= 0 or valor >= Decimal("10000000000"):
            raise ValueError(f"Valor invalido para {field_name}.")
        return valor

    @staticmethod
    def _aplicar_regras(cupom, data, tenant_id):
        for field in ("empresa_id", "cliente_id", "limite_usos", "limite_por_cliente"):
            if field not in data:
                continue
            value = data[field]
            if value in (None, ""):
                setattr(cupom, field, None)
                continue
            try:
                number = int(str(value))
            except (ValueError, TypeError):
                raise ValueError(f"{field} deve ser inteiro positivo.")
            if number <= 0 or number > 2147483647:
                raise ValueError(f"{field} deve ser inteiro positivo.")
            if field in ("empresa_id", "cliente_id"):
                model = Empresa if field == "empresa_id" else Cliente
                if not model.query.filter_by(id=number, tenant_id=tenant_id, ativo=True).first():
                    raise ValueError("Segmento do cupom indisponivel.")
            setattr(cupom, field, number)
        if "data_inicio" in data:
            cupom.data_inicio = CupomService._to_date(data["data_inicio"])
        if cupom.data_inicio and cupom.data_inicio > cupom.data_validade:
            raise ValueError("Inicio do cupom deve preceder a validade.")
        for field in ("valor_minimo", "desconto_maximo"):
            if field in data:
                value = data[field]
                parsed = None if value in (None, "") else CupomService._to_decimal(value, field) if str(value) not in ("0", "0.00", "0,00") else Decimal("0.00")
                if field == "desconto_maximo" and parsed == 0:
                    raise ValueError("Desconto maximo deve ser positivo.")
                setattr(cupom, field, parsed if field == "desconto_maximo" else parsed or Decimal("0.00"))

    @staticmethod
    def validar_uso(cupom, tenant_id, empresa_id, cliente_id, subtotal):
        hoje = TimeService.today_br()
        if not cupom.ativo or cupom.data_validade < hoje or (cupom.data_inicio and cupom.data_inicio > hoje):
            raise ValueError("Cupom fora do periodo ativo.")
        if cupom.empresa_id and cupom.empresa_id != empresa_id:
            raise ValueError("Cupom indisponivel nesta empresa.")
        if cupom.cliente_id and cupom.cliente_id != cliente_id:
            raise ValueError("Cupom indisponivel para este cliente.")
        if subtotal < cupom.valor_minimo:
            raise ValueError("Subtotal inferior ao minimo do cupom.")
        if cupom.limite_usos and CupomService.contar_usos(cupom.id, tenant_id) >= cupom.limite_usos:
            raise ValueError("Limite de usos do cupom atingido.")
        if cupom.limite_por_cliente:
            if not cliente_id:
                raise ValueError("Identifique o cliente para utilizar este cupom.")
            if CupomService.contar_usos(cupom.id, tenant_id, cliente_id) >= cupom.limite_por_cliente:
                raise ValueError("Limite do cupom por cliente atingido.")

    @staticmethod
    def contar_usos(cupom_id, tenant_id, cliente_id=None):
        statement = "SELECT count(*) FROM vendas WHERE tenant_id=:tenant_id AND cupom_id=:cupom_id"
        parameters = {"tenant_id": tenant_id, "cupom_id": cupom_id}
        if cliente_id is not None:
            statement += " AND cliente_id=:cliente_id"
            parameters["cliente_id"] = cliente_id
        return db.session.execute(db.text(statement), parameters).scalar_one()

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "on", "sim", "yes"}

    @staticmethod
    def _to_decimal_value(value):
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")
