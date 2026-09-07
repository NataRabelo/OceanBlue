from decimal import Decimal, InvalidOperation

from app.models.db import Funcionario, FuncionarioEmpresa
from app.repositorys.funcionario_repository import FuncionarioRepository
from app.security.password import generate_password_hash
from app.security.password import validate_password
from app.extensions import db


from app.services.transaction_service import atomic_operation


class FuncionarioService:

    @staticmethod
    def listar(tenant_id):
        vinculos = FuncionarioRepository.listar_por_tenant(tenant_id)
        funcionarios = {}

        for vinculo in vinculos:
            funcionario = vinculo.funcionario
            empresa = vinculo.empresa
            role = funcionario.role

            if funcionario.id not in funcionarios:
                funcionarios[funcionario.id] = {
                    "id": vinculo.id,
                    "funcionario_id": funcionario.id,
                    "empresa_id": empresa.id if empresa else None,
                    "empresa_nome": empresa.nome_fantasia if empresa else "",
                    "empresa_nomes": [],
                    "empresa_ids": [],
                    "quantidade_empresas": 0,
                    "empresa_resumo": empresa.nome_fantasia if empresa else "",
                    "nome": funcionario.nome,
                    "cpf": funcionario.cpf,
                    "usuario": funcionario.usuario,
                    "salario": str(FuncionarioService._to_decimal_value(funcionario.salario)),
                    "meta": str(FuncionarioService._to_decimal_value(funcionario.meta)),
                    "ativo": funcionario.ativo,
                    "role_id": role.id if role else None,
                    "role_nome": role.nome if role else "",
                    "role_codigo": role.codigo if role else "",
                }

            item = funcionarios[funcionario.id]

            if empresa:
                item["empresa_ids"].append(empresa.id)
                item["empresa_nomes"].append(empresa.nome_fantasia)
                item["quantidade_empresas"] += 1

        for item in funcionarios.values():
            if item["quantidade_empresas"] > 1:
                item["empresa_nome"] = ", ".join(item["empresa_nomes"])
                item["empresa_resumo"] = f"{item['quantidade_empresas']} empresas"
            elif item["empresa_nomes"]:
                item["empresa_resumo"] = item["empresa_nomes"][0]

        return list(funcionarios.values())

    @staticmethod
    def listar_empresas(tenant_id):
        return FuncionarioRepository.listar_empresas_por_tenant(tenant_id)

    @staticmethod
    def listar_roles(tenant_id):
        return FuncionarioRepository.listar_roles_por_tenant(tenant_id)

    @staticmethod
    @atomic_operation
    def criar(data, tenant_id):
        try:
            nome = (data.get("nome") or "").strip()
            cpf = FuncionarioService._normalizar_cpf(data.get("cpf"))
            usuario = (data.get("usuario") or "").strip()
            senha = (data.get("senha") or "").strip()
            empresa_id = FuncionarioService._to_int(data.get("empresa_id"), "Empresa")
            role_id = FuncionarioService._to_int(data.get("role_id"), "Role")
            salario = FuncionarioService._to_non_negative_decimal(data.get("salario"), "salario")
            meta = FuncionarioService._to_non_negative_decimal(data.get("meta"), "meta")
            ativo = FuncionarioService._to_bool(data.get("ativo", True))

            if not nome:
                raise ValueError("Nome do funcionario e obrigatorio.")
            if not cpf:
                raise ValueError("CPF e obrigatorio.")
            if not usuario:
                raise ValueError("Usuario e obrigatorio.")
            if not senha:
                raise ValueError("Senha e obrigatoria.")
            validate_password(senha)
            if not empresa_id:
                raise ValueError("Empresa e obrigatoria.")
            if not role_id:
                raise ValueError("Role e obrigatoria.")

            if FuncionarioRepository.buscar_cpf_duplicado(cpf, tenant_id):
                raise ValueError("CPF ja cadastrado no sistema.")

            if FuncionarioRepository.buscar_funcionario_duplicado(usuario, tenant_id):
                raise ValueError("Nome de usuario ja cadastrado no sistema.")

            empresa = FuncionarioRepository.buscar_empresa_por_id(empresa_id, tenant_id)
            if not empresa or not empresa.ativo:
                raise ValueError("Empresa nao encontrada.")

            role = FuncionarioRepository.buscar_role_por_id(role_id, tenant_id)
            if not role or not role.ativo:
                raise ValueError("Role nao encontrada.")

            funcionario = Funcionario(
                tenant_id=tenant_id,
                role_id=role.id,
                nome=nome,
                cpf=cpf,
                usuario=usuario,
                senha_hash=generate_password_hash(senha),
                salario=salario,
                meta=meta,
                ativo=ativo
            )
            FuncionarioRepository.adicionar(funcionario)
            db.session.flush()

            funcionario_empresa = FuncionarioEmpresa(
                tenant_id=tenant_id,
                funcionario_id=funcionario.id,
                empresa_id=empresa.id,
                ativo=True
            )
            FuncionarioRepository.adicionar(funcionario_empresa)
            db.session.flush()
            FuncionarioService._sincronizar_empresas(funcionario, data, tenant_id, empresa.id)
            FuncionarioRepository.salvar()

            return FuncionarioRepository.buscar_funcionario_empresa_por_id(funcionario_empresa.id, tenant_id)
        except Exception:
            FuncionarioRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def atualizar(funcionario_empresa_id, data, tenant_id):
        try:
            funcionario_empresa = FuncionarioRepository.buscar_funcionario_empresa_por_id(funcionario_empresa_id, tenant_id)
            if not funcionario_empresa:
                raise ValueError("Funcionario nao encontrado.")

            funcionario = funcionario_empresa.funcionario

            nome = (data.get("nome") or "").strip()
            cpf = FuncionarioService._normalizar_cpf(data.get("cpf"))
            usuario = (data.get("usuario") or "").strip()
            senha = (data.get("senha") or "").strip()
            empresa_id = FuncionarioService._to_int(data.get("empresa_id"), "Empresa")
            role_id = FuncionarioService._to_int(data.get("role_id"), "Role")
            salario = FuncionarioService._to_non_negative_decimal(data.get("salario"), "salario")
            meta = FuncionarioService._to_non_negative_decimal(data.get("meta"), "meta")
            ativo = FuncionarioService._to_bool(data.get("ativo", True))

            if not nome:
                raise ValueError("Nome do funcionario e obrigatorio.")
            if not cpf:
                raise ValueError("CPF e obrigatorio.")
            if not usuario:
                raise ValueError("Usuario e obrigatorio.")
            if not empresa_id:
                raise ValueError("Empresa e obrigatoria.")
            if not role_id:
                raise ValueError("Role e obrigatoria.")

            cpf_duplicado = FuncionarioRepository.buscar_cpf_duplicado(
                cpf,
                tenant_id,
                ignorar_funcionario_id=funcionario.id
            )
            if cpf_duplicado:
                raise ValueError("CPF ja cadastrado no sistema.")

            usuario_duplicado = FuncionarioRepository.buscar_funcionario_duplicado(
                usuario,
                tenant_id,
                ignorar_funcionario_id=funcionario.id
            )
            if usuario_duplicado:
                raise ValueError("Nome de usuario ja cadastrado no sistema.")

            empresa = FuncionarioRepository.buscar_empresa_por_id(empresa_id, tenant_id)
            if not empresa or not empresa.ativo:
                raise ValueError("Empresa nao encontrada.")

            role = FuncionarioRepository.buscar_role_por_id(role_id, tenant_id)
            if not role or not role.ativo:
                raise ValueError("Role nao encontrada.")

            funcionario.nome = nome
            funcionario.cpf = cpf
            funcionario.usuario = usuario
            funcionario.role_id = role.id
            funcionario.salario = salario
            funcionario.meta = meta
            funcionario.ativo = ativo

            if senha:
                validate_password(senha)
                funcionario.senha_hash = generate_password_hash(senha)

            if "empresa_ids" not in data and funcionario_empresa.empresa_id != empresa.id:
                data = {**data, "empresa_ids": [empresa.id]}
            funcionario_empresa.ativo = ativo

            FuncionarioService._sincronizar_empresas(funcionario, data, tenant_id, empresa.id)
            if funcionario_empresa.empresa_id not in set(data.get("empresa_ids", [funcionario_empresa.empresa_id])):
                funcionario_empresa = FuncionarioEmpresa.query.filter_by(
                    tenant_id=tenant_id, funcionario_id=funcionario.id, empresa_id=empresa.id
                ).first()

            FuncionarioRepository.salvar()
            return FuncionarioRepository.buscar_funcionario_empresa_por_id(funcionario_empresa.id, tenant_id)
        except Exception:
            FuncionarioRepository.rollback()
            raise

    @staticmethod
    @atomic_operation
    def deletar(funcionario_empresa_id, tenant_id):
        try:
            funcionario_empresa = FuncionarioRepository.buscar_funcionario_empresa_por_id(funcionario_empresa_id, tenant_id)
            if not funcionario_empresa:
                raise ValueError("Funcionario nao encontrado.")

            funcionario_id = funcionario_empresa.funcionario_id
            funcionario = funcionario_empresa.funcionario

            FuncionarioService._validar_exclusao_vinculo(funcionario_id, funcionario_empresa.empresa_id, tenant_id)
            FuncionarioRepository.deletar(funcionario_empresa)
            db.session.flush()

            total_vinculos = FuncionarioRepository.contar_vinculos_funcionario(funcionario_id, tenant_id)
            if total_vinculos == 0 and funcionario is not None:
                FuncionarioRepository.deletar(funcionario)
                FuncionarioRepository.salvar()
        except Exception:
            FuncionarioRepository.rollback()
            raise

    @staticmethod
    def _validar_exclusao_vinculo(funcionario_id, empresa_id, tenant_id):
        for table in db.metadata.tables.values():
            if table.name == "funcionarios_empresa":
                continue
            references = [foreign.parent for foreign in table.foreign_keys
                          if foreign.target_fullname == "funcionarios.id"]
            if not references:
                continue
            query = db.select(table).where(db.or_(*(column == funcionario_id for column in references)))
            if "tenant_id" in table.c:
                query = query.where(table.c.tenant_id == tenant_id)
            if "empresa_id" in table.c:
                query = query.where(table.c.empresa_id == empresa_id)
            if db.session.execute(query.limit(1)).first():
                raise ValueError("Funcionario com historico deve ser desativado, preservando seu vinculo.")

    @staticmethod
    def _sincronizar_empresas(funcionario, data, tenant_id, empresa_id):
        if "empresa_ids" not in data:
            return
        values = data["empresa_ids"]
        if not isinstance(values, list) or not values:
            raise ValueError("Informe ao menos uma empresa.")
        empresa_ids = {FuncionarioService._to_int(value, "Empresa") for value in values}
        if empresa_id not in empresa_ids:
            raise ValueError("A empresa principal deve estar entre os vinculos.")
        for company_id in empresa_ids:
            company = FuncionarioRepository.buscar_empresa_por_id(company_id, tenant_id)
            if not company or not company.ativo:
                raise ValueError("Empresa indisponivel neste tenant.")
        links = FuncionarioEmpresa.query.filter_by(tenant_id=tenant_id, funcionario_id=funcionario.id).all()
        for link in links:
            if link.empresa_id not in empresa_ids:
                FuncionarioService._validar_exclusao_vinculo(funcionario.id, link.empresa_id, tenant_id)
                db.session.delete(link)
            else:
                link.ativo = funcionario.ativo
        existing = {link.empresa_id for link in links}
        for company_id in sorted(empresa_ids - existing):
            db.session.add(FuncionarioEmpresa(tenant_id=tenant_id, funcionario_id=funcionario.id,
                                              empresa_id=company_id, ativo=funcionario.ativo))

    @staticmethod
    def _to_bool(value, default=False):
        if value is None:
            return default

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in ["1", "true", "on", "sim", "yes"]

    @staticmethod
    def _to_int(value, field_name):
        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} invalida.")

    @staticmethod
    def _normalizar_cpf(value):
        cpf = "".join(char for char in str(value or "") if char.isdigit())
        if len(cpf) != 11:
            raise ValueError("CPF deve conter 11 digitos.")
        return cpf

    @staticmethod
    def _to_non_negative_decimal(value, field_name):
        if value in (None, ""):
            return Decimal("0.00")

        try:
            valor = Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor invalido para {field_name}.")

        if not valor.is_finite() or valor < 0 or valor >= Decimal("10000000000"):
            raise ValueError(f"{field_name.capitalize()} nao pode ser negativo.")

        return valor.quantize(Decimal("0.01"))

    @staticmethod
    def _to_decimal_value(value):
        try:
            return Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return Decimal("0.00")
