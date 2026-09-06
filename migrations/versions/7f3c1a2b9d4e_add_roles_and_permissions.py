"""add roles and permissions

Revision ID: 7f3c1a2b9d4e
Revises: 1150177c20ca
Create Date: 2026-04-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7f3c1a2b9d4e"
down_revision = "1150177c20ca"
branch_labels = None
depends_on = None


permission_definitions = [
    ("visualizar_funcionario", "Visualizar funcionarios"),
    ("criar_funcionario", "Criar funcionarios"),
    ("editar_funcionario", "Editar funcionarios"),
    ("excluir_funcionario", "Excluir funcionarios"),
    ("visualizar_categoria", "Visualizar categorias"),
    ("criar_categoria", "Criar categorias"),
    ("editar_categoria", "Editar categorias"),
    ("excluir_categoria", "Excluir categorias"),
    ("visualizar_produto", "Visualizar produtos"),
    ("criar_produto", "Criar produtos"),
    ("editar_produto", "Editar produtos"),
    ("excluir_produto", "Excluir produtos"),
    ("visualizar_role", "Visualizar roles"),
    ("criar_role", "Criar roles"),
    ("editar_role", "Editar roles"),
    ("excluir_role", "Excluir roles"),
    ("visualizar_permission", "Visualizar permissions"),
    ("criar_permission", "Criar permissions"),
    ("editar_permission", "Editar permissions"),
    ("excluir_permission", "Excluir permissions"),
    ("visualizar_todas_empresas", "Visualizar dados de todas as empresas"),
]

role_definitions = [
    (
        "administrador",
        "Administrador",
        "Acesso completo ao sistema.",
        [codigo for codigo, _ in permission_definitions],
    ),
    (
        "operador",
        "Operador",
        "Opera estoque e catalogo sem gerenciar usuarios.",
        [
            "visualizar_categoria",
            "criar_categoria",
            "editar_categoria",
            "excluir_categoria",
            "visualizar_produto",
            "criar_produto",
            "editar_produto",
            "excluir_produto",
        ],
    ),
]


def upgrade():
    op.create_table(
        "permissions",
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("codigo", sa.String(length=120), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_permission_tenant_codigo"),
    )
    with op.batch_alter_table("permissions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_permissions_tenant_id"), ["tenant_id"], unique=False)

    op.create_table(
        "role",
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("codigo", sa.String(length=80), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "codigo", name="uq_role_tenant_codigo"),
        sa.UniqueConstraint("tenant_id", "nome", name="uq_role_tenant_nome"),
    )
    with op.batch_alter_table("role", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_role_tenant_id"), ["tenant_id"], unique=False)

    op.create_table(
        "role_permission",
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["role.id"]),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role_id", "permission_id", name="uq_role_permission"),
    )
    with op.batch_alter_table("role_permission", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_role_permission_tenant_id"), ["tenant_id"], unique=False)

    with op.batch_alter_table("funcionarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_funcionarios_role_id_role", "role", ["role_id"], ["id"])

    connection = op.get_bind()
    tenants = connection.execute(sa.text("SELECT id FROM tenants")).fetchall()

    for tenant in tenants:
        tenant_id = tenant[0]
        permission_ids = {}

        for codigo, nome in permission_definitions:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO permissions (nome, codigo, descricao, ativo, criado_em, atualizado_em, tenant_id)
                    VALUES (:nome, :codigo, :descricao, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :tenant_id)
                    """
                ),
                {
                    "nome": nome,
                    "codigo": codigo,
                    "descricao": None,
                    "tenant_id": tenant_id,
                }
            )
            permission_ids[codigo] = connection.execute(
                sa.text(
                    """
                    SELECT id FROM permissions
                    WHERE tenant_id = :tenant_id AND codigo = :codigo
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "codigo": codigo,
                }
            ).scalar_one()

        role_ids = {}
        for codigo, nome, descricao, permissions in role_definitions:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO role (nome, codigo, descricao, ativo, criado_em, atualizado_em, tenant_id)
                    VALUES (:nome, :codigo, :descricao, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :tenant_id)
                    """
                ),
                {
                    "nome": nome,
                    "codigo": codigo,
                    "descricao": descricao,
                    "tenant_id": tenant_id,
                }
            )
            role_id = connection.execute(
                sa.text(
                    """
                    SELECT id FROM role
                    WHERE tenant_id = :tenant_id AND codigo = :codigo
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "codigo": codigo,
                }
            ).scalar_one()
            role_ids[codigo] = role_id

            for permission_code in permissions:
                connection.execute(
                    sa.text(
                        """
                        INSERT INTO role_permission (role_id, permission_id, criado_em, atualizado_em, tenant_id)
                        VALUES (:role_id, :permission_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :tenant_id)
                        """
                    ),
                    {
                        "role_id": role_id,
                        "permission_id": permission_ids[permission_code],
                        "tenant_id": tenant_id,
                    }
                )

        connection.execute(
            sa.text(
                """
                UPDATE funcionarios
                SET role_id = CASE
                    WHEN usuario = 'admin' THEN :admin_role_id
                    ELSE :operador_role_id
                END
                WHERE tenant_id = :tenant_id
                """
            ),
            {
                "admin_role_id": role_ids["administrador"],
                "operador_role_id": role_ids["operador"],
                "tenant_id": tenant_id,
            }
        )

    with op.batch_alter_table("funcionarios", schema=None) as batch_op:
        batch_op.alter_column("role_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f("ix_funcionarios_role_id"), ["role_id"], unique=False)


def downgrade():
    with op.batch_alter_table("funcionarios", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_funcionarios_role_id"))
        batch_op.drop_constraint("fk_funcionarios_role_id_role", type_="foreignkey")
        batch_op.drop_column("role_id")

    with op.batch_alter_table("role_permission", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_role_permission_tenant_id"))
    op.drop_table("role_permission")

    with op.batch_alter_table("role", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_role_tenant_id"))
    op.drop_table("role")

    with op.batch_alter_table("permissions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_permissions_tenant_id"))
    op.drop_table("permissions")
