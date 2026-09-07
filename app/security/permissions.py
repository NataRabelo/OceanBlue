DEFAULT_PERMISSION_DEFINITIONS = [
    {"codigo": "estornar_financeiro", "nome": "Estornar lancamentos financeiros"},
    {"codigo": "reabrir_caixa", "nome": "Reabrir e ajustar caixa"},
    {"codigo": "autorizar_adiantamento", "nome": "Autorizar e baixar adiantamentos"},
    {"codigo": "gerenciar_privacidade_cliente", "nome": "Exportar e anonimizar clientes"},
    {"codigo": "visualizar_funcionario", "nome": "Visualizar funcionarios"},
    {"codigo": "criar_funcionario", "nome": "Criar funcionarios"},
    {"codigo": "editar_funcionario", "nome": "Editar funcionarios"},
    {"codigo": "excluir_funcionario", "nome": "Excluir funcionarios"},
    {"codigo": "visualizar_categoria", "nome": "Visualizar categorias"},
    {"codigo": "criar_categoria", "nome": "Criar categorias"},
    {"codigo": "editar_categoria", "nome": "Editar categorias"},
    {"codigo": "excluir_categoria", "nome": "Excluir categorias"},
    {"codigo": "visualizar_produto", "nome": "Visualizar produtos"},
    {"codigo": "criar_produto", "nome": "Criar produtos"},
    {"codigo": "editar_produto", "nome": "Editar produtos"},
    {"codigo": "excluir_produto", "nome": "Excluir produtos"},
    {"codigo": "visualizar_role", "nome": "Visualizar roles"},
    {"codigo": "criar_role", "nome": "Criar roles"},
    {"codigo": "editar_role", "nome": "Editar roles"},
    {"codigo": "excluir_role", "nome": "Excluir roles"},
    {"codigo": "visualizar_permission", "nome": "Visualizar permissions"},
    {"codigo": "criar_permission", "nome": "Criar permissions"},
    {"codigo": "editar_permission", "nome": "Editar permissions"},
    {"codigo": "excluir_permission", "nome": "Excluir permissions"},
    {"codigo": "visualizar_pdv", "nome": "Visualizar PDV"},
    {"codigo": "registrar_venda", "nome": "Registrar vendas"},
    {"codigo": "aplicar_desconto", "nome": "Aplicar desconto manual ate 10%"},
    {"codigo": "autorizar_desconto", "nome": "Autorizar desconto manual ate 100%"},
    {"codigo": "cancelar_venda", "nome": "Cancelar vendas"},
    {"codigo": "cancelar_item_venda", "nome": "Cancelar itens de venda"},
    {"codigo": "visualizar_cupom", "nome": "Visualizar cupons"},
    {"codigo": "criar_cupom", "nome": "Criar cupons"},
    {"codigo": "editar_cupom", "nome": "Editar cupons"},
    {"codigo": "excluir_cupom", "nome": "Excluir cupons"},
    {"codigo": "visualizar_cliente", "nome": "Visualizar clientes"},
    {"codigo": "criar_cliente", "nome": "Criar clientes"},
    {"codigo": "editar_cliente", "nome": "Editar clientes"},
    {"codigo": "excluir_cliente", "nome": "Excluir clientes"},
    {"codigo": "enviar_mensagem_cliente", "nome": "Enviar mensagens para clientes"},
    {"codigo": "gerenciar_configuracao_cliente", "nome": "Gerenciar configuracoes de clientes"},
    {"codigo": "visualizar_financeiro", "nome": "Visualizar financeiro"},
    {"codigo": "criar_lancamento_financeiro", "nome": "Criar lancamentos financeiros"},
    {"codigo": "fechar_caixa", "nome": "Fechar caixa"},
    {"codigo": "visualizar_fiscal", "nome": "Visualizar fiscal"},
    {"codigo": "gerenciar_fiscal", "nome": "Gerenciar fiscal"},
    {"codigo": "visualizar_adiantamento", "nome": "Visualizar adiantamentos"},
    {"codigo": "criar_adiantamento", "nome": "Criar adiantamentos"},
    {"codigo": "visualizar_relatorio_financeiro", "nome": "Visualizar relatorios financeiros"},
    {"codigo": "visualizar_notificacao", "nome": "Visualizar notificacoes"},
    {"codigo": "gerenciar_alerta_estoque", "nome": "Gerenciar configuracoes de alertas"},
    {"codigo": "cancelar_movimentacao_estoque", "nome": "Cancelar movimentacoes de estoque"},
    {"codigo": "visualizar_importacao_exportacao", "nome": "Visualizar importacao e exportacao"},
    {"codigo": "importar_dados_cadastrais", "nome": "Importar dados cadastrais"},
    {"codigo": "exportar_dados_cadastrais", "nome": "Exportar dados cadastrais"},
    {"codigo": "visualizar_todas_empresas", "nome": "Visualizar dados de todas as empresas"},
]


PERMISSION_GROUP_DEFINITIONS = [
    {
        "grupo": "pdv",
        "titulo": "PDV",
        "descricao": "Atendimento no caixa, vendas e cupons promocionais.",
        "permissions": [
            {
                "codigo": "aplicar_desconto",
                "titulo": "Desconto ate 10%",
                "descricao": "Permite desconto manual limitado a 10% do subtotal.",
                "depends_on": ["visualizar_pdv", "registrar_venda"],
            },
            {
                "codigo": "autorizar_desconto",
                "titulo": "Desconto ate 100%",
                "descricao": "Autoriza desconto manual acima de 10%, limitado ao subtotal.",
                "depends_on": ["visualizar_pdv", "registrar_venda", "aplicar_desconto"],
            },
            {
                "codigo": "visualizar_pdv",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo do PDV.",
                "kind": "general",
            },
            {
                "codigo": "registrar_venda",
                "titulo": "Registrar vendas",
                "descricao": "Permite montar carrinho, abrir pagamento e finalizar vendas.",
                "depends_on": ["visualizar_pdv"],
            },
            {
                "codigo": "cancelar_venda",
                "titulo": "Cancelar vendas",
                "descricao": "Permite cancelar vendas ja registradas no caixa.",
                "depends_on": ["visualizar_pdv"],
            },
            {
                "codigo": "cancelar_item_venda",
                "titulo": "Cancelar itens da venda",
                "descricao": "Permite devolucao ou cancelamento parcial de itens da venda.",
                "depends_on": ["visualizar_pdv", "cancelar_venda"],
            },
            {
                "codigo": "visualizar_cupom",
                "titulo": "Cupons",
                "descricao": "Libera a tela de cupons dentro do contexto do PDV.",
                "depends_on": ["visualizar_pdv"],
            },
            {
                "codigo": "criar_cupom",
                "titulo": "Criar cupons",
                "descricao": "Permite cadastrar cupons promocionais.",
                "depends_on": ["visualizar_pdv", "visualizar_cupom"],
            },
            {
                "codigo": "editar_cupom",
                "titulo": "Editar cupons",
                "descricao": "Permite alterar regras e valores dos cupons.",
                "depends_on": ["visualizar_pdv", "visualizar_cupom"],
            },
            {
                "codigo": "excluir_cupom",
                "titulo": "Excluir cupons",
                "descricao": "Permite remover cupons existentes.",
                "depends_on": ["visualizar_pdv", "visualizar_cupom"],
            },
        ],
    },
    {
        "grupo": "clientes",
        "titulo": "Clientes",
        "descricao": "Cadastro de clientes, carteira, historico e comunicacao.",
        "permissions": [
            {
                "codigo": "visualizar_cliente",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de clientes.",
                "kind": "general",
            },
            {
                "codigo": "criar_cliente",
                "titulo": "Criar clientes",
                "descricao": "Permite cadastrar novos clientes.",
                "depends_on": ["visualizar_cliente"],
            },
            {
                "codigo": "editar_cliente",
                "titulo": "Editar clientes",
                "descricao": "Permite atualizar dados cadastrais do cliente.",
                "depends_on": ["visualizar_cliente"],
            },
            {
                "codigo": "excluir_cliente",
                "titulo": "Inativar clientes",
                "descricao": "Permite remover o cliente da operacao diaria.",
                "depends_on": ["visualizar_cliente"],
            },
            {
                "codigo": "enviar_mensagem_cliente",
                "titulo": "Enviar mensagens",
                "descricao": "Permite enviar SMS, WhatsApp e email para clientes.",
                "depends_on": ["visualizar_cliente"],
            },
            {
                "codigo": "gerenciar_configuracao_cliente",
                "titulo": "Configurar canais e cashback",
                "descricao": "Permite alterar cashback, cancelamentos e servidores de comunicacao por empresa.",
                "depends_on": ["visualizar_cliente"],
            },
        ],
    },
    {
        "grupo": "estoque",
        "titulo": "Estoque",
        "descricao": "Produtos, movimentacoes, categorias e alertas operacionais.",
        "permissions": [
            {
                "codigo": "visualizar_produto",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de estoque e produtos.",
                "kind": "general",
            },
            {
                "codigo": "criar_produto",
                "titulo": "Criar produtos",
                "descricao": "Permite cadastrar novos produtos no estoque.",
                "depends_on": ["visualizar_produto"],
            },
            {
                "codigo": "editar_produto",
                "titulo": "Editar produtos",
                "descricao": "Permite editar produto, saldo e movimentacao manual.",
                "depends_on": ["visualizar_produto"],
            },
            {
                "codigo": "excluir_produto",
                "titulo": "Excluir produtos",
                "descricao": "Permite excluir produtos do cadastro.",
                "depends_on": ["visualizar_produto"],
            },
            {
                "codigo": "visualizar_categoria",
                "titulo": "Categorias",
                "descricao": "Libera a tela de categorias do estoque.",
                "depends_on": ["visualizar_produto"],
            },
            {
                "codigo": "criar_categoria",
                "titulo": "Criar categorias",
                "descricao": "Permite cadastrar categorias de produtos.",
                "depends_on": ["visualizar_produto", "visualizar_categoria"],
            },
            {
                "codigo": "editar_categoria",
                "titulo": "Editar categorias",
                "descricao": "Permite alterar categorias ja existentes.",
                "depends_on": ["visualizar_produto", "visualizar_categoria"],
            },
            {
                "codigo": "excluir_categoria",
                "titulo": "Excluir categorias",
                "descricao": "Permite remover categorias cadastradas.",
                "depends_on": ["visualizar_produto", "visualizar_categoria"],
            },
            {
                "codigo": "visualizar_notificacao",
                "titulo": "Notificacoes",
                "descricao": "Libera alertas de estoque baixo, vencimento e popup.",
                "depends_on": ["visualizar_produto"],
            },
            {
                "codigo": "gerenciar_alerta_estoque",
                "titulo": "Configurar alertas",
                "descricao": "Permite alterar regras e configuracoes das notificacoes.",
                "depends_on": ["visualizar_produto", "visualizar_notificacao"],
            },
            {
                "codigo": "cancelar_movimentacao_estoque",
                "titulo": "Cancelar movimentacoes",
                "descricao": "Permite reverter movimentacoes manuais e transferencias operacionais.",
                "depends_on": ["visualizar_produto", "editar_produto"],
            },
        ],
    },
    {
        "grupo": "financeiro",
        "titulo": "Financeiro",
        "descricao": "Fluxo de caixa, lancamentos, fechamento e relatorios.",
        "permissions": [
            {
                "codigo": "visualizar_financeiro",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo financeiro.",
                "kind": "general",
            },
            {
                "codigo": "criar_lancamento_financeiro",
                "titulo": "Lancamentos",
                "descricao": "Permite registrar entradas e saidas manuais.",
                "depends_on": ["visualizar_financeiro"],
            },
            {
                "codigo": "fechar_caixa",
                "titulo": "Fechamento de caixa",
                "descricao": "Permite registrar fechamento e saldo contado.",
                "depends_on": ["visualizar_financeiro"],
            },
            {
                "codigo": "visualizar_relatorio_financeiro",
                "titulo": "Relatorios",
                "descricao": "Libera relatorios e impressoes do financeiro.",
                "depends_on": ["visualizar_financeiro"],
            },
        ],
    },
    {
        "grupo": "fiscal",
        "titulo": "Fiscal",
        "descricao": "Configuracoes fiscais, base para NFC-e e prevalidacao de vendas.",
        "permissions": [
            {
                "codigo": "visualizar_fiscal",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo fiscal.",
                "kind": "general",
            },
            {
                "codigo": "gerenciar_fiscal",
                "titulo": "Configurar fiscal",
                "descricao": "Permite alterar dados fiscais por empresa e rodar prevalidacao de emissao.",
                "depends_on": ["visualizar_fiscal"],
            },
        ],
    },
    {
        "grupo": "adiantamentos",
        "titulo": "Adiantamentos",
        "descricao": "Vales em dinheiro ou produto com reflexo financeiro.",
        "permissions": [
            {
                "codigo": "visualizar_adiantamento",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de adiantamentos.",
                "kind": "general",
            },
            {
                "codigo": "criar_adiantamento",
                "titulo": "Criar adiantamentos",
                "descricao": "Permite registrar vales e adiantamentos para funcionarios.",
                "depends_on": ["visualizar_adiantamento"],
            },
        ],
    },
    {
        "grupo": "importacao_exportacao",
        "titulo": "Importacao e exportacao",
        "descricao": "Carga em lote, planilhas e extracao de dados.",
        "permissions": [
            {
                "codigo": "visualizar_importacao_exportacao",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de importacao e exportacao.",
                "kind": "general",
            },
            {
                "codigo": "importar_dados_cadastrais",
                "titulo": "Importar dados",
                "descricao": "Permite importar planilhas e atualizar cadastros em lote.",
                "depends_on": ["visualizar_importacao_exportacao"],
            },
            {
                "codigo": "exportar_dados_cadastrais",
                "titulo": "Exportar dados",
                "descricao": "Permite gerar planilhas de exportacao.",
                "depends_on": ["visualizar_importacao_exportacao"],
            },
        ],
    },
    {
        "grupo": "funcionarios",
        "titulo": "Funcionarios",
        "descricao": "Equipe operacional, vinculos e dados de acesso.",
        "permissions": [
            {
                "codigo": "visualizar_funcionario",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de funcionarios.",
                "kind": "general",
            },
            {
                "codigo": "criar_funcionario",
                "titulo": "Criar funcionarios",
                "descricao": "Permite cadastrar novos funcionarios.",
                "depends_on": ["visualizar_funcionario"],
            },
            {
                "codigo": "editar_funcionario",
                "titulo": "Editar funcionarios",
                "descricao": "Permite alterar dados e vinculos da equipe.",
                "depends_on": ["visualizar_funcionario"],
            },
            {
                "codigo": "excluir_funcionario",
                "titulo": "Excluir funcionarios",
                "descricao": "Permite remover funcionarios do cadastro.",
                "depends_on": ["visualizar_funcionario"],
            },
        ],
    },
    {
        "grupo": "roles",
        "titulo": "Roles",
        "descricao": "Perfis de acesso e combinacoes de permissoes.",
        "permissions": [
            {
                "codigo": "visualizar_role",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de roles.",
                "kind": "general",
            },
            {
                "codigo": "criar_role",
                "titulo": "Criar roles",
                "descricao": "Permite cadastrar novos perfis de acesso.",
                "depends_on": ["visualizar_role"],
            },
            {
                "codigo": "editar_role",
                "titulo": "Editar roles",
                "descricao": "Permite alterar permissoes e dados das roles.",
                "depends_on": ["visualizar_role"],
            },
            {
                "codigo": "excluir_role",
                "titulo": "Excluir roles",
                "descricao": "Permite excluir roles sem funcionarios vinculados.",
                "depends_on": ["visualizar_role"],
            },
        ],
    },
    {
        "grupo": "permissions",
        "titulo": "Permissions",
        "descricao": "Cadastro tecnico de permissoes disponiveis no tenant.",
        "permissions": [
            {
                "codigo": "visualizar_permission",
                "titulo": "Geral",
                "descricao": "Libera a entrada no modulo de permissions.",
                "kind": "general",
            },
            {
                "codigo": "criar_permission",
                "titulo": "Criar permissions",
                "descricao": "Permite cadastrar novas permissions tecnicas.",
                "depends_on": ["visualizar_permission"],
            },
            {
                "codigo": "editar_permission",
                "titulo": "Editar permissions",
                "descricao": "Permite alterar permissions existentes.",
                "depends_on": ["visualizar_permission"],
            },
            {
                "codigo": "excluir_permission",
                "titulo": "Excluir permissions",
                "descricao": "Permite excluir permissions sem uso.",
                "depends_on": ["visualizar_permission"],
            },
        ],
    },
    {
        "grupo": "escopo",
        "titulo": "Escopo geral",
        "descricao": "Permissoes amplas que afetam o alcance dos dados.",
        "permissions": [
            {
                "codigo": "visualizar_todas_empresas",
                "titulo": "Todas as empresas",
                "descricao": "Permite consultar dados de todas as empresas do tenant.",
                "kind": "general",
            },
        ],
    },
]


DEFAULT_ROLE_DEFINITIONS = [
    {
        "codigo": "administrador",
        "nome": "Administrador",
        "descricao": "Acesso completo ao sistema.",
        "permissoes": [item["codigo"] for item in DEFAULT_PERMISSION_DEFINITIONS],
    },
    {
        "codigo": "operador",
        "nome": "Operador",
        "descricao": "Opera estoque e catalogo sem gerenciar usuarios.",
        "permissoes": [
            "visualizar_categoria",
            "criar_categoria",
            "editar_categoria",
            "excluir_categoria",
            "visualizar_produto",
            "criar_produto",
            "editar_produto",
            "excluir_produto",
            "visualizar_pdv",
            "registrar_venda",
            "visualizar_cupom",
            "criar_cupom",
            "editar_cupom",
            "visualizar_financeiro",
            "criar_lancamento_financeiro",
            "fechar_caixa",
            "visualizar_adiantamento",
            "criar_adiantamento",
            "visualizar_relatorio_financeiro",
            "visualizar_notificacao",
            "visualizar_importacao_exportacao",
            "importar_dados_cadastrais",
            "exportar_dados_cadastrais",
        ],
    },
]


ADMIN_ROLE_CODE = "administrador"
VISUALIZAR_TODAS_EMPRESAS = "visualizar_todas_empresas"

_PERMISSION_NAME_BY_CODE = {
    item["codigo"]: item["nome"]
    for item in DEFAULT_PERMISSION_DEFINITIONS
}

_PERMISSION_METADATA_BY_CODE = {}

for group_order, group in enumerate(PERMISSION_GROUP_DEFINITIONS, start=1):
    for permission_order, permission in enumerate(group["permissions"], start=1):
        _PERMISSION_METADATA_BY_CODE[permission["codigo"]] = {
            "codigo": permission["codigo"],
            "nome_padrao": _PERMISSION_NAME_BY_CODE.get(permission["codigo"], permission.get("titulo") or permission["codigo"]),
            "titulo": permission.get("titulo") or _PERMISSION_NAME_BY_CODE.get(permission["codigo"], permission["codigo"]),
            "descricao": permission.get("descricao"),
            "kind": permission.get("kind", "specific"),
            "depends_on": list(permission.get("depends_on", [])),
            "grupo": group["grupo"],
            "grupo_titulo": group["titulo"],
            "grupo_descricao": group.get("descricao"),
            "grupo_ordem": group_order,
            "ordem": permission_order,
        }


def get_permission_metadata(permission_code):
    return _PERMISSION_METADATA_BY_CODE.get(permission_code)


def get_permission_dependency_codes(permission_code):
    metadata = get_permission_metadata(permission_code) or {}
    return list(metadata.get("depends_on", []))


def get_permission_name(permission_code):
    metadata = get_permission_metadata(permission_code) or {}
    return metadata.get("nome_padrao") or permission_code


def normalize_permission_codes(permission_codes):
    granted_codes = {
        str(code).strip()
        for code in (permission_codes or [])
        if str(code).strip()
    }
    cache = {}

    def _is_effective(permission_code, trail=None):
        if permission_code not in granted_codes:
            return False

        if permission_code in cache:
            return cache[permission_code]

        trail = trail or set()
        if permission_code in trail:
            cache[permission_code] = False
            return False

        metadata = get_permission_metadata(permission_code)
        if not metadata:
            cache[permission_code] = True
            return True

        dependencies = metadata.get("depends_on", [])
        if not dependencies:
            cache[permission_code] = True
            return True

        effective = all(
            _is_effective(dependency_code, trail | {permission_code})
            for dependency_code in dependencies
        )
        cache[permission_code] = effective
        return effective

    return {
        code
        for code in granted_codes
        if _is_effective(code)
    }


def build_permission_groups(permission_records):
    records_by_code = {
        permission.codigo: permission
        for permission in (permission_records or [])
    }
    rendered_groups = []
    used_codes = set()

    for group in PERMISSION_GROUP_DEFINITIONS:
        permissions = []
        for permission in group["permissions"]:
            record = records_by_code.get(permission["codigo"])
            if not record:
                continue

            metadata = get_permission_metadata(permission["codigo"]) or {}
            permissions.append({
                "id": record.id,
                "nome": record.nome,
                "codigo": record.codigo,
                "descricao": record.descricao,
                "ativo": record.ativo,
                "titulo": metadata.get("titulo") or record.nome,
                "ajuda": metadata.get("descricao") or record.descricao,
                "kind": metadata.get("kind", "specific"),
                "depends_on_codes": metadata.get("depends_on", []),
                "grupo": metadata.get("grupo"),
                "grupo_titulo": metadata.get("grupo_titulo"),
                "ordem": metadata.get("ordem", 999),
            })
            used_codes.add(record.codigo)

        if permissions:
            rendered_groups.append({
                "grupo": group["grupo"],
                "titulo": group["titulo"],
                "descricao": group.get("descricao"),
                "permissions": permissions,
            })

    remaining_permissions = [
        permission
        for permission in (permission_records or [])
        if permission.codigo not in used_codes
    ]
    if remaining_permissions:
        rendered_groups.append({
            "grupo": "outros",
            "titulo": "Outros",
            "descricao": "Permissoes sem agrupamento definido.",
            "permissions": [
                {
                    "id": permission.id,
                    "nome": permission.nome,
                    "codigo": permission.codigo,
                    "descricao": permission.descricao,
                    "ativo": permission.ativo,
                    "titulo": permission.nome or permission.codigo,
                    "ajuda": permission.descricao,
                    "kind": "specific",
                    "depends_on_codes": [],
                    "grupo": "outros",
                    "grupo_titulo": "Outros",
                    "ordem": 999,
                }
                for permission in sorted(remaining_permissions, key=lambda item: (item.nome or item.codigo or "").lower())
            ],
        })

    return rendered_groups
