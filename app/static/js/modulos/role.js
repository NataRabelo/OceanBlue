window.rolePage = null;
const roleCanEdit = () => window.userHasPermission?.("editar_role");
const roleCanDelete = () => window.userHasPermission?.("excluir_role");

document.addEventListener("DOMContentLoaded", async () => {
    window.rolePage = new CrudPage({
        apiBaseUrl: "/api/roles/",
        tableBodyId: "role-table-body",
        formCreateId: "form-cadastro",
        formEditId: "form-edicao",
        formDeleteId: "form-delete",
        modalCreateId: "modal-cadastro",
        modalEditId: "modal-edicao",
        modalDeleteId: "modal-delete",
        searchInputId: "input-busca",
        paginationContainerId: "role-pagination",
        pageSize: 10,
        fields: ["nome", "codigo", "descricao", "permissions_text"],
        messages: {
            loadError: "Erro ao carregar roles.",
            createSuccess: "Role cadastrada com sucesso.",
            createError: "Erro ao cadastrar role.",
            updateSuccess: "Role atualizada com sucesso.",
            updateError: "Erro ao atualizar role.",
            deleteSuccess: "Role excluida com sucesso.",
            deleteError: "Erro ao excluir role."
        },
        mapItemToEditForm: (item) => ({
            nome: item.nome || "",
            codigo: item.codigo || "",
            descricao: item.descricao || "",
            ativo: Boolean(item.ativo)
        }),
        beforeOpenCreateModal: async () => {
            await carregarPermissions("cadastro-permissions");
            preencherCheckboxAtivo("cadastro-ativo", true);
        },
        beforeOpenEditModal: async (item) => {
            await carregarPermissions("edicao-permissions", item.permission_ids || []);
            preencherCheckboxAtivo("edicao-ativo", item.ativo);
        },
        beforeSubmitCreate: () => normalizarPayload(false),
        beforeSubmitEdit: () => normalizarPayload(true),
        renderRow: (item) => `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center gap-3">
                        <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                            <i data-lucide="shield-check" class="w-4 h-4"></i>
                        </div>
                        <div>
                            <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                            <p class="text-xs text-slate-500">${escapeHtml(item.codigo || "-")}</p>
                        </div>
                    </div>
                </td>

                <td class="px-5 py-4 align-middle">
                    <p class="text-slate-300 leading-relaxed">${escapeHtml(item.descricao || "Sem descricao cadastrada.")}</p>
                </td>

                <td class="px-5 py-4 align-middle">
                    ${renderGroupedPermissions(item.permissions_grouped || [])}
                </td>

                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center justify-center gap-2">
                        ${renderRoleActions(item)}
                    </div>
                </td>
            </tr>
        `
    });

    window.rolePage.init();
    const createButton = document.getElementById("role-create-button");
    if (createButton) createButton.disabled = false;

    if (window.lucide) {
        lucide.createIcons();
    }
});

async function carregarPermissions(containerId, selectedIds = []) {
    const container = document.getElementById(containerId);
    if (!container) return;

    try {
        const response = await fetch("/api/roles/permissions-disponiveis", {
            credentials: "same-origin",
            headers: getAuthHeaders()
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Erro ao carregar permissions.");
        }

        const selected = new Set((selectedIds || []).map((id) => String(id)));
        const groups = Array.isArray(result.data) ? result.data : [];

        container.innerHTML = renderPermissionGroups(groups, selected);
        bindPermissionHierarchy(container);
    } catch (error) {
        container.innerHTML = `<p class="text-sm text-red-400">${escapeHtml(error.message)}</p>`;
    }
}

function renderPermissionGroups(groups, selected) {
    if (!Array.isArray(groups) || !groups.length) {
        return '<p class="text-sm text-slate-500">Nenhuma permission disponivel para este tenant.</p>';
    }

    return groups.map((group) => `
        <section class="rounded-2xl border border-slate-800 bg-slate-950/70 overflow-hidden">
            <div class="border-b border-slate-800 px-4 py-4">
                <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div class="min-w-0">
                        <h4 class="text-sm font-semibold uppercase tracking-[0.16em] text-sky-300">${escapeHtml(group.titulo || group.grupo || "Grupo")}</h4>
                        <p class="mt-1 text-sm text-slate-400">${escapeHtml(group.descricao || "Permissoes deste modulo.")}</p>
                    </div>
                    <span class="inline-flex items-center rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-300">
                        ${group.permissions?.length || 0} permiss${(group.permissions?.length || 0) === 1 ? "ao" : "oes"}
                    </span>
                </div>
                <p class="mt-3 text-xs text-slate-400">Ao desligar o item "Geral", todas as permissoes dependentes do modulo sao removidas automaticamente.</p>
            </div>
            <div class="grid grid-cols-1 gap-3 p-4 lg:grid-cols-2">
                ${(group.permissions || []).map((permission) => renderPermissionCard(permission, selected)).join("")}
            </div>
        </section>
    `).join("");
}

function renderPermissionCard(permission, selected) {
    const checked = selected.has(String(permission.id));
    const dependsOnCodes = Array.isArray(permission.depends_on_codes) ? permission.depends_on_codes : [];
    const dependencyLabel = dependsOnCodes.length
        ? `Depende de: ${dependsOnCodes.join(", ")}`
        : "Permissao base do modulo.";
    const helperText = permission.ajuda || permission.descricao || dependencyLabel;
    const badgeLabel = permission.kind === "general" ? "Geral" : "Especifica";

    return `
        <label class="role-permission-card flex items-start gap-3 rounded-2xl border border-slate-800 bg-slate-950 px-4 py-4 transition hover:border-sky-500/40" data-permission-card>
            <input
                type="checkbox"
                name="permission_ids"
                value="${permission.id}"
                data-permission-code="${escapeHtml(permission.codigo)}"
                data-depends-on="${escapeHtml(dependsOnCodes.join(","))}"
                class="mt-1 rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-sky-500"
                ${checked ? "checked" : ""}
            >
            <span class="min-w-0 flex-1">
                <span class="flex flex-wrap items-center gap-2">
                    <span class="block text-sm font-medium text-white">${escapeHtml(permission.titulo || permission.nome || permission.codigo)}</span>
                    <span class="inline-flex items-center rounded-full border border-slate-700 bg-slate-900 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-300">${badgeLabel}</span>
                </span>
                <span class="mt-1 block text-xs text-slate-400">${escapeHtml(permission.codigo || "")}</span>
                <span class="mt-2 block text-sm leading-relaxed text-slate-400">${escapeHtml(helperText)}</span>
                <span class="mt-2 block text-[11px] uppercase tracking-[0.16em] text-slate-400">${escapeHtml(dependencyLabel)}</span>
            </span>
        </label>
    `;
}

function renderGroupedPermissions(groups) {
    if (!Array.isArray(groups) || !groups.length) {
        return '<span class="text-sm text-slate-500">Sem permissions vinculadas.</span>';
    }

    return `
        <div class="space-y-3">
            ${groups.map((group) => `
                <div class="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
                    <p class="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-300">${escapeHtml(group.titulo || group.grupo || "Grupo")}</p>
                    <div class="mt-2 flex flex-wrap gap-2">
                        ${(group.permissions || []).map((permission) => `
                            <span class="inline-flex items-center rounded-full border ${permission.kind === "general" ? "border-sky-500/30 bg-sky-500/10 text-sky-300" : "border-slate-700 bg-slate-900 text-slate-200"} px-2.5 py-1 text-xs">
                                ${escapeHtml(permission.titulo || permission.codigo)}
                            </span>
                        `).join("")}
                    </div>
                </div>
            `).join("")}
        </div>
    `;
}

function bindPermissionHierarchy(container) {
    const checkboxes = Array.from(container.querySelectorAll('input[name="permission_ids"]'));
    if (!checkboxes.length) return;

    const checkboxByCode = new Map();
    const dependentsByCode = new Map();

    checkboxes.forEach((checkbox) => {
        const code = checkbox.dataset.permissionCode;
        if (!code) return;

        checkboxByCode.set(code, checkbox);

        const dependencyCodes = parseDependencyCodes(checkbox.dataset.dependsOn);
        dependencyCodes.forEach((dependencyCode) => {
            if (!dependentsByCode.has(dependencyCode)) {
                dependentsByCode.set(dependencyCode, new Set());
            }
            dependentsByCode.get(dependencyCode).add(code);
        });
    });

    const syncCardState = () => {
        checkboxes.forEach((checkbox) => {
            const card = checkbox.closest("[data-permission-card]");
            if (!card) return;

            card.classList.toggle("border-sky-500/50", checkbox.checked);
            card.classList.toggle("bg-sky-500/10", checkbox.checked);
            card.classList.toggle("shadow-[0_0_0_1px_rgba(56,189,248,0.08)]", checkbox.checked);
            card.classList.toggle("border-slate-800", !checkbox.checked);
            card.classList.toggle("bg-slate-950", !checkbox.checked);
        });
    };

    const ensureDependenciesChecked = (permissionCode, trail = new Set()) => {
        if (!permissionCode || trail.has(permissionCode)) return;

        const checkbox = checkboxByCode.get(permissionCode);
        if (!checkbox) return;

        trail.add(permissionCode);

        parseDependencyCodes(checkbox.dataset.dependsOn).forEach((dependencyCode) => {
            const dependencyCheckbox = checkboxByCode.get(dependencyCode);
            if (!dependencyCheckbox) return;

            if (!dependencyCheckbox.checked) {
                dependencyCheckbox.checked = true;
            }

            ensureDependenciesChecked(dependencyCode, trail);
        });
    };

    const uncheckDependents = (permissionCode, trail = new Set()) => {
        if (!permissionCode || trail.has(permissionCode)) return;

        trail.add(permissionCode);

        const dependentCodes = dependentsByCode.get(permissionCode) || new Set();
        dependentCodes.forEach((dependentCode) => {
            const dependentCheckbox = checkboxByCode.get(dependentCode);
            if (!dependentCheckbox) return;

            if (dependentCheckbox.checked) {
                dependentCheckbox.checked = false;
            }

            uncheckDependents(dependentCode, trail);
        });
    };

    checkboxes.forEach((checkbox) => {
        checkbox.addEventListener("change", () => {
            const code = checkbox.dataset.permissionCode;
            if (!code) return;

            if (checkbox.checked) {
                ensureDependenciesChecked(code);
            } else {
                uncheckDependents(code);
            }

            syncCardState();
        });
    });

    syncCardState();
}

function parseDependencyCodes(value) {
    return String(value || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

function normalizarPayload(isEdit) {
    const prefix = isEdit ? "edicao" : "cadastro";

    return {
        nome: (document.getElementById(`${prefix}-nome`)?.value || "").trim(),
        codigo: (document.getElementById(`${prefix}-codigo`)?.value || "").trim(),
        descricao: (document.getElementById(`${prefix}-descricao`)?.value || "").trim(),
        ativo: obterCheckboxAtivo(`${prefix}-ativo`),
        permission_ids: coletarPermissionIds(`${prefix}-permissions`)
    };
}

function coletarPermissionIds(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return [];

    return Array.from(container.querySelectorAll('input[name="permission_ids"]:checked'))
        .map((input) => input.value);
}

function obterCheckboxAtivo(id) {
    const checkbox = document.getElementById(id);
    return checkbox ? checkbox.checked : true;
}

function preencherCheckboxAtivo(id, value) {
    const checkbox = document.getElementById(id);
    if (checkbox) {
        checkbox.checked = Boolean(value);
    }
}

function getAuthHeaders() {
    const token = localStorage.getItem("token");
    return {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
}

function escapeHtml(value) {
    if (value === null || value === undefined) return "";

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function renderRoleActions(item) {
    const actions = [];

    if (roleCanEdit()) {
        actions.push(`
            <button
                type="button"
                onclick="rolePage.openEditModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition"
                title="Editar role"
            >
                <i data-lucide="square-pen" class="w-4 h-4"></i>
            </button>
        `);
    }

    if (roleCanDelete()) {
        actions.push(`
            <button
                type="button"
                onclick="rolePage.openDeleteModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition"
                title="Excluir role"
            >
                <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
        `);
    }

    return actions.length
        ? actions.join("")
        : '<span class="text-xs font-medium text-slate-500">Somente leitura</span>';
}
