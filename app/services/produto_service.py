from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.models.db import Produto, ProdutoEmpresa
from app.extensions import db
from app.repositorys.produto_repository import ProdutoRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.tenant_entitlement_service import TenantEntitlementService


class ProdutoService:

    @staticmethod
    def listar(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        return ProdutoRepository.listar(tenant_id, empresa_ids)

    @staticmethod
    def listar_categorias(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        return ProdutoRepository.listar_categorias(tenant_id, empresa_ids)

    @staticmethod
    def listar_empresas(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        return ProdutoRepository.listar_empresas(tenant_id, empresa_ids)

    @staticmethod
    def criar(data, tenant_id, escopo, funcionario_id=None):
        TenantEntitlementService.validar_limite_produtos(
            tenant_id,
            ProdutoRepository.contar_produtos(tenant_id),
        )
        nome = (data.get("nome") or "").strip()
        descricao = (data.get("descricao") or "").strip() or None
        categoria_id = ProdutoService._to_int(data.get("categoria_id"), "Categoria")
        empresa_id = ProdutoService._to_int(data.get("empresa_id"), "Empresa")
        codigo_barras = ProdutoService._normalize_barcode(data.get("codigo_barras"))
        possui_ncm = ProdutoService._to_bool(data.get("possui_ncm", False))
        ncm = (data.get("ncm") or "").strip() or None
        estoque_minimo = ProdutoService._to_non_negative_int(data.get("estoque_minimo", 0), "estoque minimo")
        valor_compra = ProdutoService._to_decimal(data.get("valor_compra", 0), "valor de compra", 2)
        valor_varejo = ProdutoService._to_decimal(
            data.get("valor_varejo", data.get("valor_venda", 0)),
            "valor de varejo",
            2,
        )
        valor_atacado = ProdutoService._to_decimal(
            data.get("valor_atacado", data.get("valor_varejo", data.get("valor_venda", 0))),
            "valor de atacado",
            2,
        )
        quantidade_minima_atacado = ProdutoService._to_positive_int(
            data.get("quantidade_minima_atacado", 1),
            "quantidade minima para atacado",
            default=1,
        )
        data_validade = ProdutoService._to_optional_date(data.get("data_validade"))
        ativo = ProdutoService._to_bool(data.get("ativo", True))

        if not nome:
            raise ValueError("Nome do produto e obrigatorio.")

        if not empresa_id:
            raise ValueError("Empresa e obrigatoria.")

        AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        empresa = ProdutoRepository.buscar_empresa_por_id(empresa_id, tenant_id)
        if not empresa:
            raise ValueError("Empresa nao encontrada.")

        categoria = None
        if categoria_id:
            categoria = ProdutoRepository.buscar_categoria_por_id(categoria_id, tenant_id)
            if not categoria:
                raise ValueError("Categoria nao encontrada.")

        if ProdutoRepository.buscar_produto_por_nome(nome, tenant_id):
            raise ValueError("Ja existe um produto com esse nome.")

        if not codigo_barras:
            codigo_barras = ProdutoService._gerar_codigo_barras(tenant_id)

        if codigo_barras and ProdutoRepository.buscar_produto_por_codigo_barras(codigo_barras, tenant_id):
            raise ValueError("Ja existe um produto com esse codigo de barras.")

        if possui_ncm and not ncm:
            raise ValueError("Informe o NCM quando 'possui NCM' estiver marcado.")

        if valor_atacado > valor_varejo:
            raise ValueError("O valor de atacado nao pode ser maior que o valor de varejo.")

        produto = Produto(
            tenant_id=tenant_id,
            categoria_id=categoria.id if categoria else None,
            criado_por_funcionario_id=funcionario_id,
            nome=nome,
            descricao=descricao,
            possui_ncm=possui_ncm,
            ncm=ncm,
            codigo_barras=codigo_barras,
            ativo=ativo
        )
        ProdutoRepository.adicionar(produto)
        db.session.flush()

        produto_empresa = ProdutoEmpresa(
            tenant_id=tenant_id,
            produto_id=produto.id,
            empresa_id=empresa.id,
            estoque_atual=0,
            estoque_minimo=estoque_minimo,
            valor_compra=valor_compra,
            valor_venda=valor_varejo,
            valor_varejo=valor_varejo,
            valor_atacado=valor_atacado,
            quantidade_minima_atacado=quantidade_minima_atacado,
            data_validade=data_validade,
            ativo=ativo
        )
        ProdutoRepository.adicionar(produto_empresa)
        ProdutoRepository.salvar()

        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        return ProdutoRepository.buscar_produto_empresa_por_id(produto_empresa.id, tenant_id, empresa_ids)

    @staticmethod
    def atualizar(produto_empresa_id, data, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        produto_empresa = ProdutoRepository.buscar_produto_empresa_por_id(produto_empresa_id, tenant_id, empresa_ids)
        if not produto_empresa:
            raise ValueError("Produto nao encontrado.")

        produto = produto_empresa.produto

        nome = (data.get("nome") or "").strip()
        descricao = (data.get("descricao") or "").strip() or None
        categoria_id = ProdutoService._to_int(data.get("categoria_id"), "Categoria")
        empresa_id = ProdutoService._to_int(data.get("empresa_id"), "Empresa")
        codigo_barras = ProdutoService._normalize_barcode(data.get("codigo_barras"))
        possui_ncm = ProdutoService._to_bool(data.get("possui_ncm", False))
        ncm = (data.get("ncm") or "").strip() or None
        estoque_minimo = ProdutoService._to_non_negative_int(data.get("estoque_minimo", 0), "estoque minimo")
        valor_compra = ProdutoService._to_decimal(data.get("valor_compra", 0), "valor de compra", 2)
        valor_varejo = ProdutoService._to_decimal(
            data.get("valor_varejo", data.get("valor_venda", 0)),
            "valor de varejo",
            2,
        )
        valor_atacado = ProdutoService._to_decimal(
            data.get("valor_atacado", data.get("valor_varejo", data.get("valor_venda", 0))),
            "valor de atacado",
            2,
        )
        quantidade_minima_atacado = ProdutoService._to_positive_int(
            data.get("quantidade_minima_atacado", 1),
            "quantidade minima para atacado",
            default=1,
        )
        data_validade = ProdutoService._to_optional_date(data.get("data_validade"))
        ativo = ProdutoService._to_bool(data.get("ativo", True))

        if not nome:
            raise ValueError("Nome do produto e obrigatorio.")

        if not empresa_id:
            raise ValueError("Empresa e obrigatoria.")

        AcessoEmpresaService.validar_empresa(empresa_id, escopo)

        empresa = ProdutoRepository.buscar_empresa_por_id(empresa_id, tenant_id)
        if not empresa:
            raise ValueError("Empresa nao encontrada.")

        categoria = None
        if categoria_id:
            categoria = ProdutoRepository.buscar_categoria_por_id(categoria_id, tenant_id)
            if not categoria:
                raise ValueError("Categoria nao encontrada.")

        produto_existente = ProdutoRepository.buscar_produto_por_nome(
            nome,
            tenant_id,
            ignorar_produto_id=produto.id
        )
        if produto_existente:
            raise ValueError("Ja existe um produto com esse nome.")

        if not codigo_barras:
            codigo_barras = ProdutoService._gerar_codigo_barras(tenant_id, ignorar_produto_id=produto.id)

        codigo_existente = ProdutoRepository.buscar_produto_por_codigo_barras(
            codigo_barras,
            tenant_id,
            ignorar_produto_id=produto.id
        )
        if codigo_existente:
            raise ValueError("Ja existe um produto com esse codigo de barras.")

        if possui_ncm and not ncm:
            raise ValueError("Informe o NCM quando 'possui NCM' estiver marcado.")

        if valor_atacado > valor_varejo:
            raise ValueError("O valor de atacado nao pode ser maior que o valor de varejo.")

        if ProdutoRepository.existe_produto_empresa(
            produto.id,
            empresa.id,
            tenant_id,
            ignorar_produto_empresa_id=produto_empresa.id
        ):
            raise ValueError("Esse produto ja esta vinculado a essa empresa.")

        produto.nome = nome
        produto.descricao = descricao
        produto.categoria_id = categoria.id if categoria else None
        produto.codigo_barras = codigo_barras
        produto.possui_ncm = possui_ncm
        produto.ncm = ncm
        produto.ativo = ativo

        produto_empresa.empresa_id = empresa.id
        produto_empresa.estoque_minimo = estoque_minimo
        produto_empresa.valor_compra = valor_compra
        produto_empresa.valor_venda = valor_varejo
        produto_empresa.valor_varejo = valor_varejo
        produto_empresa.valor_atacado = valor_atacado
        produto_empresa.quantidade_minima_atacado = quantidade_minima_atacado
        produto_empresa.data_validade = data_validade
        produto_empresa.ativo = ativo

        ProdutoRepository.salvar()

        return ProdutoRepository.buscar_produto_empresa_por_id(produto_empresa.id, tenant_id, empresa_ids)

    @staticmethod
    def deletar(produto_empresa_id, tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        produto_empresa = ProdutoRepository.buscar_produto_empresa_por_id(produto_empresa_id, tenant_id, empresa_ids)
        if not produto_empresa:
            raise ValueError("Produto nao encontrado.")

        produto_id = produto_empresa.produto_id
        produto = produto_empresa.produto

        ProdutoRepository.deletar(produto_empresa)
        ProdutoRepository.salvar()

        total_vinculos = ProdutoRepository.contar_vinculos_produto(produto_id, tenant_id)
        if total_vinculos == 0:
            ProdutoRepository.deletar(produto)
            ProdutoRepository.salvar()

    @staticmethod
    def _to_decimal(value, field_name, casas=2):
        if value in (None, ""):
            value = 0

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")

        quant = "0." + ("0" * (casas - 1)) + "1" if casas > 0 else "1"
        return valor.quantize(Decimal(quant))

    @staticmethod
    def _to_non_negative_int(value, field_name):
        if value in (None, ""):
            value = 0

        try:
            valor = int(str(value).strip().replace(".", "").replace(",", ""))
        except (TypeError, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if valor < 0:
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")

        return valor

    @staticmethod
    def _to_positive_int(value, field_name, default=None):
        if value in (None, ""):
            if default is not None:
                return int(default)
            raise ValueError(f"{field_name.capitalize()} e obrigatoria.")

        try:
            valor = int(str(value).strip().replace(".", "").replace(",", ""))
        except (TypeError, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if valor <= 0:
            raise ValueError(f"{field_name.capitalize()} deve ser maior que zero.")

        return valor

    @staticmethod
    def _to_bool(value):
        if isinstance(value, bool):
            return value

        if value in [1, "1", "true", "True", "on", "ON", "sim", "SIM"]:
            return True

        return False

    @staticmethod
    def _to_int(value, field_name):
        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} invalida.")

    @staticmethod
    def _to_optional_date(value):
        if value in (None, ""):
            return None

        try:
            return datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Data de validade invalida. Use o formato YYYY-MM-DD.")

    @staticmethod
    def _normalize_barcode(value):
        digits = "".join(char for char in str(value or "") if char.isdigit())
        return digits or None

    @staticmethod
    def _gerar_codigo_barras(tenant_id, ignorar_produto_id=None):
        tenant_fragment = int(tenant_id or 0) % 10000
        sequencia = max(ProdutoRepository.contar_produtos(tenant_id) + 1, 1)

        while True:
            base = f"20{tenant_fragment:04d}{sequencia:06d}"
            codigo = f"{base}{ProdutoService._calcular_digito_ean13(base)}"
            if not ProdutoRepository.buscar_produto_por_codigo_barras(
                codigo,
                tenant_id,
                ignorar_produto_id=ignorar_produto_id,
            ):
                return codigo
            sequencia += 1

    @staticmethod
    def _calcular_digito_ean13(base):
        if len(base) != 12 or not base.isdigit():
            raise ValueError("Base invalida para gerar codigo EAN-13.")

        soma_impares = sum(int(digito) for digito in base[::2])
        soma_pares = sum(int(digito) for digito in base[1::2])
        resto = (soma_impares + (soma_pares * 3)) % 10
        return (10 - resto) % 10
