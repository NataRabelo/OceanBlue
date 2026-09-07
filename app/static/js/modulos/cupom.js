window.cupomPage = null;
const cupomCanEdit = () => window.userHasPermission?.("editar_cupom");
const cupomCanDelete = () => window.userHasPermission?.("excluir_cupom");

document.addEventListener("DOMContentLoaded", () => {
    window.cupomPage = new CrudPage({
        apiBaseUrl: "/api/cupons/",
        tableBodyId: "cupom-table-body",
        formCreateId: "form-cadastro",
        formEditId: "form-edicao",
        formDeleteId: "form-delete",
        modalCreateId: "modal-cadastro",
        modalEditId: "modal-edicao",
        modalDeleteId: "modal-delete",
        searchInputId: "input-busca",
        paginationContainerId: "cupom-pagination",
        pageSize: 10,
        fields: ["nome", "codigo", "tipo_desconto", "criado_por_nome", "status"],
        messages: {
            loadError: "Erro ao carregar cupons.",
            createSuccess: "Cupom cadastrado com sucesso.",
            createError: "Erro ao cadastrar cupom.",
            updateSuccess: "Cupom atualizado com sucesso.",
            updateError: "Erro ao atualizar cupom.",
            deleteSuccess: "Cupom excluido com sucesso.",
            deleteError: "Erro ao excluir cupom."
        },
        mapItemToEditForm: (item) => ({
            data_inicio: item.data_inicio || "",
            empresa_id: item.empresa_id || "",
            cliente_id: item.cliente_id || "",
            limite_usos: item.limite_usos || "",
            limite_por_cliente: item.limite_por_cliente || "",
            valor_minimo: item.valor_minimo || "0",
            desconto_maximo: item.desconto_maximo || "",
            nome: item.nome || "",
            codigo: item.codigo || "",
            data_validade: item.data_validade || "",
            tipo_desconto: item.tipo_desconto || "PERCENTUAL",
            valor_desconto: formatCupomCurrencyInput(item.valor_desconto),
            ativo: Boolean(item.ativo),
        }),
        beforeOpenCreateModal: async () => {
            await carregarSegmentosCupom();
            resetCupomForm("cadastro");
        },
        beforeOpenEditModal: async (item) => {
            await carregarSegmentosCupom();
            for (const field of ["empresa_id", "cliente_id"]) {
                document.getElementById(`edicao-${field}`).value = item[field] || "";
            }
            document.getElementById("edicao-empresa_id").disabled = true;
            preencherCheckboxCupom("edicao-ativo", item.ativo);
        },
        beforeSubmitCreate: (payload) => normalizeCupomPayload(payload, false),
        beforeSubmitEdit: (payload) => normalizeCupomPayload(payload, true),
        renderRow: (item) => {
            const badge = item.status === "EXPIRADO"
                ? `<span class="inline-flex items-center rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 text-[11px] font-medium text-rose-300">Expirado</span>`
                : item.ativo
                    ? `<span class="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-medium text-emerald-300">${item.status === "AGENDADO" ? "Agendado" : "Ativo"}</span>`
                    : `<span class="inline-flex items-center rounded-full bg-slate-700/40 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-300">Inativo</span>`;

            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="px-5 py-4 align-middle">
                        <div class="flex items-start gap-3">
                            <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                                <i data-lucide="ticket-percent" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                                <p class="text-sm text-slate-500">${escapeHtml(item.tipo_desconto || "-")}</p>
                            </div>
                        </div>
                    </td>
                    <td class="px-5 py-4 align-middle text-slate-300 font-mono">${escapeHtml(item.codigo || "-")}</td>
                    <td class="px-5 py-4 align-middle text-slate-300">${formatCupomDate(item.data_validade)}</td>
                    <td class="px-5 py-4 align-middle text-white font-semibold">${formatCupomDiscount(item)}</td>
                    <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(item.criado_por_nome || "Sistema")}</td>
                    <td class="px-5 py-4 align-middle text-center">${badge}</td>
                    <td class="px-5 py-4 align-middle">
                        <div class="flex items-center justify-center gap-2">
                            ${renderCupomActions(item)}
                        </div>
                    </td>
                </tr>
            `;
        }
    });

    bindCupomMasks();
    window.cupomPage.init();
});

function bindCupomMasks() {
    setupCupomMoneyMask("cadastro-valor_desconto");
    setupCupomMoneyMask("edicao-valor_desconto");
    setupCupomCodeMask("cadastro-codigo");
    setupCupomCodeMask("edicao-codigo");
}

function normalizeCupomPayload(payload, isEdit) {
    const data = { ...payload };
    data.nome = (data.nome || "").trim();
    data.codigo = normalizeCupomCode(data.codigo);
    data.tipo_desconto = (data.tipo_desconto || "PERCENTUAL").trim().toUpperCase();
    data.valor_desconto = normalizeCupomMoney(data.valor_desconto);
    data.ativo = getCheckboxCupomValue(isEdit ? "edicao-ativo" : "cadastro-ativo");
    if (isEdit) delete data.empresa_id;
    return data;
}

async function carregarSegmentosCupom() {
    const response = await fetch("/api/pdv/auxiliares");
    const result = await response.json();
    if (!response.ok || !result.success) throw new Error(result.message || "Erro ao carregar segmentos.");
    for (const prefix of ["cadastro", "edicao"]) {
        for (const [field, collection] of [["empresa_id", "empresas"], ["cliente_id", "clientes"]]) {
            const select = document.getElementById(`${prefix}-${field}`);
            const selected = select.value;
            select.replaceChildren(new Option("Todos", ""));
            for (const record of result.data[collection] || []) select.add(new Option(record.nome, record.id));
            select.value = selected;
        }
    }
}

function resetCupomForm(prefix) {
    const dataField = document.getElementById(`${prefix}-data_validade`);
    const valorField = document.getElementById(`${prefix}-valor_desconto`);
    const ativoField = document.getElementById(`${prefix}-ativo`);
    const tipoField = document.getElementById(`${prefix}-tipo_desconto`);

    if (dataField) dataField.value = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
    if (valorField) valorField.value = "0,00";
    if (ativoField) ativoField.checked = true;
    if (tipoField) tipoField.value = "PERCENTUAL";
}

function preencherCheckboxCupom(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.checked = Boolean(value);
    }
}

function getCheckboxCupomValue(id) {
    const element = document.getElementById(id);
    return !!element?.checked;
}

function setupCupomMoneyMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    window.DecimalInput?.bind(input, {
        decimals: 2,
        allowEmpty: false
    });
}

function setupCupomCodeMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.maskBound === "true") return;

    input.dataset.maskBound = "true";
    input.addEventListener("input", () => {
        input.value = normalizeCupomCode(input.value);
    });
}

function normalizeCupomCode(value) {
    return String(value || "")
        .toUpperCase()
        .replace(/\s+/g, "")
        .replace(/[^A-Z0-9_-]/g, "")
        .slice(0, 60);
}

function parseCupomMoney(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function formatCupomCurrencyInput(value) {
    return window.DecimalInput?.format(value, 2, {
        allowEmpty: false,
        useGrouping: true
    }) ?? "0,00";
}

function normalizeCupomMoney(value) {
    return window.DecimalInput?.normalize(value, 2) ?? "0.00";
}

function formatCupomDiscount(item) {
    const valor = parseCupomMoney(item.valor_desconto);
    if ((item.tipo_desconto || "").toUpperCase() === "PERCENTUAL") {
        return `${formatCupomCurrencyInput(valor)}%`;
    }
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
    }).format(valor);
}

function formatCupomDate(value) {
    if (!value) return "-";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(date);
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

function renderCupomActions(item) {
    const actions = [];

    if (cupomCanEdit()) {
        actions.push(`
            <button type="button"
                onclick="cupomPage.openEditModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition"
                title="Editar cupom">
                <i data-lucide="square-pen" class="w-4 h-4"></i>
            </button>
        `);
    }

    if (cupomCanDelete()) {
        actions.push(`
            <button type="button"
                onclick="cupomPage.openDeleteModal(${item.id})"
                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition"
                title="Excluir cupom">
                <i data-lucide="trash-2" class="w-4 h-4"></i>
            </button>
        `);
    }

    return actions.length
        ? actions.join("")
        : '<span class="text-xs font-medium text-slate-500">Somente leitura</span>';
}
