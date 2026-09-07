window.funcionarioPage = null;
const funcionarioCanEdit = () => window.userHasPermission?.("editar_funcionario");
const funcionarioCanDelete = () => window.userHasPermission?.("excluir_funcionario");

document.addEventListener("DOMContentLoaded", async () => {
    window.funcionarioPage = new CrudPage({
        apiBaseUrl: "/api/funcionarios/",
        tableBodyId: "funcionario-table-body",
        formCreateId: "form-cadastro",
        formEditId: "form-edicao",
        formDeleteId: "form-delete",
        modalCreateId: "modal-cadastro",
        modalEditId: "modal-edicao",
        modalDeleteId: "modal-delete",
        searchInputId: "input-busca",
        paginationContainerId: "funcionario-pagination",
        pageSize: 10,
        fields: ["nome", "usuario", "cpf", "empresa_nome", "empresa_resumo", "role_nome", "salario", "meta"],
        messages: {
            loadError: "Erro ao carregar funcionarios.",
            createSuccess: "Funcionario cadastrado com sucesso.",
            createError: "Erro ao cadastrar funcionario.",
            updateSuccess: "Funcionario atualizado com sucesso.",
            updateError: "Erro ao atualizar funcionario.",
            deleteSuccess: "Funcionario excluido com sucesso.",
            deleteError: "Erro ao excluir funcionario."
        },
        mapItemToEditForm: (item) => ({
            id: item.id || "",
            nome: item.nome || "",
            cpf: item.cpf || "",
            usuario: item.usuario || "",
            senha: "",
            salario: formatMoneyForDisplay(item.salario),
            meta: formatMoneyForDisplay(item.meta),
            empresa_id: item.empresa_id || "",
            role_id: item.role_id || "",
            ativo: Boolean(item.ativo)
        }),
        beforeOpenCreateModal: async () => {
            await Promise.all([carregarEmpresas(), carregarRoles()]);
            limparFormularioEdicao();
        },
        beforeOpenEditModal: async (item) => {
            await Promise.all([carregarEmpresas(item.empresa_id), carregarRoles(item.role_id)]);
            preencherCheckboxAtivo("edicao-ativo", item.ativo);
        },
        beforeSubmitCreate: (payload) => normalizarPayload(payload, false),
        beforeSubmitEdit: (payload) => normalizarPayload(payload, true),
        renderRow: (item) => `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center gap-3">
                        <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                            <i data-lucide="user-round" class="w-4 h-4"></i>
                        </div>
                        <div>
                            <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                            <p class="text-xs text-slate-500">${escapeHtml(item.role_nome || "Sem role")}</p>
                        </div>
                    </div>
                </td>

                <td class="px-5 py-4 align-middle">
                    <p class="text-slate-300 leading-relaxed">${escapeHtml(item.usuario || "-")}</p>
                </td>

                <td class="px-5 py-4 align-middle">
                    <p class="text-slate-300 leading-relaxed">${escapeHtml(window.InputMask?.formatCpf(item.cpf) || item.cpf || "-")}</p>
                </td>

                <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                    ${formatMoneyForDisplay(item.salario)}
                </td>

                <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                    ${formatMoneyForDisplay(item.meta)}
                </td>

                <td class="px-5 py-4 align-middle">
                    <div class="space-y-1">
                        <p class="text-slate-300 leading-relaxed">
                            ${escapeHtml(item.empresa_resumo || item.empresa_nome || "-")}
                        </p>
                        ${item.quantidade_empresas > 1 ? `
                            <p class="text-xs text-slate-500">${escapeHtml(item.empresa_nome || "-")}</p>
                        ` : ""}
                    </div>
                </td>

                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center justify-center gap-2">
                        ${renderFuncionarioActions(item)}
                    </div>
                </td>
            </tr>
        `
    });

    await Promise.all([carregarEmpresas(), carregarRoles()]);
    window.funcionarioPage.init();

    aplicarMascaraCpf("cadastro-cpf");
    aplicarMascaraCpf("edicao-cpf");
    aplicarMascaraMoeda("cadastro-salario");
    aplicarMascaraMoeda("cadastro-meta");
    aplicarMascaraMoeda("edicao-salario");
    aplicarMascaraMoeda("edicao-meta");

    if (window.lucide) {
        lucide.createIcons();
    }
});

async function carregarEmpresas(selectedId = "") {
    const selects = [
        document.getElementById("cadastro-empresa_id"),
        document.getElementById("edicao-empresa_id")
    ].filter(Boolean);

    try {
        const response = await fetch("/api/funcionarios/empresas-disponiveis", {
            credentials: "same-origin",
            headers: getAuthHeaders()
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Erro ao carregar empresas.");
        }

        for (const select of selects) {
            const currentValue = select.id === "edicao-empresa_id" ? String(selectedId || "") : String(select.value || "");
            select.innerHTML = `<option value="">Selecione uma empresa</option>`;

            result.data.forEach((empresa) => {
                const option = document.createElement("option");
                option.value = empresa.id;
                option.textContent = empresa.nome_fantasia || empresa.razao_social || `Empresa #${empresa.id}`;

                if (String(empresa.id) === currentValue) {
                    option.selected = true;
                }

                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error(error);
    }
}

async function carregarRoles(selectedId = "") {
    const selects = [
        document.getElementById("cadastro-role_id"),
        document.getElementById("edicao-role_id")
    ].filter(Boolean);

    try {
        const response = await fetch("/api/funcionarios/roles-disponiveis", {
            credentials: "same-origin",
            headers: getAuthHeaders()
        });
        const result = await response.json();

        if (!response.ok || !result.success) {
            throw new Error(result.message || "Erro ao carregar roles.");
        }

        for (const select of selects) {
            const currentValue = select.id === "edicao-role_id" ? String(selectedId || "") : String(select.value || "");
            select.innerHTML = `<option value="">Selecione uma role</option>`;

            result.data.forEach((role) => {
                const option = document.createElement("option");
                option.value = role.id;
                option.textContent = role.nome;
                option.title = role.descricao || "";

                if (String(role.id) === currentValue) {
                    option.selected = true;
                }

                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error(error);
    }
}

function normalizarPayload(payload, isEdit) {
    const data = { ...payload };

    data.nome = (data.nome || "").trim();
    data.cpf = (data.cpf || "").trim();
    data.usuario = (data.usuario || "").trim();
    data.senha = (data.senha || "").trim();
    data.salario = normalizeMoneyForApi(data.salario);
    data.meta = normalizeMoneyForApi(data.meta);
    data.empresa_id = data.empresa_id || "";
    data.role_id = data.role_id || "";
    data.ativo = obterCheckboxAtivo(isEdit ? "edicao-ativo" : "cadastro-ativo");

    if (isEdit && !data.senha) {
        delete data.senha;
    }

    return data;
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

function limparFormularioEdicao() {
    preencherCheckboxAtivo("cadastro-ativo", true);
    preencherCheckboxAtivo("edicao-ativo", true);

    const salario = document.getElementById("cadastro-salario");
    const meta = document.getElementById("cadastro-meta");
    if (salario) salario.value = "0,00";
    if (meta) meta.value = "0,00";
}

function aplicarMascaraCpf(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    window.InputMask?.bind(input, "cpf");
}

function aplicarMascaraMoeda(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    window.DecimalInput?.bind(input, {
        decimals: 2,
        allowEmpty: false
    });
}

function parseMoneyValue(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function formatMoneyForDisplay(value) {
    return window.DecimalInput?.format(value, 2, { allowEmpty: false, useGrouping: true }) ?? "0,00";
}

function normalizeMoneyForApi(value) {
    return window.DecimalInput?.normalize(value, 2) ?? "0.00";
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

function renderFuncionarioActions(item) {
    const actions = [];

    if (funcionarioCanEdit()) {
        actions.push(`
            <button
                type="button"
                onclick="funcionarioPage.openEditModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition"
                title="Editar funcionario"
            >
                <i data-lucide="square-pen" class="w-4 h-4"></i>
            </button>
        `);
    }

    if (funcionarioCanDelete()) {
        actions.push(`
            <button
                type="button"
                onclick="funcionarioPage.openDeleteModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition"
                title="Excluir funcionario"
            >
                <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
        `);
    }

    if (funcionarioCanEdit()) {
        actions.push(`<button type="button" onclick="emitirRedefinicaoFuncionario(${Number(item.funcionario_id)})" class="px-3 py-2 text-sky-300" title="Emitir codigo de redefinicao de senha">Redefinir senha</button>`);
    }

    return actions.length
        ? actions.join("")
        : '<span class="text-xs font-medium text-slate-500">Somente leitura</span>';
}

function getAuthHeaders() {
    const token = localStorage.getItem("token");
    return {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {})
    };
}

async function emitirRedefinicaoFuncionario(funcionarioId) {
    try {
        const response = await fetch(`/api/auth/funcionarios/${funcionarioId}/redefinicao`, {
            method: "POST",
            credentials: "same-origin",
            headers: getAuthHeaders()
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            throw new Error(result.message || "Nao foi possivel emitir o codigo.");
        }
        window.prompt("Codigo de uso unico, valido por 15 minutos. Entregue por canal seguro para uso em Redefinir senha:", result.token);
    } catch (error) {
        window.alert(error.message);
    }
}
