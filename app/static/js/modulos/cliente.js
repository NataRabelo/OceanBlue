window.clientePage = null;
window.clienteModule = {
    auxiliares: { empresas: [], tipos_pessoa: [], canais_mensagem: [] },
    configuracoes: [],
    configuracoesPorEmpresa: {},
    clienteDetalheAtual: null
};

const clienteCanEdit = () => window.userHasPermission?.("editar_cliente");
const clienteCanDelete = () => window.userHasPermission?.("excluir_cliente");
const clienteCanSendMessage = () => window.userHasPermission?.("enviar_mensagem_cliente");
const clienteCanManageSettings = () => window.userHasPermission?.("gerenciar_configuracao_cliente");

document.addEventListener("DOMContentLoaded", async () => {
    try {
        await carregarAuxiliaresCliente();
        if (clienteCanManageSettings()) {
            await carregarConfiguracoesCliente();
        }

        instanciarCrudCliente();
        bindClienteAcoes();
        aplicarMascarasCliente();
        popularCamposAuxiliaresCliente();
        atualizarKpisCliente();
        window.clientePage.init();
    } catch (error) {
        showClienteMessage(error.message || "Erro ao carregar o modulo de clientes.", "error");
    }

    if (window.lucide) {
        lucide.createIcons();
    }
});

function instanciarCrudCliente() {
    window.clientePage = new CrudPage({
        apiBaseUrl: "/api/clientes/",
        tableBodyId: "cliente-table-body",
        formCreateId: "cliente-form-cadastro",
        formEditId: "cliente-form-edicao",
        formDeleteId: "cliente-form-delete",
        modalCreateId: "cliente-modal-cadastro",
        modalEditId: "cliente-modal-edicao",
        modalDeleteId: "cliente-modal-delete",
        searchInputId: "cliente-input-busca",
        paginationContainerId: "cliente-pagination",
        pageSize: 10,
        fields: ["nome", "documento", "email", "telefone", "whatsapp"],
        messages: {
            loadError: "Erro ao carregar clientes.",
            createSuccess: "Cliente cadastrado com sucesso.",
            createError: "Erro ao cadastrar cliente.",
            updateSuccess: "Cliente atualizado com sucesso.",
            updateError: "Erro ao atualizar cliente.",
            deleteSuccess: "Cliente inativado com sucesso.",
            deleteError: "Erro ao inativar cliente."
        },
        mapItemToEditForm: (item) => ({
            id: item.id || "",
            nome: item.nome || "",
            documento: item.documento || "",
            tipo_pessoa: item.tipo_pessoa || "FISICA",
            email: item.email || "",
            telefone: item.telefone || "",
            whatsapp: item.whatsapp || "",
            data_nascimento: item.data_nascimento || "",
            observacao: item.observacao || "",
            aceita_email: Boolean(item.aceita_email),
            aceita_sms: Boolean(item.aceita_sms),
            aceita_whatsapp: Boolean(item.aceita_whatsapp),
            ativo: Boolean(item.ativo)
        }),
        beforeOpenCreateModal: async () => {
            await carregarAuxiliaresCliente();
            popularCamposAuxiliaresCliente();
            resetClienteForm("cliente-form-cadastro");
        },
        beforeOpenEditModal: async () => {
            await carregarAuxiliaresCliente();
            popularCamposAuxiliaresCliente();
        },
        beforeSubmitCreate: normalizarPayloadCliente,
        beforeSubmitEdit: normalizarPayloadCliente,
        renderRow: renderClienteRow
    });

    const originalLoad = window.clientePage.load.bind(window.clientePage);
    window.clientePage.load = async () => {
        await originalLoad();
        atualizarKpisCliente();
    };

    window.clientePage.openCreateModal = async () => {
        await carregarAuxiliaresCliente();
        popularCamposAuxiliaresCliente();
        window.clientePage.clearForm("cliente-form-cadastro");
        resetClienteForm("cliente-form-cadastro");
        window.clientePage.openModal("cliente-modal-cadastro");
    };

    window.clientePage.fillForm = (formId, data) => {
        const form = document.getElementById(formId);
        if (!form) return;

        Object.keys(data || {}).forEach((key) => {
            const field = form.querySelector(`[name="${key}"]`);
            if (!field) return;

            if (field.type === "checkbox") {
                field.checked = Boolean(data[key]);
                return;
            }

            field.value = data[key] ?? "";
            window.InputMask?.refresh(field);
        });
    };
}

function bindClienteAcoes() {
    document.getElementById("cliente-open-broadcast")?.addEventListener("click", async () => {
        try {
            await abrirDisparoColetivoCliente();
        } catch (error) {
            showClienteMessage(error.message || "Erro ao preparar o disparo coletivo.", "error");
        }
    });

    document.getElementById("cliente-open-settings")?.addEventListener("click", async () => {
        try {
            await abrirModalConfiguracoesCliente();
        } catch (error) {
            showClienteMessage(error.message || "Erro ao carregar configuracoes.", "error");
        }
    });

    document.getElementById("cliente-form-mensagem")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const clienteId = document.getElementById("cliente-mensagem-id")?.value || "";

        try {
            const payload = {
                empresa_id: document.getElementById("cliente-mensagem-empresa")?.value || "",
                idempotency_key: event.target.dataset.chave ||= crypto.randomUUID(),
                canal: document.getElementById("cliente-mensagem-canal")?.value || "",
                assunto: (document.getElementById("cliente-mensagem-assunto")?.value || "").trim(),
                conteudo: (document.getElementById("cliente-mensagem-conteudo")?.value || "").trim()
            };

            const result = await requestJson(`/api/clientes/${clienteId}/mensagens`, {
                method: "POST",
                headers: getClienteAuthHeaders(true),
                body: JSON.stringify(payload)
            });

            showClienteMessage(result.message || "Mensagem enviada com sucesso.", "success");
            fecharClienteModal("cliente-modal-mensagem");
            document.getElementById("cliente-form-mensagem")?.reset();
            delete event.target.dataset.chave;
        } catch (error) {
            showClienteMessage(error.message || "Erro ao enviar mensagem.", "error");
        }
    });

    document.getElementById("cliente-form-disparo-coletivo")?.addEventListener("submit", async (event) => {
        event.preventDefault();

        try {
            const payload = {
                empresa_id: document.getElementById("cliente-coletivo-empresa")?.value || "",
                idempotency_key: event.target.dataset.chave ||= crypto.randomUUID(),
                canal: document.getElementById("cliente-coletivo-canal")?.value || "",
                assunto: (document.getElementById("cliente-coletivo-assunto")?.value || "").trim(),
                conteudo: (document.getElementById("cliente-coletivo-conteudo")?.value || "").trim()
            };

            const result = await requestJson("/api/clientes/mensagens/disparo-coletivo", {
                method: "POST",
                headers: getClienteAuthHeaders(true),
                body: JSON.stringify(payload)
            });

            const resumo = result.data || {};
            const mensagem = result.message
                || `Disparo concluido. ${resumo.enviados || 0} enviados, ${resumo.ignorados || 0} ignorados e ${resumo.erros || 0} com erro.`;

            showClienteMessage(mensagem, "success");
            fecharClienteModal("cliente-modal-disparo-coletivo");
            document.getElementById("cliente-form-disparo-coletivo")?.reset();
            delete event.target.dataset.chave;
        } catch (error) {
            showClienteMessage(error.message || "Erro ao executar o disparo coletivo.", "error");
        }
    });

    document.getElementById("cliente-config-empresa")?.addEventListener("change", async (event) => {
        try {
            await carregarConfiguracaoEmpresaSelecionada(event.target.value);
        } catch (error) {
            showClienteMessage(error.message || "Erro ao carregar configuracao da empresa.", "error");
        }
    });

    document.getElementById("cliente-form-configuracoes")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const empresaId = document.getElementById("cliente-config-empresa")?.value || "";

        try {
            const result = await requestJson(`/api/clientes/configuracoes/${empresaId}`, {
                method: "PUT",
                headers: getClienteAuthHeaders(true),
                body: JSON.stringify(coletarPayloadConfiguracaoCliente())
            });

            clienteModule.configuracoesPorEmpresa[String(empresaId)] = result.data || null;
            await carregarConfiguracoesCliente();
            preencherFormularioConfiguracaoCliente(result.data || {});
            atualizarKpisCliente();
            showClienteMessage(result.message || "Configuracoes atualizadas com sucesso.", "success");
        } catch (error) {
            showClienteMessage(error.message || "Erro ao salvar configuracoes.", "error");
        }
    });

    document.getElementById("cliente-form-teste-config")?.addEventListener("submit", async (event) => {
        event.preventDefault();
        const empresaId = document.getElementById("cliente-config-empresa")?.value || "";

        try {
            const payload = {
                canal: document.getElementById("config-teste-canal")?.value || "",
                destinatario: (document.getElementById("config-teste-destinatario")?.value || "").trim(),
                assunto: (document.getElementById("config-teste-assunto")?.value || "").trim(),
                conteudo: (document.getElementById("config-teste-conteudo")?.value || "").trim(),
                configuracao: coletarPayloadConfiguracaoCliente(),
            };

            const result = await requestJson(`/api/clientes/configuracoes/${empresaId}/testar`, {
                method: "POST",
                headers: getClienteAuthHeaders(true),
                body: JSON.stringify(payload)
            });

            showClienteMessage(result.message || "Teste executado com sucesso.", "success");
        } catch (error) {
            showClienteMessage(error.message || "Erro ao testar a comunicacao.", "error");
        }
    });
}

async function carregarAuxiliaresCliente() {
    const result = await requestJson("/api/clientes/auxiliares", { method: "GET" });
    clienteModule.auxiliares = result.data || clienteModule.auxiliares;
    popularCamposAuxiliaresCliente();
}

async function carregarConfiguracoesCliente() {
    const result = await requestJson("/api/clientes/configuracoes", { method: "GET" });
    clienteModule.configuracoes = Array.isArray(result.data) ? result.data : [];
    clienteModule.configuracoesPorEmpresa = clienteModule.configuracoes.reduce((accumulator, item) => {
        accumulator[String(item.empresa_id)] = item;
        return accumulator;
    }, {});
}

function popularCamposAuxiliaresCliente() {
    popularTiposPessoaCliente();
    popularEmpresasCliente("cliente-mensagem-empresa");
    popularEmpresasCliente("cliente-config-empresa");
    popularEmpresasCliente("cliente-coletivo-empresa");
    popularCanaisCliente();
}

function popularTiposPessoaCliente() {
    const tipos = clienteModule.auxiliares.tipos_pessoa || ["FISICA", "JURIDICA"];
    [
        document.getElementById("cliente-cadastro-tipo-pessoa"),
        document.getElementById("cliente-edicao-tipo-pessoa")
    ].filter(Boolean).forEach((select) => {
        const currentValue = select.value || "FISICA";
        select.innerHTML = tipos.map((tipo) => `
            <option value="${tipo}" ${tipo === currentValue ? "selected" : ""}>
                ${tipo === "JURIDICA" ? "Juridica" : "Fisica"}
            </option>
        `).join("");
    });
}

function popularEmpresasCliente(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const currentValue = select.value || clienteModule.auxiliares.empresas[0]?.id || "";
    select.innerHTML = clienteModule.auxiliares.empresas.map((empresa) => `
        <option value="${empresa.id}" ${String(empresa.id) === String(currentValue) ? "selected" : ""}>
            ${escapeClienteHtml(empresa.nome || `Empresa #${empresa.id}`)}
        </option>
    `).join("");
}

function popularCanaisCliente() {
    const canais = clienteModule.auxiliares.canais_mensagem || ["EMAIL", "SMS", "WHATSAPP"];
    [
        document.getElementById("cliente-mensagem-canal"),
        document.getElementById("config-teste-canal"),
        document.getElementById("cliente-coletivo-canal")
    ].filter(Boolean).forEach((select) => {
        const currentValue = select.value || canais[0] || "";
        select.innerHTML = canais.map((canal) => `
            <option value="${canal}" ${canal === currentValue ? "selected" : ""}>
                ${formatarCanalCliente(canal)}
            </option>
        `).join("");
    });
}

async function abrirDetalhesCliente(clienteId) {
    try {
        const [carteiraResult, mensagensResult] = await Promise.all([
            requestJson(`/api/clientes/${clienteId}/carteira`, { method: "GET" }),
            requestJson(`/api/clientes/${clienteId}/mensagens`, { method: "GET" })
        ]);

        const dadosCarteira = carteiraResult.data || {};
        const mensagens = Array.isArray(mensagensResult.data) ? mensagensResult.data : [];
        const cliente = dadosCarteira.cliente || {};
        const carteira = dadosCarteira.carteira || {};
        const creditos = carteira.creditos_disponiveis || [];
        const movimentos = carteira.movimentos || [];
        const vendas = dadosCarteira.historico_vendas || [];
        const container = document.getElementById("cliente-detalhes-content");

        clienteModule.clienteDetalheAtual = cliente;
        if (!container) return;

        container.innerHTML = `
            <div class="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <article class="cliente-kpi-card lg:col-span-2">
                    <span class="cliente-kpi-label">Cliente</span>
                    <strong class="cliente-kpi-value">${escapeClienteHtml(cliente.nome || "-")}</strong>
                    <p class="text-sm text-slate-400 mt-3">${escapeClienteHtml(formatClienteDocumento(cliente.documento) || "Sem documento")}</p>
                    <p class="text-sm text-slate-400">${escapeClienteHtml(cliente.email || "Sem email")} | ${escapeClienteHtml(formatClientePhone(cliente.whatsapp || cliente.telefone) || "Sem telefone")}</p>
                </article>
                <article class="cliente-kpi-card">
                    <span class="cliente-kpi-label">Saldo atual</span>
                    <strong class="cliente-kpi-value">${formatClienteCurrency(carteira.saldo_disponivel || 0)}</strong>
                </article>
                <article class="cliente-kpi-card">
                    <span class="cliente-kpi-label">Vendas vinculadas</span>
                    <strong class="cliente-kpi-value">${formatClienteInteger(cliente.quantidade_vendas || 0)}</strong>
                </article>
            </div>

            <section class="cliente-config-card">
                <h4 class="cliente-section-title">Creditos disponiveis</h4>
                ${renderListaCliente(creditos, (credito) => `
                    <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <div>
                                <p class="font-semibold text-white">${escapeClienteHtml(credito.empresa_nome || "Sem empresa")}</p>
                                <p class="text-sm text-slate-400">Venda ${escapeClienteHtml(credito.venda_origem_numero || "-")}</p>
                            </div>
                            <div class="text-right">
                                <p class="font-semibold text-emerald-300">${formatClienteCurrency(credito.saldo_disponivel)}</p>
                                <p class="text-sm text-slate-400">Expira em ${formatClienteDate(credito.data_expiracao, false)}</p>
                            </div>
                        </div>
                    </article>
                `, "Nenhum credito de cashback disponivel.")}
            </section>

            <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <section class="cliente-config-card">
                    <h4 class="cliente-section-title">Historico da carteira</h4>
                    ${renderListaCliente(movimentos, (movimento) => `
                        <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                            <div class="flex items-center justify-between gap-4">
                                <div>
                                    <p class="font-medium text-white">${escapeClienteHtml(formatarTipoMovimentoCarteira(movimento.tipo))}</p>
                                    <p class="text-sm text-slate-400">${escapeClienteHtml(movimento.descricao || "-")}</p>
                                </div>
                                <strong class="text-white">${formatClienteCurrency(movimento.valor)}</strong>
                            </div>
                            <p class="text-xs text-slate-500 mt-3">${formatClienteDate(movimento.data_movimento)}${movimento.funcionario_nome ? ` | ${escapeClienteHtml(movimento.funcionario_nome)}` : ""}</p>
                        </article>
                    `, "Nenhum movimento na carteira ate o momento.")}
                </section>

                <section class="cliente-config-card">
                    <h4 class="cliente-section-title">Mensagens enviadas</h4>
                    ${renderListaCliente(mensagens, (mensagem) => `
                        <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                            <div class="flex items-center justify-between gap-4">
                                <div>
                                    <p class="font-medium text-white">${escapeClienteHtml(formatarCanalCliente(mensagem.canal))}</p>
                                    <p class="text-sm text-slate-400">${escapeClienteHtml(mensagem.assunto || mensagem.destinatario || "-")}</p>
                                </div>
                                <span class="cliente-chip ${mensagem.status === "ENVIADO" ? "cliente-chip-ok" : "cliente-chip-off"}">
                                    ${escapeClienteHtml(mensagem.status || "-")}
                                </span>
                            </div>
                            <p class="text-sm text-slate-300 mt-3 whitespace-pre-line">${escapeClienteHtml(mensagem.conteudo || "-")}</p>
                            <p class="text-xs text-slate-500 mt-3">${formatClienteDate(mensagem.enviado_em || mensagem.criado_em)}${mensagem.erro ? ` | ${escapeClienteHtml(mensagem.erro)}` : ""}</p>
                        </article>
                    `, "Nenhuma mensagem registrada para este cliente.")}
                </section>
            </div>

            <section class="cliente-config-card">
                <h4 class="cliente-section-title">Historico de vendas</h4>
                ${renderListaCliente(vendas, (venda) => `
                    <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                            <div>
                                <p class="font-semibold text-white">${escapeClienteHtml(venda.numero_unico || `Venda #${venda.id}`)}</p>
                                <p class="text-sm text-slate-400">${escapeClienteHtml(venda.empresa_nome || "-")} | ${formatClienteDate(venda.data_venda)}</p>
                            </div>
                            <div class="text-right">
                                <p class="font-semibold text-white">${formatClienteCurrency(venda.total)}</p>
                                <p class="text-sm text-slate-400">Cashback ${formatClienteCurrency(venda.cashback_gerado || 0)}</p>
                            </div>
                        </div>
                    </article>
                `, "Nenhuma venda vinculada a este cliente.")}
            </section>
        `;

        abrirClienteModal("cliente-modal-detalhes");
        if (window.lucide) lucide.createIcons();
    } catch (error) {
        showClienteMessage(error.message || "Erro ao carregar os detalhes do cliente.", "error");
    }
}

async function abrirMensagemCliente(clienteId) {
    const cliente = window.clientePage?.items?.find((item) => String(item.id) === String(clienteId));
    if (!cliente) {
        showClienteMessage("Cliente nao encontrado para envio.", "error");
        return;
    }

    await carregarAuxiliaresCliente();
    document.getElementById("cliente-form-mensagem")?.reset();
    document.getElementById("cliente-mensagem-id").value = cliente.id;
    document.getElementById("cliente-mensagem-assunto").value = `Comunicacao ${cliente.nome}`;
    abrirClienteModal("cliente-modal-mensagem");
}

async function abrirDisparoColetivoCliente() {
    await carregarAuxiliaresCliente();
    document.getElementById("cliente-form-disparo-coletivo")?.reset();
    popularEmpresasCliente("cliente-coletivo-empresa");
    popularCanaisCliente();
    setClienteValue("cliente-coletivo-assunto", "Comunicado para clientes");
    abrirClienteModal("cliente-modal-disparo-coletivo");
}

async function abrirModalConfiguracoesCliente() {
    await carregarAuxiliaresCliente();
    await carregarConfiguracoesCliente();
    popularEmpresasCliente("cliente-config-empresa");
    popularCanaisCliente();

    const empresaId = document.getElementById("cliente-config-empresa")?.value || clienteModule.auxiliares.empresas[0]?.id || "";
    await carregarConfiguracaoEmpresaSelecionada(empresaId);
    abrirClienteModal("cliente-modal-configuracoes");
}

async function carregarConfiguracaoEmpresaSelecionada(empresaId) {
    const companyKey = String(empresaId || "");
    if (!companyKey) {
        preencherFormularioConfiguracaoCliente({});
        return;
    }

    const configuracaoExistente = clienteModule.configuracoesPorEmpresa[companyKey];
    if (configuracaoExistente) {
        preencherFormularioConfiguracaoCliente(configuracaoExistente);
        return;
    }

    const result = await requestJson(`/api/clientes/configuracoes/${companyKey}`, { method: "GET" });
    clienteModule.configuracoesPorEmpresa[companyKey] = result.data || {};
    preencherFormularioConfiguracaoCliente(result.data || {});
}

function preencherFormularioConfiguracaoCliente(configuracao) {
    setClienteChecked("config-cashback-ativo", configuracao.cashback_ativo);
    setClienteValue("config-cashback-percentual", formatClienteMoneyInput(configuracao.cashback_percentual || 0));
    setClienteValue(
        "config-cashback-limite-venda",
        formatClienteMoneyInput(configuracao.cashback_percentual_limite_resgate_venda || 100)
    );
    setClienteValue("config-cashback-validade", configuracao.cashback_validade_dias ?? 30);
    setClienteValue("config-cashback-minimo", formatClienteMoneyInput(configuracao.cashback_valor_minimo_resgate || 0));
    setClienteValue("config-cancelamento-venda", configuracao.cancelamento_venda_limite_horas ?? 24);
    setClienteValue("config-cancelamento-item", configuracao.cancelamento_item_limite_horas ?? 24);
    setClienteValue("config-cancelamento-movimento", configuracao.cancelamento_movimento_limite_horas ?? 24);
    setClienteChecked("config-whatsapp-habilitado", configuracao.whatsapp_habilitado);
    setClienteValue("config-whatsapp-api-url", configuracao.whatsapp_api_url || "");
    setClienteValue("config-whatsapp-token", "");
    setClienteValue("config-whatsapp-remetente", configuracao.whatsapp_remetente || "");
    setClienteChecked("config-sms-habilitado", configuracao.sms_habilitado);
    setClienteValue("config-sms-api-url", configuracao.sms_api_url || "");
    setClienteValue("config-sms-token", "");
    setClienteValue("config-sms-remetente", configuracao.sms_remetente || "");
    setClienteValue("config-timeout", configuracao.request_timeout_segundos ?? 15);

    const whatsappToken = document.getElementById("config-whatsapp-token");
    const smsToken = document.getElementById("config-sms-token");
    if (whatsappToken) {
        whatsappToken.placeholder = configuracao.whatsapp_token_configurado
            ? "Token ja cadastrado. Preencha somente para alterar"
            : "Token Bearer";
    }
    if (smsToken) {
        smsToken.placeholder = configuracao.sms_token_configurado
            ? "Token ja cadastrado. Preencha somente para alterar"
            : "Token Bearer";
    }
}

function coletarPayloadConfiguracaoCliente() {
    const payload = {
        cashback_ativo: document.getElementById("config-cashback-ativo")?.checked,
        cashback_percentual: normalizeClienteMoneyForApi(document.getElementById("config-cashback-percentual")?.value || "0"),
        cashback_percentual_limite_resgate_venda: normalizeClienteMoneyForApi(
            document.getElementById("config-cashback-limite-venda")?.value || "100"
        ),
        cashback_validade_dias: document.getElementById("config-cashback-validade")?.value || "30",
        cashback_valor_minimo_resgate: normalizeClienteMoneyForApi(document.getElementById("config-cashback-minimo")?.value || "0"),
        cancelamento_venda_limite_horas: document.getElementById("config-cancelamento-venda")?.value || "24",
        cancelamento_item_limite_horas: document.getElementById("config-cancelamento-item")?.value || "24",
        cancelamento_movimento_limite_horas: document.getElementById("config-cancelamento-movimento")?.value || "24",
        whatsapp_habilitado: document.getElementById("config-whatsapp-habilitado")?.checked,
        whatsapp_api_url: (document.getElementById("config-whatsapp-api-url")?.value || "").trim(),
        whatsapp_remetente: (document.getElementById("config-whatsapp-remetente")?.value || "").trim(),
        sms_habilitado: document.getElementById("config-sms-habilitado")?.checked,
        sms_api_url: (document.getElementById("config-sms-api-url")?.value || "").trim(),
        sms_remetente: (document.getElementById("config-sms-remetente")?.value || "").trim(),
        request_timeout_segundos: document.getElementById("config-timeout")?.value || "15"
    };

    const whatsappToken = (document.getElementById("config-whatsapp-token")?.value || "").trim();
    const smsToken = (document.getElementById("config-sms-token")?.value || "").trim();

    if (whatsappToken) payload.whatsapp_token = whatsappToken;
    if (smsToken) payload.sms_token = smsToken;

    return payload;
}

function renderClienteRow(item) {
    return `
        <tr class="hover:bg-slate-800/40 transition">
            <td class="px-5 py-4 align-middle">
                <div class="flex items-start gap-3">
                    <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                        <i data-lucide="contact-round" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <p class="font-semibold text-white">${escapeClienteHtml(item.nome || "-")}</p>
                        <p class="text-xs text-slate-500">${escapeClienteHtml(item.tipo_pessoa === "JURIDICA" ? "Pessoa juridica" : "Pessoa fisica")}</p>
                        <p class="text-xs text-slate-500">${escapeClienteHtml(formatClienteDocumento(item.documento) || "Sem documento")}</p>
                    </div>
                </div>
            </td>
            <td class="px-5 py-4 align-middle">
                <p class="text-slate-300">${escapeClienteHtml(item.email || "Sem email")}</p>
                <p class="text-sm text-slate-500">${escapeClienteHtml(formatClientePhone(item.whatsapp || item.telefone) || "Sem telefone")}</p>
                <div class="flex flex-wrap gap-2 mt-2">
                    <span class="cliente-chip ${item.aceita_email ? "cliente-chip-ok" : "cliente-chip-off"}">Email</span>
                    <span class="cliente-chip ${item.aceita_sms ? "cliente-chip-ok" : "cliente-chip-off"}">SMS</span>
                    <span class="cliente-chip ${item.aceita_whatsapp ? "cliente-chip-ok" : "cliente-chip-off"}">WhatsApp</span>
                </div>
            </td>
            <td class="px-5 py-4 align-middle text-right text-white font-semibold">${formatClienteCurrency(item.saldo_cashback)}</td>
            <td class="px-5 py-4 align-middle text-right text-slate-300">${formatClienteInteger(item.quantidade_vendas || 0)}</td>
            <td class="px-5 py-4 align-middle text-right text-slate-300">${formatClienteCurrency(item.total_vendido)}</td>
            <td class="px-5 py-4 align-middle">
                <div class="flex items-center justify-center gap-2">
                    <button type="button" onclick="abrirDetalhesCliente(${item.id})"
                        class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-300 hover:bg-sky-500/20 transition"
                        title="Carteira e historico">
                        <i data-lucide="wallet-cards" class="w-4 h-4"></i>
                    </button>
                    ${clienteCanSendMessage() ? `
                        <button type="button" onclick="abrirMensagemCliente(${item.id})"
                            class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 hover:bg-emerald-500/20 transition"
                            title="Enviar mensagem">
                            <i data-lucide="send" class="w-4 h-4"></i>
                        </button>
                    ` : ""}
                    ${clienteCanEdit() ? `
                        <button type="button" onclick="clientePage.openEditModal(${item.id})"
                            class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 transition"
                            title="Editar cliente">
                            <i data-lucide="square-pen" class="w-4 h-4"></i>
                        </button>
                    ` : ""}
                    ${clienteCanDelete() ? `
                        <button type="button" onclick="clientePage.openDeleteModal(${item.id})"
                            class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition"
                            title="Inativar cliente">
                            <i data-lucide="user-x" class="w-4 h-4"></i>
                        </button>
                    ` : ""}
                </div>
            </td>
        </tr>
    `;
}

function atualizarKpisCliente() {
    const itens = Array.isArray(window.clientePage?.items) ? window.clientePage.items : [];
    const saldoCashback = itens.reduce((sum, item) => sum + parseClienteMoney(item.saldo_cashback), 0);
    const canaisLiberados = clienteModule.configuracoes.reduce((sum, config) => {
        return sum
            + (config.email_habilitado ? 1 : 0)
            + (config.whatsapp_habilitado ? 1 : 0)
            + (config.sms_habilitado ? 1 : 0);
    }, 0);

    setClienteText("cliente-kpi-total", String(itens.filter((item) => item.ativo !== false).length));
    setClienteText("cliente-kpi-cashback", formatClienteCurrency(saldoCashback));
    setClienteText("cliente-kpi-canais", String(canaisLiberados));
}

function normalizarPayloadCliente(payload) {
    return {
        ...payload,
        nome: (payload.nome || "").trim(),
        documento: (payload.documento || "").trim(),
        tipo_pessoa: payload.tipo_pessoa || "FISICA",
        email: (payload.email || "").trim(),
        telefone: (payload.telefone || "").trim(),
        whatsapp: (payload.whatsapp || "").trim(),
        data_nascimento: payload.data_nascimento || "",
        observacao: (payload.observacao || "").trim(),
        aceita_email: Boolean(payload.aceita_email),
        aceita_sms: Boolean(payload.aceita_sms),
        aceita_whatsapp: payload.aceita_whatsapp === undefined ? true : Boolean(payload.aceita_whatsapp),
        ativo: payload.ativo === undefined ? true : Boolean(payload.ativo)
    };
}

function resetClienteForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    form.reset();
    const tipoPessoa = form.querySelector('[name="tipo_pessoa"]');
    if (tipoPessoa) tipoPessoa.value = "FISICA";
    const whatsapp = form.querySelector('[name="aceita_whatsapp"]');
    const ativo = form.querySelector('[name="ativo"]');
    if (whatsapp) whatsapp.checked = true;
    if (ativo) ativo.checked = true;
}

function aplicarMascarasCliente() {
    ["config-cashback-percentual", "config-cashback-limite-venda", "config-cashback-minimo"].forEach(bindClienteMoneyMask);
    window.InputMask?.bindAll(document);
}

function bindClienteMoneyMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    window.DecimalInput?.bind(input, { decimals: 2, allowEmpty: false });
}

function renderListaCliente(items, renderer, emptyMessage) {
    const list = Array.isArray(items) ? items : [];
    if (!list.length) {
        return `<div class="cliente-empty-panel">${escapeClienteHtml(emptyMessage || "Nenhum registro encontrado.")}</div>`;
    }
    return `<div class="space-y-3">${list.map((item) => renderer(item)).join("")}</div>`;
}

function abrirClienteModal(modalId) {
    document.getElementById(modalId)?.classList.remove("hidden");
}

function fecharClienteModal(modalId) {
    document.getElementById(modalId)?.classList.add("hidden");
}

function requestJson(url, options = {}) {
    return fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            ...getClienteAuthHeaders(false),
            ...(options.headers || {})
        }
    }).then(async (response) => {
        let result;
        try {
            result = await response.json();
        } catch {
            result = { success: false, message: "Resposta invalida do servidor." };
        }

        if (!response.ok || result.success === false) {
            throw new Error(result.message || "Erro na requisicao.");
        }

        return result;
    });
}

function getClienteAuthHeaders(isJson = false) {
    const token = localStorage.getItem("token");
    const headers = {};
    if (isJson) headers["Content-Type"] = "application/json";
    if (token) headers.Authorization = `Bearer ${token}`;
    return headers;
}

function showClienteMessage(message, type = "success") {
    const old = document.getElementById("crud-message");
    if (old) old.remove();

    const div = document.createElement("div");
    div.id = "crud-message";
    div.className = `
        fixed top-4 right-4 z-[9999] px-4 py-3 rounded-xl shadow-lg text-sm font-medium
        ${type === "success" ? "bg-emerald-500 text-white" : "bg-red-500 text-white"}
    `;
    div.textContent = message;
    document.body.appendChild(div);
    setTimeout(() => div.remove(), 3000);
}

function parseClienteMoney(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function normalizeClienteMoneyForApi(value) {
    return window.DecimalInput?.normalize(value, 2) ?? "0.00";
}

function formatClienteMoneyInput(value) {
    return window.DecimalInput?.format(value, 2, { allowEmpty: false, useGrouping: true }) ?? "0,00";
}

function formatClienteCurrency(value) {
    const parsed = typeof value === "number" ? value : parseClienteMoney(value);
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatClienteDocumento(value) {
    return window.InputMask?.formatDocument(value) ?? String(value ?? "");
}

function formatClientePhone(value) {
    return window.InputMask?.formatPhone(value) ?? String(value ?? "");
}

function formatClienteInteger(value) {
    const parsed = Number.parseInt(String(value ?? 0).replace(/\D/g, "") || "0", 10);
    return new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatClienteDate(value, includeTime = true) {
    if (!value) return "-";
    const date = includeTime ? new Date(value) : new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return "-";
    return new Intl.DateTimeFormat("pt-BR", includeTime ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "short" }).format(date);
}

function formatarCanalCliente(canal) {
    return { EMAIL: "Email", SMS: "SMS", WHATSAPP: "WhatsApp" }[canal] || canal || "-";
}

function formatarTipoMovimentoCarteira(tipo) {
    return { CREDITO: "Credito", DEBITO: "Debito", ESTORNO: "Estorno", EXPIRACAO: "Expiracao", AJUSTE: "Ajuste" }[tipo] || tipo || "-";
}

function setClienteText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
}

function setClienteValue(id, value) {
    const element = document.getElementById(id);
    if (element) element.value = value ?? "";
}

function setClienteChecked(id, checked) {
    const element = document.getElementById(id);
    if (element) element.checked = Boolean(checked);
}

function escapeClienteHtml(value) {
    if (value === null || value === undefined) return "";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
