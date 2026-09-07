from app.models.db import CategoriaProduto, Produto
from app.repositorys.categoria_repository import CategoriaRepository
from app.services.acesso_empresa_service import AcessoEmpresaService
from app.services.time_service import TimeService


from app.services.transaction_service import atomic_operation


class CategoriaService:

    @staticmethod
    def listar(tenant_id, escopo):
        empresa_ids = AcessoEmpresaService.filtrar_empresa_ids(escopo)
        return CategoriaRepository.listar_por_tenant(tenant_id, empresa_ids)

    @staticmethod
    @atomic_operation
    def criar(data, tenant_id):
        CategoriaService._validar(data, tenant_id)
        categoria = CategoriaProduto(
            nome=(data.get("nome") or "").strip(),
            descricao=(data.get("descricao") or "").strip() or None,
            ativo=True,
            criado_em=TimeService.now_utc_naive(),
            atualizado_em=TimeService.now_utc_naive(),
            tenant_id=tenant_id
        )
        return CategoriaRepository.criar(categoria)

    @staticmethod
    @atomic_operation
    def atualizar(categoria_id, data, tenant_id):
        CategoriaService._validar(data, tenant_id, categoria_id)
        categoria = CategoriaRepository.buscar_por_id(categoria_id, tenant_id)
        if not categoria:
            raise ValueError("Categoria nao encontrada.")

        categoria.nome = (data.get("nome") or "").strip()
        categoria.descricao = (data.get("descricao") or "").strip() or None
        categoria.atualizado_em = TimeService.now_utc_naive()

        CategoriaRepository.atualizar()
        return categoria

    @staticmethod
    @atomic_operation
    def deletar(categoria_id, tenant_id):
        categoria = CategoriaRepository.buscar_por_id(categoria_id, tenant_id)
        if not categoria:
            raise ValueError("Categoria nao encontrada.")

        if Produto.query.filter_by(tenant_id=tenant_id, categoria_id=categoria.id).first():
            raise ValueError("Categoria vinculada a produtos nao pode ser excluida.")
        CategoriaRepository.deletar(categoria)

    @staticmethod
    def _validar(data, tenant_id, categoria_id=None):
        nome = (data.get("nome") or "").strip()
        if not nome or len(nome) > 100:
            raise ValueError("Nome da categoria deve ter entre 1 e 100 caracteres.")
        if len(data.get("descricao") or "") > 255:
            raise ValueError("Descricao da categoria deve ter ate 255 caracteres.")
        duplicate = CategoriaProduto.query.filter_by(tenant_id=tenant_id, nome=nome).first()
        if duplicate and duplicate.id != categoria_id:
            raise ValueError("Ja existe uma categoria com esse nome.")
