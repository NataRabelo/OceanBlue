window.estoquePage = {
    saldos: [],
    movimentos: [],
    configuracaoAlerta: null,
    maisVendidos: {
        periodo: "mes",
        dataInicio: "",
        dataFim: "",
        itens: []
    },
    auxiliares: {
        empresas: [],
        produtos: [],
        motivos: {
            ENTRADA: [],
            SAIDA: []
        }
    },
    notificacoes: {
        resumo: {
            estoque_baixo: 0,
            sem_estoque: 0,
            vencidos: 0,
            proximos_vencimento: 0
        },
        estoque_baixo: [],
        sem_estoque: [],
        vencidos: [],
        proximos_vencimento: []
    },
    emailOperacional: {
        empresaId: "",
        configuracao: null
    },
    filtroEmpresa: "",
    busca: "",
    movimentoSelecionadoId: null,
    paginacao: {
        saldos: { paginaAtual: 1, porPagina: 10 },
        movimentos: { paginaAtual: 1, porPagina: 10 }
    }
};

document.addEventListener("DOMContentLoaded", async () => {
    document.getElementById("alertas-atualizar")?.addEventListener("click", carregarHistoricoAlertas);
    document.getElementById("alertas-executar")?.addEventListener("click", async () => {
        try {
            const empresaId = document.getElementById("filtro-empresa")?.value;
            if (!empresaId) throw new Error("Selecione uma empresa.");
            await requestJson("/api/estoque/notificacoes/processar", {
                method: "POST", headers: getAuthHeaders(true), body: JSON.stringify({ empresa_id: empresaId })
            });
            await carregarHistoricoAlertas();
        } catch (error) { showMessage(error.message, "error"); }
    });
    bindModalClose();
    bindFilters();
    bindMovementForm();
    bindMovementHelpers();
    bindMovementCancellation();
    bindAlertPanels();
    bindBestSellerFilters();
    bindIntegerMask("movimento-quantidade");
    bindDecimalMask("movimento-valor_unitario", 2);

    await carregarTudo();

    const novaMovimentacaoBtn = document.getElementById("btn-nova-movimentacao");
    if (novaMovimentacaoBtn) {
        novaMovimentacaoBtn.addEventListener("click", abrirModalMovimentacao);
    }

    if (window.lucide) {
        lucide.createIcons();
    }
});

async function carregarHistoricoAlertas() {
    const container = document.getElementById("alertas-historico");
    if (!container) return;
    try {
        const empresaId = document.getElementById("filtro-empresa")?.value;
        if (!empresaId) throw new Error("Selecione uma empresa.");
        const result = await requestJson(`/api/estoque/notificacoes/historico?empresa_id=${encodeURIComponent(empresaId)}`, { method: "GET" });
        container.replaceChildren();
        for (const entrega of result.data) {
            const row = document.createElement("div");
            row.textContent = `${entrega.assunto} — ${entrega.destinatario} — ${entrega.status} — ${entrega.tentativas} tentativa(s). ${entrega.erro || ""}`;
            if (["FALHOU", "PENDENTE"].includes(entrega.status)) {
                const button = document.createElement("button");
                button.type = "button";
                button.textContent = "Tentar novamente";
                button.className = "ml-3 rounded bg-sky-500 px-3 py-2";
                button.addEventListener("click", async () => {
                    button.disabled = true;
                    try {
                        await requestJson(`/api/estoque/notificacoes/${entrega.id}/retentar`, { method: "POST", headers: getAuthHeaders(true), body: "{}" });
                        await carregarHistoricoAlertas();
                    } catch (error) { showMessage(error.message, "error"); button.disabled = false; }
                });
                row.append(button);
            }
            container.append(row);
        }
        if (!result.data.length) container.textContent = "Nenhuma entrega registrada.";
    } catch (error) { showMessage(error.message, "error"); }
}

function estoqueNeedsAuxiliares() {
    return Boolean(
        document.getElementById("filtro-empresa")
        || document.getElementById("movimento-empresa_id")
    );
}

function estoqueNeedsSaldos() {
    return Boolean(document.getElementById("estoque-table-body"));
}

function estoqueNeedsMovimentos() {
    return Boolean(document.getElementById("movimento-table-body"));
}

function estoqueNeedsNotificacoes() {
    return Boolean(
        document.getElementById("estoque-alerta-resumo")
        || document.getElementById("estoque-alertas-lista")
        || document.getElementById("estoque-validade-lista")
    );
}

function estoqueNeedsMaisVendidos() {
    return Boolean(document.getElementById("estoque-best-sellers-list"));
}

async function carregarTudo() {
    const tarefas = [];

    if (estoqueNeedsAuxiliares()) {
        tarefas.push(carregarAuxiliares());
    }
    if (estoqueNeedsSaldos()) {
        tarefas.push(carregarSaldos());
    }
    if (estoqueNeedsMovimentos()) {
        tarefas.push(carregarMovimentos());
    }
    if (estoqueNeedsNotificacoes()) {
        tarefas.push(carregarNotificacoes());
    }
    if (estoqueNeedsMaisVendidos()) {
        tarefas.push(carregarMaisVendidos());
    }

    await Promise.all(tarefas);
}

async function carregarAuxiliares() {
    const result = await requestJson("/api/estoque/auxiliares", {
        method: "GET"
    });

    estoquePage.auxiliares = result.data || estoquePage.auxiliares;
    popularFiltroEmpresas();
    popularEmpresasModal();
    popularEmpresasEmailOperacional();
    atualizarMotivos();
    atualizarProdutosModal();
}

async function carregarSaldos() {
    const url = new URL("/api/estoque/", window.location.origin);
    if (estoquePage.filtroEmpresa) {
        url.searchParams.set("empresa_id", estoquePage.filtroEmpresa);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    estoquePage.saldos = Array.isArray(result.data) ? result.data : [];
    renderTabelaEstoque();
    atualizarKpis();
}

async function carregarMovimentos() {
    const url = new URL("/api/estoque/movimentos", window.location.origin);
    url.searchParams.set("limite", "500");

    if (estoquePage.filtroEmpresa) {
        url.searchParams.set("empresa_id", estoquePage.filtroEmpresa);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    estoquePage.movimentos = Array.isArray(result.data) ? result.data : [];
    renderTabelaMovimentos();
}

async function carregarNotificacoes() {
    const url = new URL("/api/estoque/notificacoes", window.location.origin);
    url.searchParams.set("dias_vencimento", "30");

    if (estoquePage.filtroEmpresa) {
        url.searchParams.set("empresa_id", estoquePage.filtroEmpresa);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    estoquePage.notificacoes = result.data || estoquePage.notificacoes;
    renderNotificacoes();
    atualizarKpis();
}

async function carregarConfiguracaoAlerta() {
    const response = await requestJson("/api/estoque/notificacoes/configuracao", {
        method: "GET"
    });
    estoquePage.configuracaoAlerta = response.data || null;
    preencherFormularioConfiguracaoAlerta();
}

async function carregarMaisVendidos() {
    const periodo = document.getElementById("estoque-best-sellers-periodo")?.value || estoquePage.maisVendidos.periodo || "mes";
    const dataInicio = document.getElementById("estoque-best-sellers-data-inicio")?.value || "";
    const dataFim = document.getElementById("estoque-best-sellers-data-fim")?.value || "";
    const url = new URL("/api/estoque/indicadores/produtos-mais-vendidos", window.location.origin);
    url.searchParams.set("periodo", periodo);
    url.searchParams.set("limite", "10");
    if (estoquePage.filtroEmpresa) {
        url.searchParams.set("empresa_id", estoquePage.filtroEmpresa);
    }
    if (periodo === "periodo") {
        if (dataInicio) url.searchParams.set("data_inicio", dataInicio);
        if (dataFim) url.searchParams.set("data_fim", dataFim);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    estoquePage.maisVendidos = {
        periodo,
        dataInicio,
        dataFim,
        ...(result.data || { itens: [] })
    };
    renderMaisVendidos();
}

function bindFilters() {
    const empresaFilter = document.getElementById("filtro-empresa");
    const buscaInput = document.getElementById("input-busca-estoque");

    if (empresaFilter) {
        empresaFilter.addEventListener("change", async () => {
            estoquePage.filtroEmpresa = empresaFilter.value || "";
            estoquePage.paginacao.saldos.paginaAtual = 1;
            estoquePage.paginacao.movimentos.paginaAtual = 1;
            const tarefas = [];
            if (estoqueNeedsSaldos()) tarefas.push(carregarSaldos());
            if (estoqueNeedsMovimentos()) tarefas.push(carregarMovimentos());
            if (estoqueNeedsNotificacoes()) tarefas.push(carregarNotificacoes());
            if (estoqueNeedsMaisVendidos()) tarefas.push(carregarMaisVendidos());
            await Promise.all(tarefas);
        });
    }

    if (buscaInput) {
        buscaInput.addEventListener("input", () => {
            estoquePage.busca = buscaInput.value || "";
            estoquePage.paginacao.saldos.paginaAtual = 1;
            renderTabelaEstoque();
        });
    }
}

function bindAlertPanels() {
    const alertCenterBtn = document.getElementById("btn-central-alertas");
    const alertConfigBtn = document.getElementById("btn-config-alertas");
    const alertConfigForm = document.getElementById("estoque-alert-settings-form");
    const operationalEmailBtn = document.getElementById("btn-config-email-operacional");
    const operationalEmailCompanySelect = document.getElementById("email-operacional-empresa");
    const operationalEmailForm = document.getElementById("estoque-email-settings-form");
    const operationalEmailTestForm = document.getElementById("estoque-email-test-form");

    if (alertCenterBtn) {
        alertCenterBtn.addEventListener("click", () => abrirModal("estoque-alert-center-modal"));
    }

    if (alertConfigBtn) {
        alertConfigBtn.addEventListener("click", async () => {
            try {
                await carregarConfiguracaoAlerta();
                abrirModal("estoque-alert-settings-modal");
            } catch (error) {
                showMessage(error.message || "Erro ao carregar configuracoes de alerta.", "error");
            }
        });
    }

    if (alertConfigForm) {
        alertConfigForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            try {
                const payload = {
                    popup_ao_entrar: document.getElementById("alert-popup-ao-entrar")?.checked,
                    resumo_diario: document.getElementById("alert-resumo-diario")?.checked,
                    alertar_estoque_baixo: document.getElementById("alert-estoque-baixo")?.checked,
                    alertar_sem_estoque: document.getElementById("alert-sem-estoque")?.checked,
                    alertar_validade: document.getElementById("alert-validade")?.checked,
                    dias_vencimento_alerta: document.getElementById("alert-dias-vencimento")?.value || "30",
                    email_habilitado: document.getElementById("alert-email-habilitado")?.checked,
                    email_destinatarios: document.getElementById("alert-email-destinatarios")?.value || "",
                    whatsapp_habilitado: document.getElementById("alert-whatsapp-habilitado")?.checked,
                    whatsapp_destinatarios: document.getElementById("alert-whatsapp-destinatarios")?.value || ""
                };

                const result = await requestJson("/api/estoque/notificacoes/configuracao", {
                    method: "PUT",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(payload)
                });
                estoquePage.configuracaoAlerta = result.data || null;
                showMessage(result.message || "Configuracoes salvas com sucesso.", "success");
                fecharModal("estoque-alert-settings-modal");
                await carregarNotificacoes();
            } catch (error) {
                showMessage(error.message || "Erro ao salvar configuracoes de alerta.", "error");
            }
        });
    }

    if (operationalEmailBtn) {
        operationalEmailBtn.addEventListener("click", async () => {
            try {
                if (!estoquePage.auxiliares.empresas.length) {
                    await carregarAuxiliares();
                }

                popularEmpresasEmailOperacional();
                const empresaPadrao = estoquePage.emailOperacional.empresaId
                    || estoquePage.filtroEmpresa
                    || String(estoquePage.auxiliares.empresas[0]?.id || "");

                if (operationalEmailCompanySelect && empresaPadrao) {
                    operationalEmailCompanySelect.value = empresaPadrao;
                }

                await carregarConfiguracaoEmailOperacional(operationalEmailCompanySelect?.value || empresaPadrao);
                abrirModal("estoque-email-settings-modal");
            } catch (error) {
                showMessage(error.message || "Erro ao carregar a configuracao de email operacional.", "error");
            }
        });
    }

    if (operationalEmailCompanySelect) {
        operationalEmailCompanySelect.addEventListener("change", async () => {
            try {
                await carregarConfiguracaoEmailOperacional(operationalEmailCompanySelect.value || "");
            } catch (error) {
                showMessage(error.message || "Erro ao carregar o email da empresa selecionada.", "error");
            }
        });
    }

    if (operationalEmailForm) {
        operationalEmailForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const empresaId = document.getElementById("email-operacional-empresa")?.value || "";

            try {
                const result = await requestJson(`/api/clientes/configuracoes/${empresaId}`, {
                    method: "PUT",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(coletarPayloadEmailOperacional())
                });

                estoquePage.emailOperacional = {
                    empresaId,
                    configuracao: result.data || null
                };
                preencherFormularioEmailOperacional(result.data || {});
                showMessage(result.message || "Email operacional salvo com sucesso.", "success");
            } catch (error) {
                showMessage(error.message || "Erro ao salvar o email operacional.", "error");
            }
        });
    }

    if (operationalEmailTestForm) {
        operationalEmailTestForm.addEventListener("submit", async (event) => {
            event.preventDefault();
            const empresaId = document.getElementById("email-operacional-empresa")?.value || "";

            try {
                const payload = {
                    canal: "EMAIL",
                    destinatario: (document.getElementById("email-operacional-teste-destinatario")?.value || "").trim(),
                    assunto: (document.getElementById("email-operacional-teste-assunto")?.value || "").trim(),
                    conteudo: (document.getElementById("email-operacional-teste-conteudo")?.value || "").trim(),
                    configuracao: coletarPayloadEmailOperacional(),
                };

                const result = await requestJson(`/api/clientes/configuracoes/${empresaId}/testar`, {
                    method: "POST",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(payload)
                });

                showMessage(result.message || "Teste de email executado com sucesso.", "success");
            } catch (error) {
                showMessage(error.message || "Erro ao testar o email operacional.", "error");
            }
        });
    }
}

function bindBestSellerFilters() {
    const periodo = document.getElementById("estoque-best-sellers-periodo");
    const dataInicio = document.getElementById("estoque-best-sellers-data-inicio");
    const dataFim = document.getElementById("estoque-best-sellers-data-fim");

    [periodo, dataInicio, dataFim].filter(Boolean).forEach((element) => {
        element.addEventListener("change", async () => {
            toggleBestSellerDateFilters();
            await carregarMaisVendidos();
        });
    });

    toggleBestSellerDateFilters();
}

function bindMovementForm() {
    const form = document.getElementById("form-movimentacao");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        try {
            const payload = normalizarPayloadMovimentacao();

            await requestJson("/api/estoque/movimentos/manual", {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify(payload)
            });

            showMessage("Movimentação registrada com sucesso.", "success");
            fecharModal("modal-movimentacao");
            limparFormularioMovimentacao();
            await Promise.all([carregarSaldos(), carregarMovimentos(), carregarAuxiliares(), carregarNotificacoes()]);
        } catch (error) {
            showMessage(error.message || "Erro ao registrar movimentação.", "error");
        }
    });
}

function bindMovementHelpers() {
    const tipoSelect = document.getElementById("movimento-tipo_movimento");
    const empresaSelect = document.getElementById("movimento-empresa_id");
    const produtoSelect = document.getElementById("movimento-produto_empresa_id");

    if (tipoSelect) {
        tipoSelect.addEventListener("change", () => {
            atualizarMotivos();
        });
    }

    if (empresaSelect) {
        empresaSelect.addEventListener("change", () => {
            atualizarProdutosModal();
        });
    }

    if (produtoSelect) {
        produtoSelect.addEventListener("change", () => {
            atualizarHintProduto();
        });
    }
}

function bindMovementCancellation() {
    const form = document.getElementById("form-cancelar-movimento");
    if (!form) return;

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        if (!estoquePage.movimentoSelecionadoId) {
            showMessage("Movimentacao nao selecionada para cancelamento.", "error");
            return;
        }

        try {
            const payload = {
                motivo: (document.getElementById("cancelar-movimento-motivo")?.value || "").trim()
            };

            const result = await requestJson(`/api/estoque/movimentos/${estoquePage.movimentoSelecionadoId}/cancelar`, {
                method: "POST",
                headers: getAuthHeaders(true),
                body: JSON.stringify(payload)
            });

            showMessage(result.message || "Movimentacao cancelada com sucesso.", "success");
            estoquePage.movimentoSelecionadoId = null;
            document.getElementById("cancelar-movimento-motivo").value = "";
            fecharModal("modal-cancelar-movimento");
            await Promise.all([carregarSaldos(), carregarMovimentos(), carregarAuxiliares()]);
        } catch (error) {
            showMessage(error.message || "Erro ao cancelar a movimentacao.", "error");
        }
    });
}

function popularFiltroEmpresas() {
    const select = document.getElementById("filtro-empresa");
    if (!select) return;

    const current = select.value;
    select.innerHTML = `<option value="">Todas as empresas</option>`;

    (estoquePage.auxiliares.empresas || []).forEach((empresa) => {
        const option = document.createElement("option");
        option.value = empresa.id;
        option.textContent = empresa.nome;
        if (String(empresa.id) === String(current || estoquePage.filtroEmpresa || "")) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

function popularEmpresasModal() {
    const select = document.getElementById("movimento-empresa_id");
    if (!select) return;

    const current = select.value;
    select.innerHTML = `<option value="">Selecione</option>`;

    (estoquePage.auxiliares.empresas || []).forEach((empresa) => {
        const option = document.createElement("option");
        option.value = empresa.id;
        option.textContent = empresa.nome;
        if (String(empresa.id) === String(current || "")) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

function popularEmpresasEmailOperacional() {
    const select = document.getElementById("email-operacional-empresa");
    if (!select) return;

    const empresaAtual = String(
        select.value
        || estoquePage.emailOperacional.empresaId
        || estoquePage.filtroEmpresa
        || estoquePage.auxiliares.empresas[0]?.id
        || ""
    );

    select.innerHTML = (estoquePage.auxiliares.empresas || []).map((empresa) => `
        <option value="${empresa.id}" ${String(empresa.id) === empresaAtual ? "selected" : ""}>
            ${escapeHtml(empresa.nome || `Empresa #${empresa.id}`)}
        </option>
    `).join("");
}

async function carregarConfiguracaoEmailOperacional(empresaId) {
    if (!empresaId) {
        estoquePage.emailOperacional = { empresaId: "", configuracao: null };
        preencherFormularioEmailOperacional({});
        return;
    }

    const result = await requestJson(`/api/clientes/configuracoes/${empresaId}`, { method: "GET" });
    estoquePage.emailOperacional = {
        empresaId: String(empresaId),
        configuracao: result.data || null
    };
    preencherFormularioEmailOperacional(result.data || {});
    preencherTesteEmailOperacional(result.data || {});
}

function preencherFormularioEmailOperacional(configuracao) {
    setChecked("email-operacional-habilitado", configuracao.email_habilitado);
    setValue("email-operacional-remetente-nome", configuracao.email_remetente_nome || "");
    setValue("email-operacional-remetente", configuracao.email_remetente || "");
    setValue("email-operacional-smtp-host", configuracao.smtp_host || "");
    setValue("email-operacional-smtp-port", configuracao.smtp_port ?? 587);
    setValue("email-operacional-smtp-usuario", configuracao.smtp_usuario || "");
    setValue("email-operacional-smtp-senha", "");
    setChecked("email-operacional-smtp-tls", configuracao.smtp_tls ?? true);
    setChecked("email-operacional-smtp-ssl", configuracao.smtp_ssl);

    const senhaInput = document.getElementById("email-operacional-smtp-senha");
    const senhaStatus = document.getElementById("email-operacional-smtp-senha-status");
    if (senhaInput) {
        senhaInput.placeholder = configuracao.smtp_senha_configurada
            ? "Senha SMTP cadastrada. Preencha somente para alterar"
            : "Senha SMTP";
    }
    if (senhaStatus) {
        senhaStatus.textContent = configuracao.smtp_senha_configurada
            ? "Senha SMTP salva com sucesso. Preencha o campo somente se quiser trocar a credencial."
            : "Se estiver usando Gmail, utilize senha de app. O sistema normaliza automaticamente quando ela vier com espacos.";
    }
}

function preencherTesteEmailOperacional(configuracao) {
    const remetente = configuracao.email_remetente || "";
    if (!document.getElementById("email-operacional-teste-destinatario")?.value) {
        setValue("email-operacional-teste-destinatario", remetente);
    }
    if (!document.getElementById("email-operacional-teste-assunto")?.value) {
        setValue("email-operacional-teste-assunto", "Teste de email operacional");
    }
    if (!document.getElementById("email-operacional-teste-conteudo")?.value) {
        setValue(
            "email-operacional-teste-conteudo",
            "Mensagem de teste enviada pelo modulo operacional de estoque."
        );
    }
}

function coletarPayloadEmailOperacional() {
    const payload = {
        email_habilitado: document.getElementById("email-operacional-habilitado")?.checked,
        email_remetente_nome: (document.getElementById("email-operacional-remetente-nome")?.value || "").trim(),
        email_remetente: (document.getElementById("email-operacional-remetente")?.value || "").trim(),
        smtp_host: (document.getElementById("email-operacional-smtp-host")?.value || "").trim(),
        smtp_port: document.getElementById("email-operacional-smtp-port")?.value || "587",
        smtp_usuario: (document.getElementById("email-operacional-smtp-usuario")?.value || "").trim(),
        smtp_tls: document.getElementById("email-operacional-smtp-tls")?.checked,
        smtp_ssl: document.getElementById("email-operacional-smtp-ssl")?.checked,
    };

    const smtpSenha = (document.getElementById("email-operacional-smtp-senha")?.value || "").trim();
    if (smtpSenha) {
        payload.smtp_senha = smtpSenha;
    }

    return payload;
}

function atualizarMotivos() {
    const tipo = document.getElementById("movimento-tipo_movimento")?.value || "ENTRADA";
    const select = document.getElementById("movimento-motivo");
    if (!select) return;

    const motivos = estoquePage.auxiliares.motivos?.[tipo] || [];
    const current = select.value;
    select.innerHTML = "";

    motivos.forEach((motivo) => {
        const option = document.createElement("option");
        option.value = motivo;
        option.textContent = formatMotivo(motivo);
        if (motivo === current) {
            option.selected = true;
        }
        select.appendChild(option);
    });

    if (!select.value && motivos.length) {
        select.value = motivos[0];
    }
}

function atualizarProdutosModal() {
    const empresaId = document.getElementById("movimento-empresa_id")?.value || "";
    const select = document.getElementById("movimento-produto_empresa_id");
    if (!select) return;

    const produtos = (estoquePage.auxiliares.produtos || []).filter((item) => {
        if (!empresaId) return false;
        return String(item.empresa_id) === String(empresaId);
    });

    select.innerHTML = `<option value="">Selecione</option>`;

    produtos.forEach((produto) => {
        const option = document.createElement("option");
        option.value = produto.id;
        option.textContent = `${produto.nome} • saldo ${formatInteger(itemToInteger(produto.estoque_atual))}`;
        select.appendChild(option);
    });

    atualizarHintProduto();
}

function atualizarHintProduto() {
    const produtoEmpresaId = document.getElementById("movimento-produto_empresa_id")?.value || "";
    const hintProduto = document.getElementById("hint-produto");
    const hintEstoque = document.getElementById("hint-estoque");
    const hintMinimo = document.getElementById("hint-minimo");

    const item = (estoquePage.auxiliares.produtos || []).find((produto) => String(produto.id) === String(produtoEmpresaId));

    if (!item) {
        if (hintProduto) hintProduto.textContent = "Nenhum produto selecionado.";
        if (hintEstoque) hintEstoque.textContent = "0";
        if (hintMinimo) hintMinimo.textContent = "0";
        return;
    }

    if (hintProduto) {
        hintProduto.textContent = `${item.nome} • ${item.empresa_nome}`;
    }
    if (hintEstoque) {
        hintEstoque.textContent = formatInteger(item.estoque_atual);
    }
    if (hintMinimo) {
        hintMinimo.textContent = formatInteger(item.estoque_minimo);
    }
}

function atualizarKpis() {
    const totalProdutos = estoquePage.saldos.length;
    const abaixoMinimo = estoquePage.saldos.filter((item) => item.abaixo_minimo).length;
    const quantidadeTotal = estoquePage.saldos.reduce((sum, item) => sum + itemToInteger(item.estoque_atual), 0);
    const resumoNotificacoes = estoquePage.notificacoes?.resumo || {};

    setText("kpi-total-produtos", String(totalProdutos));
    setText("kpi-abaixo-minimo", String(abaixoMinimo));
    setText("kpi-quantidade-total", formatInteger(quantidadeTotal));
    setText("kpi-proximo-vencimento", String(resumoNotificacoes.proximos_vencimento || 0));
    setText("kpi-vencidos", String(resumoNotificacoes.vencidos || 0));
    setText("kpi-movimentos", String(estoquePage.movimentos.length));
}

function preencherFormularioConfiguracaoAlerta() {
    const config = estoquePage.configuracaoAlerta;
    if (!config) return;

    setChecked("alert-popup-ao-entrar", config.popup_ao_entrar);
    setChecked("alert-resumo-diario", config.resumo_diario);
    setChecked("alert-estoque-baixo", config.alertar_estoque_baixo);
    setChecked("alert-sem-estoque", config.alertar_sem_estoque);
    setChecked("alert-validade", config.alertar_validade);
    setChecked("alert-email-habilitado", config.email_habilitado);
    setChecked("alert-whatsapp-habilitado", config.whatsapp_habilitado);
    setValue("alert-dias-vencimento", config.dias_vencimento_alerta);
    setValue("alert-email-destinatarios", config.email_destinatarios || "");
    setValue("alert-whatsapp-destinatarios", config.whatsapp_destinatarios || "");
}

function renderTabelaEstoque() {
    const tableBody = document.getElementById("estoque-table-body");
    if (!tableBody) return;

    const termo = (estoquePage.busca || "").toLowerCase().trim();
    const items = estoquePage.saldos.filter((item) => {
        if (!termo) return true;

        return [
            item.nome,
            item.descricao,
            item.categoria_nome,
            item.empresa_nome,
            item.codigo_barras
        ].some((value) => String(value || "").toLowerCase().includes(termo));
    });

    const paginacao = estoquePage.paginacao.saldos;

    if (!items.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="px-5 py-8 text-center text-slate-400">
                    Nenhum produto encontrado para o filtro atual.
                </td>
            </tr>
        `;
        renderPagination("estoque-pagination", paginacao, items.length, () => renderTabelaEstoque());
        return;
    }

    const itensPagina = getPageItems(items, paginacao);

    tableBody.innerHTML = itensPagina.map((item) => {
        const statusBadge = item.abaixo_minimo
            ? `<span class="inline-flex items-center rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-medium text-amber-300">Baixo</span>`
            : `<span class="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-medium text-emerald-300">Saudável</span>`;

        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle">
                    <div class="flex items-start gap-3">
                        <div class="flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                            <i data-lucide="boxes" class="w-4 h-4"></i>
                        </div>
                        <div>
                            <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                            <p class="text-sm text-slate-400">${escapeHtml(item.codigo_barras || "Sem código de barras")}</p>
                        </div>
                    </div>
                </td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(item.categoria_nome || "Sem categoria")}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(item.empresa_nome || "-")}</td>
                <td class="px-5 py-4 align-middle text-right text-white font-semibold">${formatInteger(item.estoque_atual)}</td>
                <td class="px-5 py-4 align-middle text-right text-slate-300">${formatInteger(item.estoque_minimo)}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${formatValidadeEstoque(item.data_validade)}</td>
                <td class="px-5 py-4 align-middle text-right text-slate-300">${formatCurrency(item.valor_compra)}</td>
                <td class="px-5 py-4 align-middle text-right text-slate-300">${formatCurrency(item.valor_venda)}</td>
                <td class="px-5 py-4 align-middle text-center">${statusBadge}</td>
            </tr>
        `;
    }).join("");

    renderPagination("estoque-pagination", paginacao, items.length, () => renderTabelaEstoque());

    if (window.lucide) {
        lucide.createIcons();
    }
}

function renderTabelaMovimentos() {
    const tableBody = document.getElementById("movimento-table-body");
    if (!tableBody) return;

    const paginacao = estoquePage.paginacao.movimentos;

    if (!estoquePage.movimentos.length) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="px-5 py-8 text-center text-slate-400">
                    Nenhuma movimentação encontrada.
                </td>
            </tr>
        `;
        renderPagination("movimento-pagination", paginacao, 0, () => renderTabelaMovimentos());
        return;
    }

    const itensPagina = getPageItems(estoquePage.movimentos, paginacao);

    tableBody.innerHTML = itensPagina.map((item) => {
        const tipoBadge = item.tipo_movimento === "ENTRADA"
            ? `<span class="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-medium text-emerald-300">Entrada</span>`
            : `<span class="inline-flex items-center rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 text-[11px] font-medium text-rose-300">Saída</span>`;

        const origemBadge = item.origem === "PDV"
            ? `<span class="inline-flex items-center rounded-full bg-sky-500/10 border border-sky-500/20 px-2.5 py-1 text-[11px] font-medium text-sky-300">PDV</span>`
            : item.origem === "VALE"
                ? `<span class="inline-flex items-center rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-medium text-amber-300">Vale</span>`
                : `<span class="inline-flex items-center rounded-full bg-slate-700/40 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-300">Manual</span>`;
        const statusOperacao = item.cancelado_em
            ? `<span class="inline-flex items-center rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 text-[11px] font-medium text-amber-300">Cancelado</span>`
            : item.revertido
                ? `<span class="inline-flex items-center rounded-full bg-sky-500/10 border border-sky-500/20 px-2.5 py-1 text-[11px] font-medium text-sky-300">Revertido</span>`
                : `<span class="inline-flex items-center rounded-full bg-slate-700/40 border border-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-300">Ativo</span>`;
        const podeCancelar = movimentoPodeSerCancelado(item);

        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle text-slate-300">${formatDate(item.data_movimento)}</td>
                <td class="px-5 py-4 align-middle">
                    <p class="font-medium text-white">${escapeHtml(item.produto_nome || "-")}</p>
                    <p class="text-xs text-slate-500">${escapeHtml(item.funcionario_nome || "Sem responsável")}</p>
                </td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(item.empresa_nome || "-")}</td>
                <td class="px-5 py-4 align-middle">${origemBadge}</td>
                <td class="px-5 py-4 align-middle">${tipoBadge}</td>
                <td class="px-5 py-4 align-middle text-slate-300">
                    <div class="space-y-1">
                        <p>${escapeHtml(formatMotivo(item.motivo))}</p>
                        <p>${statusOperacao}</p>
                        ${item.motivo_cancelamento ? `<p class="text-xs text-amber-300">${escapeHtml(item.motivo_cancelamento)}</p>` : ""}
                    </div>
                </td>
                <td class="px-5 py-4 align-middle text-right text-white font-semibold">${formatInteger(item.quantidade)}</td>
                <td class="px-5 py-4 align-middle text-right text-slate-300">${item.valor_total ? formatCurrency(item.valor_total) : "-"}</td>
                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center justify-center gap-2">
                        ${podeCancelar ? `
                            <button type="button"
                                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 hover:bg-rose-500/20 transition"
                                onclick="abrirModalCancelamentoMovimento(${item.id})"
                                title="Cancelar movimentacao">
                                <i data-lucide="rotate-ccw" class="w-4 h-4"></i>
                            </button>
                        ` : `<span class="text-xs text-slate-500">-</span>`}
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    renderPagination("movimento-pagination", paginacao, estoquePage.movimentos.length, () => renderTabelaMovimentos());
    if (window.lucide) {
        lucide.createIcons();
    }
}

function movimentoPodeSerCancelado(item) {
    return Boolean(
        window.__uiFlags?.can_cancel_stock_movements
        && item
        && item.origem === "MANUAL"
        && !item.revertido
        && !item.cancelado_em
    );
}

function abrirModalCancelamentoMovimento(movimentoId) {
    estoquePage.movimentoSelecionadoId = movimentoId;
    const campoMotivo = document.getElementById("cancelar-movimento-motivo");
    if (campoMotivo) {
        campoMotivo.value = "";
    }
    abrirModal("modal-cancelar-movimento");
}

function abrirModalMovimentacao() {
    limparFormularioMovimentacao();
    popularEmpresasModal();

    const empresaSelect = document.getElementById("movimento-empresa_id");
    if (empresaSelect && estoquePage.filtroEmpresa) {
        empresaSelect.value = estoquePage.filtroEmpresa;
    }

    atualizarMotivos();
    atualizarProdutosModal();
    abrirModal("modal-movimentacao");
}

function renderNotificacoes() {
    renderResumoAlertas();
    const estoqueContainer = document.getElementById("estoque-alertas-lista");
    const validadeContainer = document.getElementById("estoque-validade-lista");
    const notificacoes = estoquePage.notificacoes || {};

    if (estoqueContainer) {
        const itens = [
            ...(notificacoes.sem_estoque || []).map((item) => ({
                ...item,
                tipo: "Sem estoque",
                classe: "text-rose-300"
            })),
            ...(notificacoes.estoque_baixo || []).map((item) => ({
                ...item,
                tipo: "Baixo estoque",
                classe: "text-amber-300"
            }))
        ].slice(0, 10);

        estoqueContainer.innerHTML = itens.length
            ? itens.map((item) => `
                <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div class="flex items-start justify-between gap-4">
                        <div>
                            <p class="font-medium text-white">${escapeHtml(item.nome || "-")}</p>
                            <p class="text-sm text-slate-400">${escapeHtml(item.empresa_nome || "-")}</p>
                        </div>
                        <span class="text-xs font-semibold ${item.classe}">${item.tipo}</span>
                    </div>
                    <div class="mt-3 flex items-center justify-between gap-3 text-sm text-slate-300">
                        <span>Atual ${formatInteger(item.estoque_atual)}</span>
                        <span>Minimo ${formatInteger(item.estoque_minimo)}</span>
                    </div>
                </article>
            `).join("")
            : `<p class="text-slate-400">Nenhum alerta de estoque no momento.</p>`;
    }

    if (validadeContainer) {
        const itens = [
            ...(notificacoes.vencidos || []).map((item) => ({
                ...item,
                tipo: "Vencido",
                detalhe: `${Math.abs(Number(item.dias_para_vencimento || 0))} dia(s) atras`,
                classe: "text-rose-300"
            })),
            ...(notificacoes.proximos_vencimento || []).map((item) => ({
                ...item,
                tipo: "A vencer",
                detalhe: `${Number(item.dias_para_vencimento || 0)} dia(s)`,
                classe: "text-sky-300"
            }))
        ].slice(0, 10);

        validadeContainer.innerHTML = itens.length
            ? itens.map((item) => `
                <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <div class="flex items-start justify-between gap-4">
                        <div>
                            <p class="font-medium text-white">${escapeHtml(item.nome || "-")}</p>
                            <p class="text-sm text-slate-400">${escapeHtml(item.empresa_nome || "-")}</p>
                        </div>
                        <span class="text-xs font-semibold ${item.classe}">${item.tipo}</span>
                    </div>
                    <div class="mt-3 flex items-center justify-between gap-3 text-sm text-slate-300">
                        <span>${formatValidadeEstoque(item.data_validade)}</span>
                        <span>${item.detalhe}</span>
                    </div>
                </article>
            `).join("")
            : `<p class="text-slate-400">Nenhum alerta de validade no momento.</p>`;
    }

    renderDestaquesAlerta(notificacoes);
}

function renderResumoAlertas() {
    const container = document.getElementById("estoque-alerta-resumo");
    if (!container) return;

    const resumo = estoquePage.notificacoes?.resumo || {};
    const cards = [
        { label: "Baixo", value: resumo.estoque_baixo || 0, tone: "text-amber-300" },
        { label: "Sem saldo", value: resumo.sem_estoque || 0, tone: "text-rose-300" },
        { label: "Vencidos", value: resumo.vencidos || 0, tone: "text-rose-300" },
        { label: "A vencer", value: resumo.proximos_vencimento || 0, tone: "text-sky-300" }
    ];

    container.innerHTML = cards.map((card) => `
        <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.14em] text-slate-500">${card.label}</p>
            <strong class="block mt-2 text-2xl ${card.tone}">${formatInteger(card.value)}</strong>
        </article>
    `).join("");
}

function renderDestaquesAlerta(notificacoes) {
    const container = document.getElementById("estoque-alerta-destaques");
    if (!container) return;

    const itens = [
        ...(notificacoes.sem_estoque || []).slice(0, 2).map((item) => ({
            ...item,
            titulo: "Sem estoque",
            detalhe: `Atual ${formatInteger(item.estoque_atual)} / minimo ${formatInteger(item.estoque_minimo)}`
        })),
        ...(notificacoes.estoque_baixo || []).slice(0, 2).map((item) => ({
            ...item,
            titulo: "Baixo estoque",
            detalhe: `Atual ${formatInteger(item.estoque_atual)} / minimo ${formatInteger(item.estoque_minimo)}`
        })),
        ...(notificacoes.vencidos || []).slice(0, 1).map((item) => ({
            ...item,
            titulo: "Produto vencido",
            detalhe: formatValidadeEstoque(item.data_validade)
        })),
        ...(notificacoes.proximos_vencimento || []).slice(0, 1).map((item) => ({
            ...item,
            titulo: "Validade proxima",
            detalhe: formatValidadeEstoque(item.data_validade)
        }))
    ].slice(0, 4);

    container.innerHTML = itens.length
        ? itens.map((item) => `
            <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <p class="font-semibold text-white">${escapeHtml(item.nome || "-")}</p>
                        <p class="text-sm text-slate-400">${escapeHtml(item.empresa_nome || "-")}</p>
                    </div>
                    <span class="text-xs uppercase tracking-[0.14em] text-sky-300">${escapeHtml(item.titulo || "Alerta")}</span>
                </div>
                <p class="text-sm text-slate-300 mt-3">${escapeHtml(item.detalhe || "-")}</p>
            </article>
        `).join("")
        : `<p class="text-slate-400">Nenhum alerta prioritario no momento.</p>`;
}

function renderMaisVendidos() {
    const container = document.getElementById("estoque-best-sellers-list");
    if (!container) return;

    const itens = estoquePage.maisVendidos?.itens || [];
    if (!itens.length) {
        container.innerHTML = `<p class="text-slate-400">Nenhuma venda encontrada para o filtro informado.</p>`;
        return;
    }

    container.innerHTML = itens.map((item, index) => `
        <article class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div class="flex items-start justify-between gap-4">
                <div>
                    <p class="font-semibold text-white">${index + 1}. ${escapeHtml(item.produto_nome || "-")}</p>
                    <p class="text-sm text-slate-400">${escapeHtml(item.empresa_nome || "-")}</p>
                </div>
                <span class="text-xs uppercase tracking-[0.14em] text-sky-300">${formatInteger(item.quantidade)} un.</span>
            </div>
            <div class="mt-3 flex items-center justify-between gap-3 text-sm text-slate-300">
                <span>Faturamento</span>
                <strong class="text-white">${formatCurrency(item.faturamento)}</strong>
            </div>
        </article>
    `).join("");
}

function limparFormularioMovimentacao() {
    const form = document.getElementById("form-movimentacao");
    if (form) form.reset();

    const tipo = document.getElementById("movimento-tipo_movimento");
    const quantidade = document.getElementById("movimento-quantidade");
    const valorUnitario = document.getElementById("movimento-valor_unitario");

    if (tipo) tipo.value = "ENTRADA";
    if (quantidade) quantidade.value = "0";
    if (valorUnitario) valorUnitario.value = "";

    atualizarMotivos();
    atualizarProdutosModal();
}

function toggleBestSellerDateFilters() {
    const periodo = document.getElementById("estoque-best-sellers-periodo")?.value || "mes";
    const dataInicio = document.getElementById("estoque-best-sellers-data-inicio");
    const dataFim = document.getElementById("estoque-best-sellers-data-fim");
    const disabled = periodo !== "periodo";

    [dataInicio, dataFim].filter(Boolean).forEach((field) => {
        field.disabled = disabled;
        field.classList.toggle("opacity-60", disabled);
    });
}

function normalizarPayloadMovimentacao() {
    return {
        tipo_movimento: document.getElementById("movimento-tipo_movimento")?.value || "",
        motivo: document.getElementById("movimento-motivo")?.value || "",
        empresa_id: document.getElementById("movimento-empresa_id")?.value || "",
        produto_empresa_id: document.getElementById("movimento-produto_empresa_id")?.value || "",
        quantidade: normalizeIntegerForApi(document.getElementById("movimento-quantidade")?.value || "0"),
        valor_unitario: normalizeOptionalDecimalForApi(document.getElementById("movimento-valor_unitario")?.value || "", 2),
        observacao: (document.getElementById("movimento-observacao")?.value || "").trim()
    };
}

function bindDecimalMask(inputId, decimals) {
    const input = document.getElementById(inputId);
    if (!input) return;

    window.DecimalInput?.bind(input, {
        decimals,
        allowEmpty: true
    });
}

function bindIntegerMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input || input.dataset.maskBound === "true") return;

    input.dataset.maskBound = "true";
    input.addEventListener("input", () => {
        input.value = formatInteger(itemToInteger(input.value));
    });
    input.addEventListener("blur", () => {
        input.value = String(itemToInteger(input.value));
    });
}

function requestJson(url, options = {}) {
    return fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            ...getAuthHeaders(false),
            ...(options.headers || {})
        }
    }).then(async (response) => {
        let result;
        try {
            result = await response.json();
        } catch {
            result = { success: false, message: "Resposta inválida do servidor." };
        }

        if (!response.ok || result.success === false) {
            throw new Error(result.message || "Erro na requisição.");
        }

        return result;
    });
}

function getAuthHeaders(isJson = false) {
    const token = localStorage.getItem("token");
    const headers = {};

    if (isJson) {
        headers["Content-Type"] = "application/json";
    }

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    return headers;
}

function bindModalClose() {
    document.addEventListener("click", (event) => {
        const closeTrigger = event.target.closest("[data-close-modal]");
        if (!closeTrigger) return;

        const modalId = closeTrigger.getAttribute("data-close-modal");
        if (modalId) {
            fecharModal(modalId);
        }
    });

    window.addEventListener("click", (event) => {
        if (event.target.classList.contains("modal-overlay")) {
            event.target.classList.add("hidden");
        }
    });
}

function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove("hidden");
}

function fecharModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add("hidden");
}

function showMessage(message, type = "success") {
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

function normalizeDecimalForApi(value, decimals = 2) {
    return parseDecimal(value).toFixed(decimals);
}

function normalizeOptionalDecimalForApi(value, decimals = 2) {
    if (!String(value || "").trim()) {
        return "";
    }
    return normalizeDecimalForApi(value, decimals);
}

function normalizeIntegerForApi(value) {
    return String(itemToInteger(value));
}

function parseDecimal(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function formatDecimalFromDigits(value, decimals = 2) {
    const digits = String(value ?? "").replace(/\D/g, "");

    if (!digits) {
        return decimals === 3 ? "0,000" : "";
    }

    const numericValue = Number(digits) / (10 ** decimals);
    return formatNumber(numericValue, decimals);
}

function formatNumber(value, decimals = 3) {
    const parsed = Number(String(value ?? 0).replace(",", "."));
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatInteger(value) {
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(itemToInteger(value));
}

function formatCurrency(value) {
    const parsed = Number(String(value ?? 0).replace(",", "."));
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatDate(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";

    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short"
    }).format(date);
}

function formatValidadeEstoque(value) {
    if (!value) return "Sem validade";
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return "Sem validade";
    return new Intl.DateTimeFormat("pt-BR").format(date);
}

function formatMotivo(value) {
    const mapa = {
        COMPRA: "Compra",
        VENDA: "Venda",
        AJUSTE: "Ajuste",
        PERDA: "Perda",
        DEVOLUCAO: "Devolução",
        TRANSFERENCIA: "Transferência"
    };

    return mapa[value] || value || "-";
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function setValue(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.value = value ?? "";
    }
}

function setChecked(id, checked) {
    const element = document.getElementById(id);
    if (element) {
        element.checked = Boolean(checked);
    }
}

function itemToInteger(value) {
    if (typeof value === "number" && Number.isInteger(value)) {
        return value;
    }

    const digits = String(value ?? "").replace(/\D/g, "");
    if (!digits) return 0;

    const parsed = Number.parseInt(digits, 10);
    return Number.isNaN(parsed) ? 0 : parsed;
}

function getPageItems(items, paginacao) {
    const totalPaginas = Math.max(Math.ceil(items.length / paginacao.porPagina), 1);
    if (paginacao.paginaAtual > totalPaginas) {
        paginacao.paginaAtual = totalPaginas;
    }

    const inicio = (paginacao.paginaAtual - 1) * paginacao.porPagina;
    return items.slice(inicio, inicio + paginacao.porPagina);
}

function renderPagination(containerId, paginacao, totalItens, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const totalPaginas = Math.max(Math.ceil(totalItens / paginacao.porPagina), 1);

    if (!totalItens || totalPaginas <= 1) {
        container.innerHTML = totalItens
            ? `<div class="pagination-summary px-5 py-4">Exibindo ${totalItens} registro(s).</div>`
            : "";
        return;
    }

    const inicio = ((paginacao.paginaAtual - 1) * paginacao.porPagina) + 1;
    const fim = Math.min(paginacao.paginaAtual * paginacao.porPagina, totalItens);
    const paginas = buildPageNumbers(paginacao.paginaAtual, totalPaginas);

    container.innerHTML = `
        <div class="pagination-shell">
            <div class="pagination-summary">Exibindo ${inicio}-${fim} de ${totalItens} registros</div>
            <div class="pagination-controls">
                <button type="button" class="pagination-btn" data-page="${paginacao.paginaAtual - 1}" ${paginacao.paginaAtual === 1 ? "disabled" : ""}>Anterior</button>
                ${paginas.map((pagina) => pagina === "..."
                    ? `<span class="pagination-ellipsis">...</span>`
                    : `<button type="button" class="pagination-btn ${pagina === paginacao.paginaAtual ? "pagination-btn-active" : ""}" data-page="${pagina}">${pagina}</button>`
                ).join("")}
                <button type="button" class="pagination-btn" data-page="${paginacao.paginaAtual + 1}" ${paginacao.paginaAtual === totalPaginas ? "disabled" : ""}>Próxima</button>
            </div>
        </div>
    `;

    container.querySelectorAll("[data-page]").forEach((button) => {
        button.addEventListener("click", () => {
            const pagina = Number(button.getAttribute("data-page"));
            if (!Number.isInteger(pagina)) return;
            paginacao.paginaAtual = Math.min(Math.max(pagina, 1), totalPaginas);
            onChange();
        });
    });
}

function buildPageNumbers(paginaAtual, totalPaginas) {
    if (totalPaginas <= 7) {
        return Array.from({ length: totalPaginas }, (_, index) => index + 1);
    }

    if (paginaAtual <= 4) {
        return [1, 2, 3, 4, 5, "...", totalPaginas];
    }

    if (paginaAtual >= totalPaginas - 3) {
        return [1, "...", totalPaginas - 4, totalPaginas - 3, totalPaginas - 2, totalPaginas - 1, totalPaginas];
    }

    return [1, "...", paginaAtual - 1, paginaAtual, paginaAtual + 1, "...", totalPaginas];
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
