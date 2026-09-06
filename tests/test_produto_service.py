import os
import unittest

from app import create_app
from tests.database import reset_test_database
from app.extensions import db
from app.models.db import CategoriaProduto, Empresa, Funcionario, FuncionarioEmpresa, Tenant, TipoEmpresa
from app.security.password import hash_password
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.produto_service import ProdutoService
from app.services.tenant_bootstrap_service import TenantBootstrapService


class ProdutoServiceTestCase(unittest.TestCase):
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

        tenant = Tenant(nome="Tenant Produto")
        db.session.add(tenant)
        db.session.commit()

        roles = TenantBootstrapService.garantir_permissoes_e_roles(tenant.id)
        TenantBootstrapService.garantir_cadastros_operacionais(tenant.id)

        empresa = Empresa(
            tenant_id=tenant.id,
            cnpj="98.765.432/0001-10",
            razao_social="Empresa Produto LTDA",
            nome_fantasia="Empresa Produto",
            tipo_empresa=TipoEmpresa.MATRIZ,
            ativo=True,
        )
        db.session.add(empresa)
        db.session.flush()

        funcionario = Funcionario(
            tenant_id=tenant.id,
            role_id=roles["administrador"].id,
            nome="Admin Produto",
            cpf="987.654.321-00",
            usuario="admin_produto",
            senha_hash=hash_password("123456"),
            salario=2500,
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
            nome="Mercearia",
            descricao="Categoria sem produto vinculado",
            ativo=True,
        )
        db.session.add(categoria)
        db.session.commit()

        self.tenant = tenant
        self.empresa = empresa
        self.funcionario = funcionario
        self.categoria = categoria
        self.escopo = AcessoEmpresaService.obter_escopo(funcionario.id, tenant.id)

    def test_listar_categorias_retorna_categoria_sem_produto_vinculado(self):
        categorias = ProdutoService.listar_categorias(self.tenant.id, self.escopo)
        nomes = {categoria.nome for categoria in categorias}

        self.assertIn("Mercearia", nomes)

    def test_criar_produto_gera_codigo_barras_ean13_quando_vazio(self):
        produto = ProdutoService.criar(
            {
                "nome": "Arroz Tipo 1",
                "descricao": "Pacote 5kg",
                "categoria_id": self.categoria.id,
                "empresa_id": self.empresa.id,
                "codigo_barras": "",
                "possui_ncm": False,
                "estoque_minimo": "3",
                "valor_compra": "18.90",
                "valor_varejo": "24.90",
                "valor_atacado": "22.90",
                "quantidade_minima_atacado": "6",
                "ativo": True,
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        codigo = produto.produto.codigo_barras
        base = codigo[:12]

        self.assertTrue(codigo.isdigit())
        self.assertEqual(len(codigo), 13)
        self.assertEqual(codigo[-1], str(ProdutoService._calcular_digito_ean13(base)))

    def test_limite_de_produtos_do_plano_bloqueia_novo_cadastro(self):
        self.tenant.limite_produtos = 1
        db.session.commit()

        ProdutoService.criar(
            {
                "nome": "Feijao Tipo 1",
                "categoria_id": self.categoria.id,
                "empresa_id": self.empresa.id,
                "valor_varejo": "8.90",
                "valor_atacado": "8.50",
            },
            self.tenant.id,
            self.escopo,
            self.funcionario.id,
        )

        with self.assertRaises(ValueError) as contexto:
            ProdutoService.criar(
                {
                    "nome": "Cafe Torrado",
                    "categoria_id": self.categoria.id,
                    "empresa_id": self.empresa.id,
                    "valor_varejo": "14.90",
                    "valor_atacado": "13.90",
                },
                self.tenant.id,
                self.escopo,
                self.funcionario.id,
            )

        self.assertIn("Limite de produtos", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
