window.produtoPage = null;
const produtoCanEdit = () => window.userHasPermission?.("editar_produto");
const produtoCanDelete = () => window.userHasPermission?.("excluir_produto");

document.addEventListener("DOMContentLoaded", () => {
    window.produtoPage = new CrudPage({
        apiBaseUrl: "/api/produtos/",
        tableBodyId: "produto-table-body",
        formCreateId: "form-cadastro",
        formEditId: "form-edicao",
        formDeleteId: "form-delete",
        modalCreateId: "modal-cadastro",
        modalEditId: "modal-edicao",
        modalDeleteId: "modal-delete",
        searchInputId: "input-busca",
        paginationContainerId: "produto-pagination",
        pageSize: 10,
        fields: ["nome", "descricao", "categoria_nome", "empresa_nome", "codigo_barras", "data_validade"],

        messages: {
            loadError: "Erro ao carregar produtos.",
            createSuccess: "Produto cadastrado com sucesso.",
            createError: "Erro ao cadastrar produto.",
            updateSuccess: "Produto atualizado com sucesso.",
            updateError: "Erro ao atualizar produto.",
            deleteSuccess: "Produto excluído com sucesso.",
            deleteError: "Erro ao excluir produto."
        },

        mapItemToEditForm: (item) => ({
            nome: item.nome || "",
            descricao: item.descricao || "",
            categoria_id: item.categoria_id || "",
            empresa_id: item.empresa_id || "",
            codigo_barras: item.codigo_barras || "",
            possui_ncm: !!item.possui_ncm,
            ncm: item.ncm || "",
            estoque_minimo: formatIntegerForDisplay(item.estoque_minimo),
            data_validade: item.data_validade || "",
            valor_compra: formatDecimalForDisplay(item.valor_compra, 2),
            valor_varejo: formatDecimalForDisplay(item.valor_varejo ?? item.valor_venda, 2),
            valor_atacado: formatDecimalForDisplay(item.valor_atacado ?? item.valor_venda, 2),
            quantidade_minima_atacado: formatIntegerForDisplay(item.quantidade_minima_atacado ?? 1),
            ativo: !!item.ativo
        }),

        beforeSubmitCreate: (payload) => normalizeProdutoPayload(payload, false),
        beforeSubmitEdit: (payload) => normalizeProdutoPayload(payload, true),

        renderRow: (item) => {
            const categoria = item.categoria_nome || "Sem categoria";
            const empresa = item.empresa_nome || "-";
            const codigoBarras = item.codigo_barras || "-";
            const estoqueAtual = formatInteger(item.estoque_atual);
            const validade = formatDateForDisplay(item.data_validade);
            const valorCompra = formatCurrency(item.valor_compra);
            const valorVarejoNumerico = Number(String(item.valor_varejo ?? item.valor_venda ?? 0).replace(",", "."));
            const valorAtacadoNumerico = Number(String(item.valor_atacado ?? item.valor_venda ?? 0).replace(",", "."));
            const atacadoConfigurado = valorAtacadoNumerico > 0 && valorAtacadoNumerico < valorVarejoNumerico;
            const valorVarejo = formatCurrency(item.valor_varejo ?? item.valor_venda);
            const valorAtacado = atacadoConfigurado
                ? formatCurrency(item.valor_atacado ?? item.valor_venda)
                : "Nao configurado";
            const quantidadeMinimaAtacado = atacadoConfigurado
                ? formatInteger(item.quantidade_minima_atacado ?? 1)
                : "-";
            const ativoBadge = item.ativo
                ? `<span class="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-medium text-emerald-400">Ativo</span>`
                : `<span class="inline-flex items-center rounded-full bg-slate-700/40 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-400">Inativo</span>`;
            const actions = [
                `
                    <button
                        type="button"
                        onclick="visualizarCodigoBarras(${item.id})"
                        class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-300 hover:bg-sky-500/20 transition"
                        title="Visualizar codigo de barras"
                    >
                        <i data-lucide="barcode" class="w-4 h-4"></i>
                    </button>
                `
            ];

            if (produtoCanEdit()) {
                actions.push(`
                    <button
                        type="button"
                        onclick="produtoPage.openEditModal(${item.id})"
                        class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition"
                        title="Editar produto"
                        >
                            <i data-lucide="square-pen" class="w-4 h-4"></i>
                        </button>
                `);
            }

            if (produtoCanDelete()) {
                actions.push(`
                    <button
                        type="button"
                        onclick="produtoPage.openDeleteModal(${item.id})"
                        class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition"
                        title="Excluir produto"
                    >
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                `);
            }

            if (window.userHasPermission?.("criar_produto")) {
                actions.push(`<button type="button" onclick="vincularProdutoEmpresa(${item.id})" class="text-sky-300 px-2 py-2" title="Vincular em outra empresa">Vincular</button>`);
            }

            return `
                <tr class="hover:bg-slate-800/40 transition">
                    <td class="px-5 py-4 align-middle">
                        <div class="flex items-start gap-3">
                            <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                                <i data-lucide="package" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                                <p class="text-sm text-slate-400">${escapeHtml(item.descricao || "Sem descrição cadastrada.")}</p>
                                <div class="mt-2">${ativoBadge}</div>
                            </div>
                        </div>
                    </td>

                    <td class="px-5 py-4 align-middle text-slate-300">
                        ${escapeHtml(categoria)}
                    </td>

                    <td class="px-5 py-4 align-middle text-slate-300">
                        ${escapeHtml(empresa)}
                    </td>

                    <td class="px-5 py-4 align-middle text-slate-300">
                        ${escapeHtml(codigoBarras)}
                    </td>

                    <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                        ${estoqueAtual}
                    </td>

                    <td class="px-5 py-4 align-middle text-slate-300">
                        ${escapeHtml(validade)}
                    </td>

                    <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                        ${valorCompra}
                    </td>

                    <td class="px-5 py-4 align-middle text-right text-white font-semibold">
                        ${valorVarejo}
                    </td>

                    <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                        ${valorAtacado}
                    </td>

                    <td class="px-5 py-4 align-middle text-right text-slate-300 font-medium">
                        ${quantidadeMinimaAtacado}
                    </td>

                    <td class="px-5 py-4 align-middle">
                        <div class="flex items-center justify-center gap-2">
                            ${actions.join("")}
                        </div>
                    </td>
                </tr>
            `;
        }
    });

    enhanceProdutoPage(window.produtoPage);
    window.produtoPage.init();

    if (window.lucide) {
        lucide.createIcons();
    }
});

function enhanceProdutoPage(page) {
    page.auxiliares = {
        categorias: [],
        empresas: []
    };

    const originalInit = page.init.bind(page);
    page.init = async function () {
        this.bindCreateForm();
        this.bindEditForm();
        this.bindDeleteForm();
        this.bindSearch();
        this.bindModalClose();
        this.bindNcmToggle();
        this.bindMasks();
        await this.loadAuxiliares();
        await this.load();
    };

    page.loadAuxiliares = async function () {
        try {
            const result = await this.request(`${this.config.apiBaseUrl}auxiliares`, {
                method: "GET",
                headers: this.getHeaders(false)
            });

            this.auxiliares = result.data || { categorias: [], empresas: [] };
            this.populateAuxiliares();
        } catch (error) {
            this.showMessage(error.message || "Erro ao carregar dados auxiliares.", "error");
        }
    };

    page.populateAuxiliares = function () {
        populateSelect("cadastro-categoria_id", this.auxiliares.categorias, true);
        populateSelect("edicao-categoria_id", this.auxiliares.categorias, true);
        populateSelect("cadastro-empresa_id", this.auxiliares.empresas, false);
        populateSelect("edicao-empresa_id", this.auxiliares.empresas, false);
    };

    page.bindNcmToggle = function () {
        setupNcmToggle("cadastro-possui_ncm", "cadastro-ncm");
        setupNcmToggle("edicao-possui_ncm", "edicao-ncm");
    };

    page.bindMasks = function () {
        setupIntegerMask("cadastro-estoque_minimo");
        setupIntegerMask("edicao-estoque_minimo");
        setupIntegerMask("cadastro-quantidade_minima_atacado");
        setupIntegerMask("edicao-quantidade_minima_atacado");
        setupDecimalMask("cadastro-valor_compra", 2);
        setupDecimalMask("edicao-valor_compra", 2);
        setupDecimalMask("cadastro-valor_varejo", 2);
        setupDecimalMask("edicao-valor_varejo", 2);
        setupDecimalMask("cadastro-valor_atacado", 2);
        setupDecimalMask("edicao-valor_atacado", 2);
        setupDigitsMask("cadastro-codigo_barras", 50);
        setupDigitsMask("edicao-codigo_barras", 50);
        setupNcmMask("cadastro-ncm");
        setupNcmMask("edicao-ncm");
    };

    const originalOpenCreateModal = page.openCreateModal.bind(page);
    page.openCreateModal = async function () {
        await originalOpenCreateModal();
        this.populateAuxiliares();

        const ativo = document.getElementById("cadastro-ativo");
        const possuiNcm = document.getElementById("cadastro-possui_ncm");
        const ncm = document.getElementById("cadastro-ncm");

        if (ativo) ativo.checked = true;
        if (possuiNcm) possuiNcm.checked = false;
        if (ncm) {
            ncm.value = "";
            ncm.disabled = true;
        }

        applyIntegerDisplay("cadastro-estoque_minimo");
        applyIntegerDisplay("cadastro-quantidade_minima_atacado");
        applyDecimalDisplay("cadastro-valor_compra", 2);
        applyDecimalDisplay("cadastro-valor_varejo", 2);
        applyDecimalDisplay("cadastro-valor_atacado", 2);
    };

    const originalFillForm = page.fillForm.bind(page);
    page.fillForm = function (formId, data) {
        const form = document.getElementById(formId);
        if (!form) return;

        Object.keys(data).forEach((key) => {
            const field = form.querySelector(`[name="${key}"]`);
            if (!field) return;

            if (field.type === "checkbox") {
                field.checked = !!data[key];
            } else {
                field.value = data[key] ?? "";
            }
        });

        const possuiNcmField = form.querySelector(`[name="possui_ncm"]`);
        const ncmField = form.querySelector(`[name="ncm"]`);

        if (possuiNcmField && ncmField) {
            ncmField.disabled = !possuiNcmField.checked;
            if (!possuiNcmField.checked) {
                ncmField.value = "";
            }
        }

        if (window.lucide) {
            lucide.createIcons();
        }
    };

    const originalClearForm = page.clearForm.bind(page);
    page.clearForm = function (formId) {
        originalClearForm(formId);

        const form = document.getElementById(formId);
        if (!form) return;

        form.querySelectorAll('input[type="checkbox"]').forEach((checkbox) => {
            checkbox.checked = false;
        });

        const ativo = form.querySelector('[name="ativo"]');
        if (ativo) ativo.checked = true;

        const ncm = form.querySelector('[name="ncm"]');
        if (ncm) {
            ncm.value = "";
            ncm.disabled = true;
        }

        const estoqueMinimo = form.querySelector('[name="estoque_minimo"]');
        const quantidadeMinimaAtacado = form.querySelector('[name="quantidade_minima_atacado"]');
        const valorCompra = form.querySelector('[name="valor_compra"]');
        const valorVarejo = form.querySelector('[name="valor_varejo"]');
        const valorAtacado = form.querySelector('[name="valor_atacado"]');

        if (estoqueMinimo) estoqueMinimo.value = "0";
        if (quantidadeMinimaAtacado) quantidadeMinimaAtacado.value = "1";
        if (valorCompra) valorCompra.value = "0,00";
        if (valorVarejo) valorVarejo.value = "0,00";
        if (valorAtacado) valorAtacado.value = "0,00";
    };
}

function populateSelect(selectId, items, allowEmptyOption) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const currentValue = select.value;

    select.innerHTML = "";

    if (allowEmptyOption) {
        select.innerHTML += `<option value="">Sem categoria</option>`;
    } else {
        select.innerHTML += `<option value="">Selecione</option>`;
    }

    (items || []).forEach((item) => {
        select.innerHTML += `<option value="${item.id}">${escapeHtml(item.nome)}</option>`;
    });

    if (currentValue) {
        select.value = currentValue;
    }
}

function setupNcmToggle(checkboxId, inputId) {
    const checkbox = document.getElementById(checkboxId);
    const input = document.getElementById(inputId);

    if (!checkbox || !input) return;

    const applyState = () => {
        input.disabled = !checkbox.checked;
        if (!checkbox.checked) {
            input.value = "";
        }
    };

    checkbox.addEventListener("change", applyState);
    applyState();
}

async function vincularProdutoEmpresa(itemId) {
    const item = produtoPage.items.find(record => record.id === itemId);
    if (!item) return;
    await produtoPage.openCreateModal();
    produtoPage.fillForm("form-cadastro", {
        ...produtoPage.config.mapItemToEditForm(item),
        produto_id: item.produto_id,
        empresa_id: "",
    });
    produtoPage.showMessage("Selecione a nova empresa e seus precos. O novo estoque inicia em zero; os dados gerais permanecem compartilhados.", "success");
}

function normalizeProdutoPayload(payload, isEdit) {
    const data = { ...payload };

    data.nome = (data.nome || "").trim();
    data.descricao = (data.descricao || "").trim();
    data.categoria_id = data.categoria_id || "";
    data.empresa_id = isEdit ? document.getElementById("edicao-empresa_id").value : (data.empresa_id || "");
    data.codigo_barras = normalizeDigits(data.codigo_barras, 50);
    data.possui_ncm = getCheckboxValue(isEdit ? "edicao-possui_ncm" : "cadastro-possui_ncm");
    data.ncm = normalizeNcm(data.ncm);
    data.estoque_minimo = normalizeIntegerForApi(data.estoque_minimo);
    data.quantidade_minima_atacado = normalizeIntegerForApi(data.quantidade_minima_atacado || "1");
    data.data_validade = data.data_validade || "";
    data.valor_compra = normalizeDecimalForApi(data.valor_compra, 2);
    data.valor_varejo = normalizeDecimalForApi(data.valor_varejo, 2);
    data.valor_atacado = normalizeDecimalForApi(data.valor_atacado, 2);
    data.ativo = getCheckboxValue(isEdit ? "edicao-ativo" : "cadastro-ativo");

    if (!data.possui_ncm) {
        data.ncm = "";
    }

    return data;
}

function normalizeDecimalForApi(value, decimals = 2) {
    const normalized = parseDecimalInput(value);
    const fixed = normalized.toFixed(decimals);
    return decimals > 0 ? fixed : String(Math.trunc(normalized));
}

function formatDecimalForDisplay(value, decimals = 2) {
    return window.DecimalInput?.format(value, decimals, {
        allowEmpty: false,
        useGrouping: true
    }) ?? formatNumber(0, decimals);
}

function formatIntegerForDisplay(value) {
    if (value === null || value === undefined || value === "") {
        return "0";
    }

    return formatInteger(value);
}

function formatDateForDisplay(value) {
    if (!value) {
        return "Sem validade";
    }

    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
        return "Sem validade";
    }

    return new Intl.DateTimeFormat("pt-BR").format(date);
}

function formatCurrency(value) {
    const parsed = Number(String(value ?? 0).replace(",", "."));
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatNumber(value, decimals = 3) {
    const parsed = Number(String(value ?? 0).replace(",", "."));
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatInteger(value) {
    const parsed = Number.parseInt(String(value ?? 0).replace(/\D/g, ""), 10);
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function setupDecimalMask(inputId, decimals = 2) {
    const input = document.getElementById(inputId);
    if (!input) return;

    window.DecimalInput?.bind(input, {
        decimals,
        allowEmpty: false
    });
}

function setupIntegerMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.maskBound === "true") return;

    input.dataset.maskBound = "true";
    input.setAttribute("inputmode", "numeric");

    const applyMask = () => {
        input.value = formatIntegerInput(input.value);
    };

    input.addEventListener("input", applyMask);
    input.addEventListener("blur", applyMask);
    applyMask();
}

function setupDigitsMask(inputId, maxLength = 50) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.maskBound === "true") return;

    input.dataset.maskBound = "true";
    input.setAttribute("inputmode", "numeric");

    input.addEventListener("input", () => {
        input.value = normalizeDigits(input.value, maxLength);
    });
}

function setupNcmMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.maskBound === "true") return;

    input.dataset.maskBound = "true";
    input.setAttribute("inputmode", "numeric");

    input.addEventListener("input", () => {
        input.value = formatNcm(input.value);
    });
}

function formatDecimalFromDigits(value, decimals = 2) {
    const digits = String(value ?? "").replace(/\D/g, "");

    if (!digits) {
        return formatNumber(0, decimals);
    }

    const numericValue = Number(digits) / (10 ** decimals);
    return formatNumber(numericValue, decimals);
}

function parseDecimalInput(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function parseIntegerInput(value) {
    const digits = String(value ?? "").replace(/\D/g, "");
    if (!digits) return 0;

    const parsed = Number.parseInt(digits, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function normalizeDigits(value, maxLength = 50) {
    return String(value ?? "").replace(/\D/g, "").slice(0, maxLength);
}

function normalizeIntegerForApi(value) {
    return String(parseIntegerInput(value));
}

function formatNcm(value) {
    const digits = normalizeDigits(value, 8);

    if (digits.length <= 4) return digits;
    if (digits.length <= 6) return digits.replace(/^(\d{4})(\d+)/, "$1.$2");
    return digits.replace(/^(\d{4})(\d{2})(\d{0,2}).*/, "$1.$2.$3");
}

function normalizeNcm(value) {
    return normalizeDigits(value, 8);
}

function getCheckboxValue(inputId) {
    const input = document.getElementById(inputId);
    return !!input?.checked;
}

function applyDecimalDisplay(inputId, decimals = 2) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.value = window.DecimalInput?.format(input.value, decimals, {
        allowEmpty: false,
        useGrouping: true
    }) ?? formatDecimalForDisplay(input.value, decimals);
}

function applyIntegerDisplay(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.value = formatIntegerInput(input.value);
}

function formatIntegerInput(value) {
    return formatInteger(parseIntegerInput(value));
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

function visualizarCodigoBarras(produtoEmpresaId) {
    const item = window.produtoPage?.items?.find((produto) => String(produto.id) === String(produtoEmpresaId));
    if (!item) {
        window.produtoPage?.showMessage("Produto nao encontrado para gerar a etiqueta.", "error");
        return;
    }

    const codigo = normalizeDigits(item.codigo_barras, 13);
    const popup = window.open("", "_blank", "noopener,width=720,height=640");
    if (!popup) {
        window.produtoPage?.showMessage("Nao foi possivel abrir a visualizacao do codigo de barras.", "error");
        return;
    }

    const barcodeMarkup = codigo.length === 13
        ? gerarMarkupEan13(codigo)
        : `<div style="padding:24px;border:1px solid #d5d8dc;border-radius:12px;background:#fafafa;text-align:center;">
            <p style="font-size:14px;color:#5f6368;margin:0 0 12px;">Codigo sem padrao EAN-13. Exibicao textual:</p>
            <strong style="font-size:28px;letter-spacing:0.2em;">${escapeHtml(codigo || "SEM CODIGO")}</strong>
        </div>`;

    popup.document.write(`
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Etiqueta - ${escapeHtml(item.nome || "Produto")}</title>
            <style>
                body { font-family: Arial, sans-serif; background: #f3f4f6; margin: 0; padding: 24px; color: #111827; }
                .sheet { max-width: 640px; margin: 0 auto; background: #fff; border-radius: 18px; padding: 28px; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.14); }
                .title { margin: 0 0 8px; font-size: 28px; }
                .meta { margin: 0 0 20px; color: #4b5563; }
                .actions { display: flex; gap: 12px; margin-top: 24px; }
                .actions button { border: none; border-radius: 10px; padding: 12px 18px; font-weight: 600; cursor: pointer; }
                .print { background: #0ea5e9; color: #082f49; }
                .close { background: #e5e7eb; color: #111827; }
                @media print {
                    body { background: #fff; padding: 0; }
                    .sheet { box-shadow: none; padding: 0; }
                    .actions { display: none; }
                }
            </style>
        </head>
        <body>
            <div class="sheet">
                <h1 class="title">${escapeHtml(item.nome || "Produto")}</h1>
                <p class="meta">Empresa: ${escapeHtml(item.empresa_nome || "-")} · Codigo: ${escapeHtml(item.codigo_barras || "-")}</p>
                ${barcodeMarkup}
                <div class="actions">
                    <button class="print" onclick="window.print()">Imprimir</button>
                    <button class="close" onclick="window.close()">Fechar</button>
                </div>
            </div>
        </body>
        </html>
    `);
    popup.document.close();
}

function gerarMarkupEan13(codigo) {
    const patternsA = {
        0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
        5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011"
    };
    const patternsB = {
        0: "0100111", 1: "0110011", 2: "0011011", 3: "0100001", 4: "0011101",
        5: "0111001", 6: "0000101", 7: "0010001", 8: "0001001", 9: "0010111"
    };
    const patternsC = {
        0: "1110010", 1: "1100110", 2: "1101100", 3: "1000010", 4: "1011100",
        5: "1001110", 6: "1010000", 7: "1000100", 8: "1001000", 9: "1110100"
    };
    const parity = {
        0: "AAAAAA", 1: "AABABB", 2: "AABBAB", 3: "AABBBA", 4: "ABAABB",
        5: "ABBAAB", 6: "ABBBAA", 7: "ABABAB", 8: "ABABBA", 9: "ABBABA"
    };

    const firstDigit = Number(codigo[0]);
    const leftDigits = codigo.slice(1, 7).split("").map(Number);
    const rightDigits = codigo.slice(7).split("").map(Number);
    const parityPattern = parity[firstDigit];

    let encoded = "101";
    leftDigits.forEach((digit, index) => {
        encoded += parityPattern[index] === "A" ? patternsA[digit] : patternsB[digit];
    });
    encoded += "01010";
    rightDigits.forEach((digit) => {
        encoded += patternsC[digit];
    });
    encoded += "101";

    const bars = encoded.split("").map((bit, index) => {
        const isGuard = index < 3 || (index >= 45 && index < 50) || index >= 92;
        const height = isGuard ? 110 : 96;
        return `<rect x="${index * 2}" y="0" width="2" height="${height}" fill="${bit === "1" ? "#111827" : "#ffffff"}"></rect>`;
    }).join("");

    return `
        <div style="padding:24px;border:1px solid #d5d8dc;border-radius:12px;background:#fff;">
            <svg viewBox="0 0 190 132" width="100%" height="180" role="img" aria-label="Codigo de barras EAN-13">
                <rect x="0" y="0" width="190" height="132" fill="#ffffff"></rect>
                <g transform="translate(10,10)">
                    ${bars}
                </g>
                <text x="95" y="128" text-anchor="middle" font-size="16" font-family="Arial, sans-serif" letter-spacing="3">${escapeHtml(codigo)}</text>
            </svg>
        </div>
    `;
}

function visualizarCodigoBarras(produtoEmpresaId) {
    const item = window.produtoPage?.items?.find((produto) => String(produto.id) === String(produtoEmpresaId));
    if (!item) {
        window.produtoPage?.showMessage("Produto nao encontrado para gerar a etiqueta.", "error");
        return;
    }

    const codigoOriginal = normalizeDigits(item.codigo_barras, 50);
    if (!codigoOriginal) {
        window.produtoPage?.showMessage("Este produto ainda nao possui codigo de barras cadastrado.", "error");
        return;
    }

    const codigo = normalizarCodigoEtiqueta(codigoOriginal);
    const popup = window.open("about:blank", "_blank", "width=720,height=640");
    if (!popup) {
        window.produtoPage?.showMessage("Nao foi possivel abrir a visualizacao do codigo de barras.", "error");
        return;
    }

    const barcodeMarkup = codigo.length === 13
        ? gerarMarkupEan13(codigo)
        : `<div style="padding:24px;border:1px solid #d5d8dc;border-radius:12px;background:#fafafa;text-align:center;">
            <p style="font-size:14px;color:#5f6368;margin:0 0 12px;">Codigo fora do padrao EAN-13. Exibicao textual:</p>
            <strong style="font-size:28px;letter-spacing:0.2em;">${escapeHtml(codigoOriginal)}</strong>
        </div>`;

    popup.document.open();
    popup.document.write(`
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <title>Etiqueta - ${escapeHtml(item.nome || "Produto")}</title>
            <style>
                body { font-family: Arial, sans-serif; background: #f3f4f6; margin: 0; padding: 24px; color: #111827; }
                .sheet { max-width: 640px; margin: 0 auto; background: #fff; border-radius: 18px; padding: 28px; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.14); }
                .title { margin: 0 0 8px; font-size: 28px; }
                .meta { margin: 0 0 20px; color: #4b5563; }
                .actions { display: flex; gap: 12px; margin-top: 24px; }
                .actions button { border: none; border-radius: 10px; padding: 12px 18px; font-weight: 600; cursor: pointer; }
                .print { background: #0ea5e9; color: #082f49; }
                .close { background: #e5e7eb; color: #111827; }
                @media print {
                    body { background: #fff; padding: 0; }
                    .sheet { box-shadow: none; padding: 0; }
                    .actions { display: none; }
                }
            </style>
        </head>
        <body>
            <div class="sheet">
                <h1 class="title">${escapeHtml(item.nome || "Produto")}</h1>
                <p class="meta">Empresa: ${escapeHtml(item.empresa_nome || "-")} | Codigo: ${escapeHtml(codigoOriginal)}</p>
                ${barcodeMarkup}
                <div class="actions">
                    <button type="button" class="print" onclick="window.print()">Imprimir</button>
                    <button type="button" class="close" onclick="window.close()">Fechar</button>
                </div>
            </div>
        </body>
        </html>
    `);
    popup.document.close();
    popup.focus();
}

function normalizarCodigoEtiqueta(codigo) {
    if (!codigo) return "";

    if (codigo.length === 13) {
        return codigo;
    }

    if (codigo.length === 12) {
        return `${codigo}${calcularDigitoEan13(codigo)}`;
    }

    return "";
}

function calcularDigitoEan13(base) {
    if (!/^\d{12}$/.test(String(base || ""))) {
        return "";
    }

    const digitos = String(base).split("").map(Number);
    const soma = digitos.reduce((total, digito, index) => {
        return total + (index % 2 === 0 ? digito : digito * 3);
    }, 0);

    return String((10 - (soma % 10)) % 10);
}

function gerarMarkupEan13(codigo) {
    const patternsA = {
        0: "0001101", 1: "0011001", 2: "0010011", 3: "0111101", 4: "0100011",
        5: "0110001", 6: "0101111", 7: "0111011", 8: "0110111", 9: "0001011"
    };
    const patternsB = {
        0: "0100111", 1: "0110011", 2: "0011011", 3: "0100001", 4: "0011101",
        5: "0111001", 6: "0000101", 7: "0010001", 8: "0001001", 9: "0010111"
    };
    const patternsC = {
        0: "1110010", 1: "1100110", 2: "1101100", 3: "1000010", 4: "1011100",
        5: "1001110", 6: "1010000", 7: "1000100", 8: "1001000", 9: "1110100"
    };
    const parity = {
        0: "AAAAAA", 1: "AABABB", 2: "AABBAB", 3: "AABBBA", 4: "ABAABB",
        5: "ABBAAB", 6: "ABBBAA", 7: "ABABAB", 8: "ABABBA", 9: "ABBABA"
    };

    const firstDigit = Number(codigo[0]);
    const leftDigits = codigo.slice(1, 7).split("").map(Number);
    const rightDigits = codigo.slice(7).split("").map(Number);
    const parityPattern = parity[firstDigit];
    const moduleWidth = 2;
    const quietZone = 12;

    let encoded = "101";
    leftDigits.forEach((digit, index) => {
        encoded += parityPattern[index] === "A" ? patternsA[digit] : patternsB[digit];
    });
    encoded += "01010";
    rightDigits.forEach((digit) => {
        encoded += patternsC[digit];
    });
    encoded += "101";

    const bars = encoded.split("").map((bit, index) => {
        if (bit !== "1") {
            return "";
        }

        const isGuard = index < 3 || (index >= 45 && index < 50) || index >= 92;
        const height = isGuard ? 110 : 96;
        return `<rect x="${quietZone + (index * moduleWidth)}" y="10" width="${moduleWidth}" height="${height}" fill="#111827"></rect>`;
    }).join("");

    const svgWidth = (encoded.length * moduleWidth) + (quietZone * 2);
    const svgHeight = 138;

    return `
        <div style="padding:24px;border:1px solid #d5d8dc;border-radius:12px;background:#fff;">
            <svg viewBox="0 0 ${svgWidth} ${svgHeight}" width="100%" height="180" role="img" aria-label="Codigo de barras EAN-13">
                <rect x="0" y="0" width="${svgWidth}" height="${svgHeight}" fill="#ffffff"></rect>
                ${bars}
                <text x="${svgWidth / 2}" y="${svgHeight - 8}" text-anchor="middle" font-size="16" font-family="Arial, sans-serif" letter-spacing="3">${escapeHtml(codigo)}</text>
            </svg>
        </div>
    `;
}
