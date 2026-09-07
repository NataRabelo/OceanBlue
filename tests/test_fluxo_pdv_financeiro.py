import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from tests.database import reset_test_database
from app.extensions import db
from app.models.db import (
    AdiantamentoFuncionario,
    CategoriaProduto,
    Cliente,
    Empresa,
    Funcionario,
    FuncionarioEmpresa,
    LancamentoFinanceiro,
    MensagemCliente,
    MovimentoEstoque,
    NotaFiscalVenda,
    Produto,
    ProdutoEmpresa,
    StatusMensagemCliente,
    StatusOficialNotaFiscal,
    StatusNotaFiscal,
    StatusVenda,
    Tenant,
    TipoEmpresa,
    TipoFinanceiro,
)
from app.repositorys.cliente_repository import ClienteRepository
from app.services.mensagem_fila_service import MensagemFilaService, GatewaySimulado
from app.security.password import hash_password
from app.security.field_crypto import FieldCrypto
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.adiantamento_service import AdiantamentoService
from app.services.cliente_service import ClienteService
from app.services.comunicacao_service import ComunicacaoService
from app.services.estoque_service import EstoqueService
from app.services.fiscal_service import FiscalService
from app.services.financeiro_service import FinanceiroService
from app.services.pdv_service import PdvService
from app.services.tenant_bootstrap_service import TenantBootstrapService


class FluxoPdvFinanceiroTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        cls.app_context.pop()

    def setUp(self):
        reset_test_database()

        tenant = Tenant(nome="Tenant Teste")
        db.session.add(tenant)
        db.session.commit()

        roles = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
        TenantBootstrapService.garantir_cadastros_operacionais(tenant.id)

        empresa = Empresa(
            tenant_id=tenant.id,
            cnpj="12.345.678/0001-00",
            razao_social="Empresa Teste LTDA",
            nome_fantasia="Empresa Teste",
            tipo_empresa=TipoEmpresa.MATRIZ,
            ativo=True,
        )
        db.session.add(empresa)
        db.session.flush()

        funcionario = Funcionario(
            tenant_id=tenant.id,
            role_id=roles["administrador"].id,
            nome="Admin Teste",
            cpf="123.456.789-99",
            usuario="admin_teste",
            senha_hash=hash_password("123456"),
            salario=2000,
            ativo=True,
        )
        db.session.add(funcionario)
        db.session.flush()

        db.session.add(
            FuncionarioEmpresa(
                tenant_id=tenant.id,
                funcionario_id=funcionario.id,
                empresa_id=empresa.id,
                ativo=True,
            )
        )

        categoria = CategoriaProduto(
            tenant_id=tenant.id,
            nome="Bebidas",
            descricao="Categoria de teste",
            ativo=True,
        )
        db.session.add(categoria)
        db.session.flush()

        produto = Produto(
            tenant_id=tenant.id,
            categoria_id=categoria.id,
            criado_por_funcionario_id=funcionario.id,
            nome="Refrigerante 2L",
            descricao="Produto para fluxo de teste",
            possui_ncm=False,
            codigo_barras="789000000001",
            ativo=True,
        )
        db.session.add(produto)
        db.session.flush()

        produto_empresa = ProdutoEmpresa(
            tenant_id=tenant.id,
            produto_id=produto.id,
            empresa_id=empresa.id,
            estoque_atual=10,
            estoque_minimo=2,
            valor_compra=4.50,
            valor_venda=7.50,
            valor_varejo=7.50,
            valor_atacado=6.90,
            quantidade_minima_atacado=3,
            ativo=True,
        )
        db.session.add(produto_empresa)
        db.session.commit()

        self.tenant = tenant
        self.empresa = empresa
        self.funcionario = funcionario
        self.produto = produto
        self.produto_empresa = produto_empresa
        self.escopo = AcessoEmpresaService.obter_escopo(funcionario.id, tenant.id)

    def test_venda_baixa_estoque_e_gera_financeiro(self):
        payload = {
            "empresa_id": self.empresa.id,
            "itens": [
                {
                    "produto_id": self.produto.id,
                    "quantidade": 2,
                    "valor_unitario": "7.50",
                }
            ],
            "pagamentos": [
                {
                    "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                    "valor": "15.00",
                }
            ],
            "desconto_manual": "0.00",
        }

        venda = PdvService.criar_venda(payload, self.tenant.id, self.escopo, self.funcionario.id)
        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)

        self.assertEqual(venda["status"], StatusVenda.FINALIZADA.value)
        self.assertEqual(produto_empresa.estoque_atual, 8)
        self.assertEqual(venda["total"], "15.00")
        self.assertEqual(LancamentoFinanceiro.query.count(), 1)
        self.assertEqual(MovimentoEstoque.query.count(), 1)

    def test_venda_automatica_aplica_preco_atacado_ao_atingir_quantidade_minima(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]

        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "modalidade_preco": "AUTOMATICO",
                "itens": [{"produto_id": self.produto.id, "quantidade": 3}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "20.70"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        self.assertEqual(venda["modalidade_preco"], "AUTOMATICO")
        self.assertEqual(venda["subtotal"], "20.70")
        self.assertEqual(venda["itens"][0]["modalidade_preco_aplicada"], "ATACADO")

    def test_venda_em_atacado_exige_quantidade_minima_configurada(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]

        with self.assertRaisesRegex(ValueError, "minimo para venda em atacado"):
            PdvService.criar_venda(
                {
                    "empresa_id": self.empresa.id,
                    "modalidade_preco": "ATACADO",
                    "itens": [{"produto_id": self.produto.id, "quantidade": 2}],
                    "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "13.80"}],
                    "desconto_manual": "0.00",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

    def test_prevalidacao_fiscal_aponta_pendencias_sem_configuracao(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]
        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "7.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        resultado = FiscalService.prevalidar_venda(venda["id"], self.tenant.id, self.escopo)

        self.assertEqual(resultado["status"], "VALIDACAO_ERRO")
        self.assertTrue(any("configuracao fiscal" in item.lower() for item in resultado["pendencias"]))

    def test_prevalidacao_fiscal_fica_pronta_com_base_minima_preenchida(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]
        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "7.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        self.produto.possui_ncm = True
        self.produto.ncm = "22021000"
        db.session.commit()

        with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as certificado:
            certificado.write(b"dummy-cert")
            certificado_path = certificado.name

        os.environ["SEFAZ_CERT_PASSWORD_TEST"] = "123456"
        try:
            FiscalService.atualizar_configuracao(
                self.empresa.id,
                {
                    "ambiente": "HOMOLOGACAO",
                    "regime_tributario": "SIMPLES_NACIONAL",
                    "serie_nfce": 1,
                    "proximo_numero_nfce": 1,
                    "inscricao_estadual": "123456789",
                    "uf": "SP",
                    "municipio_nome": "Sao Paulo",
                    "municipio_codigo_ibge": "3550308",
                    "cep": "01001000",
                    "logradouro": "Rua Fiscal",
                    "numero": "100",
                    "bairro": "Centro",
                    "certificado_caminho": certificado_path,
                    "certificado_senha_env": "SEFAZ_CERT_PASSWORD_TEST",
                    "csc_id": "000001",
                    "csc_token": "TOKEN-CSC",
                },
                self.tenant.id,
                self.escopo,
            )

            resultado = FiscalService.prevalidar_venda(venda["id"], self.tenant.id, self.escopo)
            self.assertEqual(resultado["status"], "PRONTA_PARA_EMISSAO")
            self.assertEqual(resultado["pendencias"], [])
        finally:
            if os.path.exists(certificado_path):
                os.remove(certificado_path)
            os.environ.pop("SEFAZ_CERT_PASSWORD_TEST", None)

    def test_emissao_fiscal_gera_numero_chave_xml_e_incrementa_numeracao(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]
        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "7.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        self.produto.possui_ncm = True
        self.produto.ncm = "22021000"
        db.session.commit()

        with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as certificado:
            certificado.write(b"dummy-cert")
            certificado_path = certificado.name

        os.environ["SEFAZ_CERT_PASSWORD_TEST"] = "123456"
        try:
            FiscalService.atualizar_configuracao(
                self.empresa.id,
                {
                    "ambiente": "HOMOLOGACAO",
                    "regime_tributario": "SIMPLES_NACIONAL",
                    "serie_nfce": 3,
                    "proximo_numero_nfce": 42,
                    "inscricao_estadual": "123456789",
                    "uf": "SP",
                    "municipio_nome": "Sao Paulo",
                    "municipio_codigo_ibge": "3550308",
                    "cep": "01001000",
                    "logradouro": "Rua Fiscal",
                    "numero": "100",
                    "bairro": "Centro",
                    "certificado_caminho": certificado_path,
                    "certificado_senha_env": "SEFAZ_CERT_PASSWORD_TEST",
                    "csc_id": "000001",
                    "csc_token": "TOKEN-CSC",
                },
                self.tenant.id,
                self.escopo,
            )

            nota = FiscalService.emitir_nota_venda(venda["id"], self.tenant.id, self.escopo)
            registro = NotaFiscalVenda.query.filter_by(venda_id=venda["id"]).first()

            self.assertEqual(nota["status"], StatusNotaFiscal.EMITIDA.value)
            self.assertEqual(nota["status_oficial"], StatusOficialNotaFiscal.AUTORIZADA.value)
            self.assertEqual(nota["serie"], 3)
            self.assertEqual(nota["numero"], 42)
            self.assertEqual(len(nota["chave_acesso"]), 44)
            self.assertTrue(os.path.exists(registro.xml_path))
            self.assertTrue(os.path.exists(registro.xml_autorizado_path))
            self.assertTrue(os.path.exists(registro.danfe_path))
            self.assertIsNotNone(registro.protocolo_oficial)
            self.assertIn("<NFCe", open(registro.xml_path, encoding="utf-8").read())
            self.assertEqual(self.empresa.configuracao_fiscal.proximo_numero_nfce, 43)
        finally:
            if os.path.exists(certificado_path):
                os.remove(certificado_path)
            os.environ.pop("SEFAZ_CERT_PASSWORD_TEST", None)

    def test_cancelamento_reverte_estoque_e_financeiro(self):
        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                "pagamentos": [{
                    "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                    "valor": "7.50",
                }],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        cancelada = PdvService.cancelar_venda(
            venda["id"],
            {"motivo": "Cliente desistiu"},
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)
        lancamentos = LancamentoFinanceiro.query.order_by(LancamentoFinanceiro.id.asc()).all()

        self.assertEqual(cancelada["status"], StatusVenda.CANCELADA.value)
        self.assertEqual(produto_empresa.estoque_atual, 10)
        self.assertEqual(MovimentoEstoque.query.count(), 2)
        self.assertEqual(len(lancamentos), 2)
        self.assertEqual(lancamentos[0].tipo, TipoFinanceiro.ENTRADA)
        self.assertEqual(lancamentos[1].tipo, TipoFinanceiro.SAIDA)

    def test_lancamento_manual_e_fechamento(self):
        auxiliares = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)
        categoria_saida = auxiliares["categorias"]["SAIDA"][0]["id"]
        forma_pagamento = auxiliares["formas_pagamento"][0]["id"]

        lancamento = FinanceiroService.criar_lancamento_manual(
            {
                "empresa_id": self.empresa.id,
                "tipo": "SAIDA",
                "categoria_id": categoria_saida,
                "forma_pagamento_id": forma_pagamento,
                "descricao": "Compra emergencial",
                "valor": "20.00",
                "observacao": "Teste do financeiro",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        fechamento = FinanceiroService.criar_fechamento(
            {
                "empresa_id": self.empresa.id,
                "valor_inicial": "100.00",
                "valor_final": "80.00",
                "observacao": "Fechamento de teste",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        self.assertEqual(lancamento["tipo"], "SAIDA")
        self.assertEqual(fechamento["valor_inicial"], "100.00")
        self.assertEqual(fechamento["valor_final"], "80.00")

    def test_listagem_de_fechamentos_retorna_operador_e_diferenca(self):
        FinanceiroService.criar_fechamento(
            {
                "empresa_id": self.empresa.id,
                "valor_inicial": "100.00",
                "valor_final": "95.00",
                "observacao": "Fechamento do turno da tarde",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        fechamentos = FinanceiroService.listar_fechamentos(
            tenant_id=self.tenant.id,
            escopo=self.escopo,
            empresa_id=self.empresa.id,
            limite=10,
        )

        self.assertEqual(len(fechamentos), 1)
        self.assertEqual(fechamentos[0]["funcionario_nome"], self.funcionario.nome)
        self.assertEqual(fechamentos[0]["observacao"], "Fechamento do turno da tarde")
        self.assertEqual(fechamentos[0]["diferenca"], "-5.00")

    def test_busca_produto_por_codigo_barras_no_pdv(self):
        produto = PdvService.buscar_produto_por_codigo_barras(
            tenant_id=self.tenant.id,
            escopo=self.escopo,
            empresa_id=self.empresa.id,
            codigo_barras="789000000001",
        )

        self.assertEqual(produto["id"], self.produto.id)
        self.assertEqual(produto["codigo_barras"], "789000000001")

    def test_adiantamento_em_produto_baixa_estoque_e_gera_financeiro(self):
        auxiliares = AdiantamentoService.listar_auxiliares(self.tenant.id, self.escopo)
        forma_pagamento_id = next(
            item["id"]
            for item in auxiliares["formas_pagamento"]
            if item["nome"] == "Vale em folha"
        )

        registro = AdiantamentoService.criar(
            {
                "empresa_id": self.empresa.id,
                "funcionario_id": self.funcionario.id,
                "tipo_adiantamento": "PRODUTO",
                "forma_pagamento_id": forma_pagamento_id,
                "produto_id": self.produto.id,
                "quantidade": 2,
                "competencia": "2026-04",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)

        self.assertEqual(registro.tipo_adiantamento.value, "PRODUTO")
        self.assertEqual(produto_empresa.estoque_atual, 8)
        self.assertEqual(AdiantamentoFuncionario.query.count(), 1)
        self.assertEqual(LancamentoFinanceiro.query.count(), 1)
        self.assertEqual(MovimentoEstoque.query.count(), 1)

    def test_resumo_folha_considera_adiantamento_em_dinheiro(self):
        auxiliares = AdiantamentoService.listar_auxiliares(self.tenant.id, self.escopo)
        forma_pagamento_id = next(
            item["id"]
            for item in auxiliares["formas_pagamento"]
            if item["nome"] == "Vale em folha"
        )

        AdiantamentoService.criar(
            {
                "empresa_id": self.empresa.id,
                "funcionario_id": self.funcionario.id,
                "tipo_adiantamento": "DINHEIRO",
                "forma_pagamento_id": forma_pagamento_id,
                "valor_total": "150.00",
                "competencia": "2026-04",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        resumo = AdiantamentoService.obter_resumo_folha(
            tenant_id=self.tenant.id,
            escopo=self.escopo,
            empresa_id=self.empresa.id,
            competencia="2026-04",
        )

        self.assertEqual(resumo["totais"]["adiantado"], "150.00")
        self.assertEqual(resumo["funcionarios"][0]["saldo_a_pagar"], "1850.00")

    def test_relatorio_produtos_mais_vendidos_consolida_itens_do_pdv(self):
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]

        PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 3, "valor_unitario": "7.50"}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "22.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        relatorio = FinanceiroService.obter_relatorio_produtos_vendidos(
            tenant_id=self.tenant.id,
            escopo=self.escopo,
            empresa_id=self.empresa.id,
        )

        self.assertEqual(relatorio["totais"]["produtos"], 1)
        self.assertEqual(relatorio["itens"][0]["produto_nome"], "Refrigerante 2L")
        self.assertEqual(relatorio["itens"][0]["quantidade"], 3)

    def test_venda_com_cliente_gera_cashback_e_historico(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Cashback",
                "documento": "12345678901",
                "email": "cliente@example.com",
                "aceita_email": True,
                "aceita_whatsapp": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "10.00",
                "cashback_validade_dias": "45",
                "cashback_valor_minimo_resgate": "1.00",
            },
            self.tenant.id,
            self.escopo,
        )

        payload = {
            "empresa_id": self.empresa.id,
            "cliente_id": cliente.id,
            "itens": [{"produto_id": self.produto.id, "quantidade": 2, "valor_unitario": "7.50"}],
            "pagamentos": [{
                "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                "valor": "15.00",
            }],
            "desconto_manual": "0.00",
        }

        venda = PdvService.criar_venda(payload, self.tenant.id, self.escopo, self.funcionario.id)
        historico = ClienteService.obter_historico_vendas(cliente.id, self.tenant.id, self.escopo)

        self.assertEqual(venda["cliente_id"], cliente.id)
        self.assertEqual(venda["cashback_gerado"], "1.50")
        self.assertEqual(str(ClienteService.calcular_saldo_disponivel(cliente.id, self.tenant.id)), "1.50")
        self.assertEqual(len(historico), 1)
        self.assertEqual(historico[0]["numero_unico"], venda["numero_unico"])

    def test_cashback_respeita_limite_percentual_de_resgate_por_venda(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Limite Cashback",
                "documento": "12312312312",
                "aceita_whatsapp": True,
            },
            self.tenant.id,
        )
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]

        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "100.00",
                "cashback_percentual_limite_resgate_venda": "25.00",
                "cashback_validade_dias": "30",
                "cashback_valor_minimo_resgate": "1.00",
            },
            self.tenant.id,
            self.escopo,
        )

        PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "cliente_id": cliente.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "7.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        with self.assertRaisesRegex(ValueError, "25.00% do valor liquido da venda"):
            PdvService.criar_venda(
                {
                    "empresa_id": self.empresa.id,
                    "cliente_id": cliente.id,
                    "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                    "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "5.50"}],
                    "cashback_utilizado": "2.00",
                    "desconto_manual": "0.00",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

    def test_venda_pode_desativar_cashback_sem_afetar_carteira_existente(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Opt-out Cashback",
                "documento": "55511133322",
                "aceita_whatsapp": True,
            },
            self.tenant.id,
        )
        forma_pagamento_id = FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"]

        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "10.00",
                "cashback_percentual_limite_resgate_venda": "100.00",
                "cashback_validade_dias": "30",
                "cashback_valor_minimo_resgate": "1.00",
            },
            self.tenant.id,
            self.escopo,
        )

        PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "cliente_id": cliente.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 2, "valor_unitario": "7.50"}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "15.00"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "cliente_id": cliente.id,
                "cashback_ativado": False,
                "cashback_utilizado": "1.00",
                "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                "pagamentos": [{"forma_pagamento_id": forma_pagamento_id, "valor": "7.50"}],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        self.assertFalse(venda["cashback_ativado"])
        self.assertEqual(venda["cashback_utilizado"], "0.00")
        self.assertEqual(venda["cashback_gerado"], "0.00")
        self.assertEqual(str(ClienteService.calcular_saldo_disponivel(cliente.id, self.tenant.id)), "1.50")

    def test_cliente_sem_vendas_serializa_total_zero(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Novo",
                "documento": "32165498700",
                "telefone": "(11) 99888-7766",
                "whatsapp": "+55 11 99888-7766",
            },
            self.tenant.id,
        )

        serializado = ClienteService.serializar_cliente(cliente)

        self.assertEqual(serializado["documento"], "32165498700")
        self.assertEqual(serializado["telefone"], "11998887766")
        self.assertEqual(serializado["whatsapp"], "+5511998887766")
        self.assertEqual(serializado["total_vendido"], "0.00")
        self.assertEqual(serializado["saldo_cashback"], "0.00")

    def test_configuracao_cliente_preserva_senha_existente_quando_campo_nao_e_enviado(self):
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "loja@example.com",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "loja@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )

        dados = ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "loja@example.com",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "loja@example.com",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )

        configuracao = ClienteService._obter_ou_criar_configuracao_empresa(self.empresa.id, self.tenant.id)

        self.assertTrue(FieldCrypto.is_encrypted(configuracao.smtp_senha))
        self.assertEqual(FieldCrypto.decrypt(configuracao.smtp_senha), "senha-app")
        self.assertEqual(dados["smtp_senha"], "")
        self.assertTrue(dados["smtp_senha_configurada"])

    def test_normalizacao_de_senha_app_do_gmail_remove_espacos(self):
        configuracao = SimpleNamespace(
            smtp_host="smtp.gmail.com",
            smtp_senha="abcd efgh ijkl mnop",
        )

        self.assertEqual(
            ComunicacaoService._normalizar_senha_smtp(configuracao),
            "abcdefghijklmnop",
        )

    def test_teste_configuracao_empresa_usa_payload_informado_sem_persistir(self):
        with patch("app.services.cliente_service.ComunicacaoService.enviar") as mocked:
            mocked.return_value = {"resposta": "ok"}

            ClienteService.testar_configuracao_empresa(
                self.empresa.id,
                {
                    "canal": "EMAIL",
                    "destinatario": "destino@example.com",
                    "assunto": "Teste SMTP",
                    "conteudo": "Mensagem",
                    "configuracao": {
                        "email_habilitado": True,
                        "email_remetente": "loja@example.com",
                        "smtp_host": "smtp.gmail.com",
                        "smtp_port": "587",
                        "smtp_usuario": "loja@example.com",
                        "smtp_senha": "senha-app",
                        "smtp_tls": True,
                        "smtp_ssl": False,
                    },
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        configuracao_enviada = mocked.call_args.kwargs["configuracao"]
        configuracao_salva = ClienteRepository.buscar_configuracao_empresa(self.empresa.id, self.tenant.id)

        self.assertEqual(configuracao_enviada.smtp_host, "smtp.gmail.com")
        self.assertEqual(configuracao_enviada.smtp_senha, "senha-app")
        self.assertIsNone(configuracao_salva)

    def test_venda_com_cliente_envia_email_automatico_e_registra_cashback(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Email",
                "documento": "11122233344",
                "email": "cliente@email.com",
                "aceita_email": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "10.00",
                "cashback_validade_dias": "30",
                "cashback_valor_minimo_resgate": "1.00",
                "email_habilitado": True,
                "email_remetente": "loja@example.com",
                "email_remetente_nome": "Loja Teste",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "loja@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )

        with patch("app.services.cliente_service.ComunicacaoService.enviar") as mocked:
            mocked.return_value = {"resposta": "ok"}

            venda = PdvService.criar_venda(
                {
                    "empresa_id": self.empresa.id,
                    "cliente_id": cliente.id,
                    "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                    "pagamentos": [{
                        "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                        "valor": "7.50",
                    }],
                    "desconto_manual": "0.00",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        mensagem = MensagemCliente.query.first()

        self.assertEqual(venda["status"], StatusVenda.FINALIZADA.value)
        self.assertEqual(venda["cashback_gerado"], "0.75")
        self.assertEqual(venda["email_venda"]["status"], "PENDENTE")
        delivered = MensagemFilaService.entregar(mensagem.id, self.tenant.id, self.escopo, self.funcionario.id, GatewaySimulado())
        self.assertEqual(delivered["status"], "ENVIADO")
        self.assertEqual(MensagemCliente.query.count(), 1)
        self.assertEqual(mensagem.status, StatusMensagemCliente.ENVIADO)
        self.assertIn("Comprovante da venda", mensagem.assunto)
        self.assertIn("Cashback gerado nesta compra", mensagem.conteudo)
        self.assertEqual(mocked.call_count, 0)

    def test_template_html_do_email_de_venda_usa_identidade_oceanblue(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Layout",
                "documento": "55566677788",
                "email": "layout@email.com",
                "aceita_email": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "10.00",
                "cashback_validade_dias": "30",
                "cashback_valor_minimo_resgate": "1.00",
            },
            self.tenant.id,
            self.escopo,
        )

        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "cliente_id": cliente.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                "pagamentos": [{
                    "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                    "valor": "7.50",
                }],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        venda_modelo = ClienteRepository.listar_vendas_cliente(cliente.id, self.tenant.id, limite=1)[0]
        assunto, conteudo, html = ClienteService._montar_email_venda(venda_modelo, self.tenant.id)

        self.assertIn("Comprovante da venda", assunto)
        self.assertIn("Cashback gerado nesta compra", conteudo)
        self.assertIn("OceanBlue", html)
        self.assertIn("Sua compra foi concluida", html)
        self.assertIn("Itens da venda", html)
        self.assertIn(venda["numero_unico"], html)

    def test_venda_permanece_finalizada_quando_email_automatico_falha(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente SMTP",
                "documento": "44433322211",
                "email": "cliente@email.com",
                "aceita_email": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "loja@example.com",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "loja@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )

        with patch("app.services.cliente_service.ComunicacaoService.enviar") as mocked:
            mocked.side_effect = ValueError("SMTP indisponivel")

            venda = PdvService.criar_venda(
                {
                    "empresa_id": self.empresa.id,
                    "cliente_id": cliente.id,
                    "itens": [{"produto_id": self.produto.id, "quantidade": 1, "valor_unitario": "7.50"}],
                    "pagamentos": [{
                        "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                        "valor": "7.50",
                    }],
                    "desconto_manual": "0.00",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        mensagem = MensagemCliente.query.first()

        self.assertEqual(venda["status"], StatusVenda.FINALIZADA.value)
        self.assertEqual(venda["email_venda"]["status"], "PENDENTE")
        delivered = MensagemFilaService.entregar(mensagem.id, self.tenant.id, self.escopo, self.funcionario.id, GatewaySimulado("recusa"))
        self.assertEqual(delivered["status"], "FALHOU")
        self.assertEqual(MensagemCliente.query.count(), 1)
        self.assertEqual(mensagem.status, StatusMensagemCliente.ERRO)
        self.assertEqual(mensagem.erro, "Entrega recusada antes do aceite.")
        self.assertEqual(mocked.call_count, 0)

    def test_disparo_coletivo_envia_apenas_para_clientes_elegiveis(self):
        ClienteService.criar(
            {
                "nome": "Cliente Elegivel",
                "documento": "10020030040",
                "email": "elegivel@email.com",
                "aceita_email": True,
            },
            self.tenant.id,
        )
        ClienteService.criar(
            {
                "nome": "Cliente Sem Optin",
                "documento": "10020030041",
                "email": "semoptin@email.com",
                "aceita_email": False,
            },
            self.tenant.id,
        )
        ClienteService.criar(
            {
                "nome": "Cliente Sem Email",
                "documento": "10020030042",
                "aceita_email": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "loja@example.com",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "loja@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )

        with patch("app.services.cliente_service.ComunicacaoService.enviar") as mocked:
            mocked.return_value = {"resposta": "ok"}

            resumo = ClienteService.enviar_mensagem_coletiva(
                {
                    "empresa_id": self.empresa.id,
                    "canal": "EMAIL",
                    "assunto": "Campanha",
                    "conteudo": "Oferta especial para voce.",
                    "idempotency_key": "campanha-sintetica",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        self.assertEqual(resumo["enfileirados"], 1)
        self.assertEqual(resumo["enviados"], 0)
        delivered = MensagemFilaService.processar(self.tenant.id, self.escopo, self.funcionario.id, gateway=GatewaySimulado())
        self.assertEqual([record["status"] for record in delivered], ["ENVIADO"])
        self.assertEqual(resumo["ignorados"], 2)
        self.assertEqual(resumo["erros"], 0)
        self.assertEqual(MensagemCliente.query.count(), 1)
        self.assertEqual(mocked.call_count, 0)

    def test_alerta_email_estoque_dispara_ao_atingir_minimo(self):
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "operacoes@example.com",
                "email_remetente_nome": "Operacoes Loja",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "operacoes@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )
        EstoqueService.atualizar_configuracao_alerta(
            {
                "popup_ao_entrar": True,
                "alertar_estoque_baixo": True,
                "alertar_sem_estoque": True,
                "alertar_validade": True,
                "dias_vencimento_alerta": "30",
                "email_habilitado": True,
                "email_destinatarios": "estoque@example.com",
            },
            self.tenant.id,
            self.escopo,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)
        produto_empresa.estoque_atual = 3
        db.session.commit()

        with patch("app.services.estoque_service.ComunicacaoService.enviar") as mocked:
            mocked.return_value = {"resposta": "ok"}

            EstoqueService.registrar_movimentacao_manual(
                {
                    "tipo_movimento": "SAIDA",
                    "motivo": "AJUSTE",
                    "empresa_id": self.empresa.id,
                    "produto_empresa_id": self.produto_empresa.id,
                    "quantidade": "1",
                    "observacao": "Consumo interno",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)

        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(mocked.call_args.kwargs["destinatario"], "estoque@example.com")
        self.assertEqual(produto_empresa.estoque_atual, 2)
        self.assertEqual(produto_empresa.ultimo_alerta_estoque_status, EstoqueService.STATUS_ALERTA_ESTOQUE_BAIXO)
        self.assertIsNotNone(produto_empresa.ultimo_alerta_estoque_em)

    def test_alerta_email_estoque_respeita_cooldown_e_reenvia_em_novo_status(self):
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "email_habilitado": True,
                "email_remetente": "operacoes@example.com",
                "email_remetente_nome": "Operacoes Loja",
                "smtp_host": "smtp.gmail.com",
                "smtp_port": "587",
                "smtp_usuario": "operacoes@example.com",
                "smtp_senha": "senha-app",
                "smtp_tls": True,
                "smtp_ssl": False,
            },
            self.tenant.id,
            self.escopo,
        )
        EstoqueService.atualizar_configuracao_alerta(
            {
                "popup_ao_entrar": True,
                "alertar_estoque_baixo": True,
                "alertar_sem_estoque": True,
                "alertar_validade": True,
                "dias_vencimento_alerta": "30",
                "email_habilitado": True,
                "email_destinatarios": "estoque@example.com",
            },
            self.tenant.id,
            self.escopo,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)
        produto_empresa.estoque_atual = 3
        db.session.commit()

        with patch("app.services.estoque_service.ComunicacaoService.enviar") as mocked:
            mocked.return_value = {"resposta": "ok"}

            EstoqueService.registrar_movimentacao_manual(
                {
                    "tipo_movimento": "SAIDA",
                    "motivo": "AJUSTE",
                    "empresa_id": self.empresa.id,
                    "produto_empresa_id": self.produto_empresa.id,
                    "quantidade": "1",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )
            EstoqueService.registrar_movimentacao_manual(
                {
                    "tipo_movimento": "SAIDA",
                    "motivo": "AJUSTE",
                    "empresa_id": self.empresa.id,
                    "produto_empresa_id": self.produto_empresa.id,
                    "quantidade": "1",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )
            EstoqueService.registrar_movimentacao_manual(
                {
                    "tipo_movimento": "SAIDA",
                    "motivo": "AJUSTE",
                    "empresa_id": self.empresa.id,
                    "produto_empresa_id": self.produto_empresa.id,
                    "quantidade": "1",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)

        self.assertEqual(mocked.call_count, 2)
        self.assertEqual(produto_empresa.estoque_atual, 0)
        self.assertEqual(produto_empresa.ultimo_alerta_estoque_status, EstoqueService.STATUS_ALERTA_SEM_ESTOQUE)

    def test_cancelamento_parcial_de_item_reverte_estoque_e_ajusta_cashback(self):
        cliente = ClienteService.criar(
            {
                "nome": "Cliente Parcial",
                "documento": "98765432100",
                "aceita_whatsapp": True,
            },
            self.tenant.id,
        )
        ClienteService.atualizar_configuracao_empresa(
            self.empresa.id,
            {
                "cashback_ativo": True,
                "cashback_percentual": "10.00",
                "cashback_validade_dias": "30",
                "cashback_valor_minimo_resgate": "1.00",
            },
            self.tenant.id,
            self.escopo,
        )

        venda = PdvService.criar_venda(
            {
                "empresa_id": self.empresa.id,
                "cliente_id": cliente.id,
                "itens": [{"produto_id": self.produto.id, "quantidade": 2, "valor_unitario": "7.50"}],
                "pagamentos": [{
                    "forma_pagamento_id": FinanceiroService.listar_auxiliares(self.tenant.id, self.escopo)["formas_pagamento"][0]["id"],
                    "valor": "15.00",
                }],
                "desconto_manual": "0.00",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        item_id = venda["itens"][0]["id"]
        ajustada = PdvService.cancelar_item_venda(
            venda["id"],
            item_id,
            {"motivo": "Devolucao parcial"},
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)

        self.assertEqual(produto_empresa.estoque_atual, 9)
        self.assertEqual(ajustada["itens"][0]["quantidade_cancelada"], 1)
        self.assertEqual(ajustada["valor_cancelado"], "7.50")
        self.assertEqual(ajustada["cashback_gerado"], "0.75")
        self.assertEqual(str(ClienteService.calcular_saldo_disponivel(cliente.id, self.tenant.id)), "0.75")
        self.assertEqual(LancamentoFinanceiro.query.count(), 2)
        self.assertEqual(MovimentoEstoque.query.count(), 2)

    def test_cancelamento_de_movimento_manual_reverte_saldo(self):
        movimento = EstoqueService.registrar_movimentacao_manual(
            {
                "tipo_movimento": "ENTRADA",
                "motivo": "AJUSTE",
                "empresa_id": self.empresa.id,
                "produto_empresa_id": self.produto_empresa.id,
                "quantidade": "3",
                "valor_unitario": "4.50",
                "observacao": "Ajuste de entrada",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        cancelamento = EstoqueService.cancelar_movimento(
            movimento.id,
            {"motivo": "Lancamento incorreto"},
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        produto_empresa = db.session.get(ProdutoEmpresa, self.produto_empresa.id)
        movimento_original = db.session.get(MovimentoEstoque, movimento.id)

        self.assertEqual(produto_empresa.estoque_atual, 10)
        self.assertTrue(movimento_original.revertido)
        self.assertEqual(cancelamento.tipo_movimento.value, "SAIDA")
        self.assertEqual(MovimentoEstoque.query.count(), 2)


if __name__ == "__main__":
    unittest.main()
