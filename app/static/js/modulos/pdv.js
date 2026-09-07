window.pdvPage = {
    auxiliares: { empresas: [], formas_pagamento: [], cupons: [] },
    produtos: [],
    catalogoPorId: {},
    catalogoPorCodigoBarras: {},
    vendas: [],
    carrinho: [],
    pagamentos: [],
    empresaId: "",
    clienteId: "",
    busca: "",
    statusVenda: "",
    vendaSelecionada: null,
    payloadConfirmacaoPendente: null,
    ultimaVendaFinalizada: null,
    pagamentoConfirmado: false,
    pagamentoConfirmadoTotal: null,
    paymentCounter: 1,
    empresaConfiguracaoAtual: null,
    cashbackAtivadoNaVenda: true,
    modalidadePreco: "AUTOMATICO",
    paginacao: {
        produtos: { paginaAtual: 1, porPagina: 10 },
        vendas: { paginaAtual: 1, porPagina: 10 }
    }
};

document.addEventListener("DOMContentLoaded", async () => {
    bindModalClose();
    bindPdvFilters();
    bindCartActions();
    bindSaleActions();
    bindTopActions();
    bindCloseoutActions();
    bindMoneyMask("pdv-desconto-manual");
    bindMoneyMask("pdv-cashback-utilizado");
    bindMoneyMask("pdv-closeout-inicial");
    bindMoneyMask("pdv-closeout-final");

    await carregarAuxiliares();

    if (pdvPage.auxiliares.empresas.length === 1) {
        pdvPage.empresaId = String(pdvPage.auxiliares.empresas[0].id);
    }

    popularEmpresas();
    resetPayments();
    await carregarDadosPdv();
    if (pdvPage.empresaId) {
        document.getElementById("pdv-barcode-input")?.focus();
    }

    if (window.lucide) {
        lucide.createIcons();
    }
});

async function carregarAuxiliares() {
    const result = await requestJson("/api/pdv/auxiliares", { method: "GET" });
    pdvPage.auxiliares = result.data || pdvPage.auxiliares;
    const descontoInput = document.getElementById("pdv-desconto-manual");
    if (descontoInput) {
        descontoInput.disabled = !pdvPage.auxiliares.limite_desconto_percentual;
        descontoInput.title = `Autorizacao de desconto: ${pdvPage.auxiliares.limite_desconto_percentual || 0}%`;
    }
}

async function carregarDadosPdv() {
    await Promise.all([carregarProdutos(), carregarVendas()]);
}

async function carregarProdutos() {
    if (!pdvPage.empresaId) {
        pdvPage.produtos = [];
        limparCatalogoPdv();
        renderProdutos();
        atualizarKpis();
        return;
    }

    const url = new URL("/api/pdv/produtos", window.location.origin);
    url.searchParams.set("empresa_id", pdvPage.empresaId);
    if (pdvPage.busca) {
        url.searchParams.set("busca", pdvPage.busca);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    pdvPage.produtos = Array.isArray(result.data) ? result.data : [];
    reindexarCatalogoPdv(pdvPage.produtos);
    renderProdutos();
    atualizarKpis();
}

async function carregarVendas() {
    const url = new URL("/api/pdv/vendas", window.location.origin);
    url.searchParams.set("limite", "500");
    if (pdvPage.empresaId) {
        url.searchParams.set("empresa_id", pdvPage.empresaId);
    }
    if (pdvPage.statusVenda) {
        url.searchParams.set("status", pdvPage.statusVenda);
    }

    const result = await requestJson(url.toString(), { method: "GET" });
    pdvPage.vendas = Array.isArray(result.data) ? result.data : [];
    renderVendas();
    atualizarKpis();
}

function bindPdvFilters() {
    const empresaSelect = document.getElementById("pdv-empresa");
    const clienteSelect = document.getElementById("pdv-cliente");
    const buscaInput = document.getElementById("pdv-busca");
    const cashbackInput = document.getElementById("pdv-cashback-utilizado");
    const cashbackToggle = document.getElementById("pdv-cashback-ativado");
    const modalidadePrecoSelect = document.getElementById("pdv-modalidade-preco");
    const barcodeInput = document.getElementById("pdv-barcode-input");
    const barcodeSubmit = document.getElementById("pdv-barcode-submit");
    const statusSelect = document.getElementById("pdv-status-venda");

    if (empresaSelect) {
        empresaSelect.addEventListener("change", async () => {
            pdvPage.empresaId = empresaSelect.value || "";
            pdvPage.paginacao.produtos.paginaAtual = 1;
            pdvPage.paginacao.vendas.paginaAtual = 1;
            limparCatalogoPdv();
            limparCarrinho();
            limparBarcodeField();
            popularEmpresas();
            popularClientesPdv();
            await carregarDadosPdv();
            document.getElementById("pdv-barcode-input")?.focus();
        });
    }

    if (clienteSelect) {
        clienteSelect.addEventListener("change", () => {
            pdvPage.clienteId = clienteSelect.value || "";
            if (!pdvPage.clienteId) {
                const input = document.getElementById("pdv-cashback-utilizado");
                if (input) {
                    input.value = "0,00";
                }
            }
            marcarPagamentoPendente();
            atualizarResumoClientePdv();
            atualizarResumoVenda();
        });
    }

    if (buscaInput) {
        buscaInput.addEventListener("input", async () => {
            pdvPage.busca = buscaInput.value || "";
            pdvPage.paginacao.produtos.paginaAtual = 1;
            await carregarProdutos();
        });
    }

    if (barcodeInput) {
        barcodeInput.addEventListener("keydown", async (event) => {
            if (event.key !== "Enter") return;
            event.preventDefault();
            await adicionarProdutoPorCodigoDeBarras();
        });
    }

    if (barcodeSubmit) {
        barcodeSubmit.addEventListener("click", async () => {
            await adicionarProdutoPorCodigoDeBarras();
        });
    }

    if (statusSelect) {
        statusSelect.addEventListener("change", async () => {
            pdvPage.statusVenda = statusSelect.value || "";
            pdvPage.paginacao.vendas.paginaAtual = 1;
            await carregarVendas();
        });
    }

    if (modalidadePrecoSelect) {
        modalidadePrecoSelect.value = pdvPage.modalidadePreco;
        modalidadePrecoSelect.addEventListener("change", () => {
            pdvPage.modalidadePreco = modalidadePrecoSelect.value || "AUTOMATICO";
            marcarPagamentoPendente();
            recalcularPrecosCarrinho();
            renderCarrinho();
            atualizarResumoModalidadePreco();
        });
    }

    if (cashbackInput) {
        cashbackInput.addEventListener("input", () => {
            marcarPagamentoPendente();
            atualizarResumoClientePdv();
            atualizarResumoVenda();
        });
        cashbackInput.addEventListener("blur", () => {
            cashbackInput.value = formatCurrencyInput(obterCashbackAplicado(obterBaseTotalAntesDoCashback()));
            atualizarResumoClientePdv();
            atualizarResumoVenda();
        });
    }

    if (cashbackToggle) {
        cashbackToggle.addEventListener("change", () => {
            pdvPage.cashbackAtivadoNaVenda = Boolean(cashbackToggle.checked);
            if (!pdvPage.cashbackAtivadoNaVenda && cashbackInput) {
                cashbackInput.value = "0,00";
            }
            marcarPagamentoPendente();
            atualizarResumoClientePdv();
            atualizarResumoVenda();
        });
    }
}

function bindCartActions() {
    const clearCartBtn = document.getElementById("pdv-clear-cart");
    const addPaymentBtn = document.getElementById("pdv-add-payment");
    const cupomInput = document.getElementById("pdv-cupom-codigo");
    const openPaymentStepBtn = document.getElementById("pdv-open-payment-modal");

    if (clearCartBtn) {
        clearCartBtn.addEventListener("click", () => {
            limparCarrinho();
            showMessage("Carrinho limpo.", "success");
        });
    }

    if (addPaymentBtn) {
        addPaymentBtn.addEventListener("click", () => {
            pdvPage.pagamentos.push(criarPagamentoVazio());
            marcarPagamentoPendente();
            renderPayments();
        });
    }

    if (cupomInput) {
        cupomInput.addEventListener("input", () => atualizarResumoVenda());
    }

    if (openPaymentStepBtn) {
        openPaymentStepBtn.addEventListener("click", () => {
            renderPayments();
            abrirModal("pdv-payments-modal");
        });
    }
}

function bindSaleActions() {
    const finalizeBtn = document.getElementById("pdv-finalizar-venda");
    const cancelBtn = document.getElementById("pdv-sale-cancel-button");
    const salePrintBtn = document.getElementById("pdv-sale-print-button");
    const confirmSubmitBtn = document.getElementById("pdv-confirm-submit");
    const successPrintBtn = document.getElementById("pdv-success-print");
    const successFiscalBtn = document.getElementById("pdv-success-fiscal");
    const confirmPaymentBtn = document.getElementById("pdv-confirm-payment-modal");

    if (finalizeBtn) {
        finalizeBtn.addEventListener("click", () => {
            try {
                if (!pagamentoEstaConfirmadoParaTotalAtual()) {
                    abrirModal("pdv-payments-modal");
                    throw new Error("Confirme o pagamento antes de finalizar a venda.");
                }

                const payload = montarPayloadVenda();
                pdvPage.payloadConfirmacaoPendente = { ...payload, idempotency_key: crypto.randomUUID() };
                abrirModalConfirmacaoVenda(payload);
            } catch (error) {
                showMessage(error.message || "Erro ao registrar a venda.", "error");
            }
        });
    }

    if (cancelBtn) {
        cancelBtn.addEventListener("click", async () => {
            if (!pdvPage.vendaSelecionada || !pdvPage.vendaSelecionada.permite_cancelamento) {
                return;
            }

            try {
                const motivo = (document.getElementById("pdv-sale-cancel-reason")?.value || "").trim();
                const result = await requestJson(`/api/pdv/vendas/${pdvPage.vendaSelecionada.id}/cancelar`, {
                    method: "POST",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify({ motivo })
                });

                showMessage(result.message || "Venda cancelada com sucesso.", "success");
                fecharModal("pdv-sale-modal");
                pdvPage.vendaSelecionada = null;
                await carregarDadosPdv();
            } catch (error) {
                showMessage(error.message || "Erro ao cancelar a venda.", "error");
            }
        });
    }

    if (salePrintBtn) {
        salePrintBtn.addEventListener("click", () => {
            if (!pdvPage.vendaSelecionada) return;
            abrirComprovanteVenda(pdvPage.vendaSelecionada.id);
        });
    }

    if (confirmSubmitBtn) {
        confirmSubmitBtn.addEventListener("click", async () => {
            if (!pdvPage.payloadConfirmacaoPendente) return;

            try {
                confirmSubmitBtn.disabled = true;
                const result = await requestJson("/api/pdv/vendas", {
                    method: "POST",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(pdvPage.payloadConfirmacaoPendente)
                });

                pdvPage.ultimaVendaFinalizada = result.data || null;
                pdvPage.payloadConfirmacaoPendente = null;
                fecharModal("pdv-confirm-modal");
                abrirModalSucessoVenda(pdvPage.ultimaVendaFinalizada);
                const emailVenda = result.data?.email_venda || null;
                let mensagemSucesso = result.message || "Venda registrada com sucesso.";
                if (emailVenda?.status === "ENVIADO") {
                    mensagemSucesso = `${mensagemSucesso} Email da venda enviado ao cliente.`;
                } else if (emailVenda?.status === "ERRO") {
                    mensagemSucesso = `${mensagemSucesso} O email automatico nao foi enviado: ${emailVenda.erro || "falha na comunicacao SMTP."}`;
                }
                showMessage(mensagemSucesso, "success");
                limparCarrinho();
                await carregarDadosPdv();
            } catch (error) {
                showMessage(error.message || "Erro ao registrar a venda.", "error");
            } finally {
                confirmSubmitBtn.disabled = false;
            }
        });
    }

    if (successPrintBtn) {
        successPrintBtn.addEventListener("click", () => {
            if (!pdvPage.ultimaVendaFinalizada?.id) return;
            abrirComprovanteVenda(pdvPage.ultimaVendaFinalizada.id);
        });
    }

    if (successFiscalBtn) {
        successFiscalBtn.addEventListener("click", async () => {
            if (!pdvPage.ultimaVendaFinalizada?.id) return;
            await emitirNotaFiscalPdv(pdvPage.ultimaVendaFinalizada.id);
        });
    }

    if (confirmPaymentBtn) {
        confirmPaymentBtn.addEventListener("click", () => {
            try {
                confirmarPagamentoAtual();
                showMessage("Pagamento confirmado para esta venda.", "success");
            } catch (error) {
                showMessage(error.message || "Erro ao confirmar pagamento.", "error");
            }
        });
    }
}

function popularEmpresas() {
    const empresaSelect = document.getElementById("pdv-empresa");
    const closeoutSelect = document.getElementById("pdv-closeout-empresa");
    if (empresaSelect) {
        empresaSelect.innerHTML = `<option value="">Selecione a empresa</option>`;
        pdvPage.auxiliares.empresas.forEach((empresa) => {
            const option = document.createElement("option");
            option.value = empresa.id;
            option.textContent = empresa.nome;
            option.selected = String(empresa.id) === String(pdvPage.empresaId);
            empresaSelect.appendChild(option);
        });
    }

    if (closeoutSelect) {
        closeoutSelect.innerHTML = `<option value="">Selecione a empresa</option>`;
        pdvPage.auxiliares.empresas.forEach((empresa) => {
            const option = document.createElement("option");
            option.value = empresa.id;
            option.textContent = empresa.nome;
            option.selected = String(empresa.id) === String(pdvPage.empresaId);
            closeoutSelect.appendChild(option);
        });
    }

    const empresaInfo = document.getElementById("pdv-info-empresa");
    const empresaAtual = pdvPage.auxiliares.empresas.find((item) => String(item.id) === String(pdvPage.empresaId));
    pdvPage.empresaConfiguracaoAtual = empresaAtual?.configuracao_cliente || null;
    pdvPage.cashbackAtivadoNaVenda = cashbackPodeSerOperadoNaVenda();
    sincronizarToggleCashbackVenda();
    if (empresaInfo) {
        empresaInfo.textContent = empresaAtual
            ? `Caixa pronto para atendimento em ${empresaAtual.nome}.`
            : "Escolha a empresa para liberar os produtos no caixa.";
    }

    setBarcodeFeedback(
        empresaAtual
            ? "Leitor pronto. Bip e Enter adicionam o item direto no carrinho."
            : "Selecione a empresa para habilitar a leitura por codigo de barras.",
        empresaAtual ? "info" : "muted"
    );

    popularClientesPdv();
    atualizarResumoClientePdv();
    atualizarResumoModalidadePreco();
}

function popularClientesPdv() {
    const select = document.getElementById("pdv-cliente");
    if (!select) return;

    const currentValue = pdvPage.clienteId || "";
    select.innerHTML = `
        <option value="">Venda sem cliente vinculado</option>
        ${(pdvPage.auxiliares.clientes || []).map((cliente) => `
            <option value="${cliente.id}" ${String(cliente.id) === String(currentValue) ? "selected" : ""}>
                ${escapeHtml(cliente.nome || "Cliente")} ${cliente.documento ? `- ${escapeHtml(formatDocumentValue(cliente.documento))}` : ""}
            </option>
        `).join("")}
    `;
}

function obterEmpresaAtualPdv() {
    return (pdvPage.auxiliares.empresas || []).find((item) => String(item.id) === String(pdvPage.empresaId)) || null;
}

function obterModalidadePrecoSelecionada() {
    const modalidade = String(pdvPage.modalidadePreco || "AUTOMATICO").toUpperCase();
    if (["AUTOMATICO", "VAREJO", "ATACADO"].includes(modalidade)) {
        return modalidade;
    }
    return "AUTOMATICO";
}

function produtoPossuiPrecoAtacado(produto) {
    const valorAtacado = parseCurrencyValue(produto?.valor_atacado || "0");
    const valorVarejo = parseCurrencyValue(produto?.valor_varejo ?? produto?.valor_venda ?? "0");
    return valorAtacado > 0 && valorAtacado < valorVarejo;
}

function resolverPrecoItem(produto, quantidade) {
    const valorVarejo = parseCurrencyValue(produto?.valor_varejo ?? produto?.valor_venda ?? "0");
    const valorAtacado = parseCurrencyValue(produto?.valor_atacado ?? produto?.valor_venda ?? "0");
    const quantidadeMinimaAtacado = Math.max(Number(produto?.quantidade_minima_atacado || 1), 1);
    const modalidade = obterModalidadePrecoSelecionada();
    const possuiAtacado = produtoPossuiPrecoAtacado(produto);
    const atingiuMinimo = Number(quantidade || 0) >= quantidadeMinimaAtacado;

    if (modalidade === "ATACADO") {
        if (possuiAtacado && atingiuMinimo) {
            return {
                valorUnitario: valorAtacado,
                modalidadeAplicada: "ATACADO",
                atacadoPendente: false,
                atacadoIndisponivel: false,
            };
        }

        return {
            valorUnitario: valorVarejo,
            modalidadeAplicada: "VAREJO",
            atacadoPendente: possuiAtacado && !atingiuMinimo,
            atacadoIndisponivel: !possuiAtacado,
        };
    }

    if (modalidade === "AUTOMATICO" && possuiAtacado && atingiuMinimo) {
        return {
            valorUnitario: valorAtacado,
            modalidadeAplicada: "ATACADO",
            atacadoPendente: false,
            atacadoIndisponivel: false,
        };
    }

    return {
        valorUnitario: valorVarejo,
        modalidadeAplicada: "VAREJO",
        atacadoPendente: false,
        atacadoIndisponivel: false,
    };
}

function atualizarPrecoItemCarrinho(item) {
    if (!item) return;
    const resolucao = resolverPrecoItem(item, item.quantidade);
    item.valor_venda = String(resolucao.valorUnitario.toFixed(2));
    item.modalidade_preco_aplicada = resolucao.modalidadeAplicada;
    item.atacado_pendente = Boolean(resolucao.atacadoPendente);
    item.atacado_indisponivel = Boolean(resolucao.atacadoIndisponivel);
}

function recalcularPrecosCarrinho() {
    pdvPage.carrinho.forEach((item) => atualizarPrecoItemCarrinho(item));
}

function formatModalidadePrecoLabel(value) {
    if (value === "ATACADO") return "Atacado";
    if (value === "VAREJO") return "Varejo";
    return "Automatico";
}

function atualizarResumoModalidadePreco() {
    const feedback = document.getElementById("pdv-modalidade-feedback");
    if (!feedback) return;

    const modalidade = obterModalidadePrecoSelecionada();
    if (modalidade === "ATACADO") {
        const pendentes = pdvPage.carrinho.filter((item) => item.atacado_pendente);
        const indisponiveis = pdvPage.carrinho.filter((item) => item.atacado_indisponivel);

        if (indisponiveis.length) {
            feedback.textContent = "Alguns itens do carrinho nao possuem preco de atacado configurado. O fechamento sera bloqueado ate a regra ser corrigida.";
            return;
        }

        if (pendentes.length) {
            feedback.textContent = "Modo atacado ativo. Alcance a quantidade minima em todos os itens para liberar o fechamento com preco atacado.";
            return;
        }

        feedback.textContent = "Modo atacado ativo. Todos os itens do carrinho estao aptos para preco atacado.";
        return;
    }

    if (modalidade === "VAREJO") {
        feedback.textContent = "Modo varejo ativo. O sistema mantem o preco de balcão em todos os itens.";
        return;
    }

    feedback.textContent = "Modo automatico ativo. O sistema aplica atacado ao atingir a quantidade minima configurada.";
}

function cashbackPodeSerOperadoNaVenda() {
    const configuracao = pdvPage.empresaConfiguracaoAtual || {};
    return Boolean(pdvPage.empresaId && configuracao.cashback_ativo);
}

function cashbackEstaAtivadoNaVenda() {
    return Boolean(pdvPage.cashbackAtivadoNaVenda && cashbackPodeSerOperadoNaVenda());
}

function sincronizarToggleCashbackVenda() {
    const cashbackToggle = document.getElementById("pdv-cashback-ativado");
    if (!cashbackToggle) return;

    const podeOperar = cashbackPodeSerOperadoNaVenda();
    cashbackToggle.disabled = !podeOperar;
    cashbackToggle.checked = Boolean(podeOperar && pdvPage.cashbackAtivadoNaVenda);
}

function obterClienteSelecionadoPdv() {
    return (pdvPage.auxiliares.clientes || []).find((item) => String(item.id) === String(pdvPage.clienteId)) || null;
}

function obterBaseTotalAntesDoCashback() {
    const subtotal = obterSubtotalCarrinho();
    const descontoManual = parseCurrencyValue(document.getElementById("pdv-desconto-manual")?.value || "0");
    const cupom = obterCupomSelecionado();
    const descontoCupom = calcularDescontoCupom(cupom, subtotal);
    const descontoTotal = Math.min(subtotal, descontoManual + descontoCupom);
    return Math.max(subtotal - descontoTotal, 0);
}

function obterCashbackAplicado(baseTotal) {
    const input = document.getElementById("pdv-cashback-utilizado");
    const cliente = obterClienteSelecionadoPdv();
    const configuracao = pdvPage.empresaConfiguracaoAtual || {};
    const saldo = parseCurrencyValue(cliente?.saldo_cashback || "0");
    const informado = parseCurrencyValue(input?.value || "0");
    const minimo = parseCurrencyValue(configuracao.cashback_valor_minimo_resgate || "0");
    const percentualLimite = Math.min(
        Math.max(parseCurrencyValue(configuracao.cashback_percentual_limite_resgate_venda || "100"), 0),
        100
    );

    if (!cliente || !cashbackEstaAtivadoNaVenda()) {
        return 0;
    }

    const base = typeof baseTotal === "number" ? baseTotal : obterBaseTotalAntesDoCashback();
    if (base <= 0) return 0;
    const limitePercentual = base * (percentualLimite / 100);

    let valor = Math.min(informado, saldo, base, limitePercentual);
    if (valor < 0) valor = 0;
    if (valor > 0 && valor < minimo) {
        valor = 0;
    }
    return valor;
}

function atualizarResumoClientePdv() {
    const cliente = obterClienteSelecionadoPdv();
    const configuracao = pdvPage.empresaConfiguracaoAtual || {};
    const feedback = document.getElementById("pdv-cliente-feedback");
    const saldo = document.getElementById("pdv-cliente-saldo");
    const regra = document.getElementById("pdv-cashback-regra");
    const cashbackFeedback = document.getElementById("pdv-cashback-feedback");
    const cashbackInput = document.getElementById("pdv-cashback-utilizado");

    const saldoDisponivel = parseCurrencyValue(cliente?.saldo_cashback || "0");
    const baseTotal = obterBaseTotalAntesDoCashback();
    const cashbackAplicado = obterCashbackAplicado(baseTotal);

    if (saldo) {
        saldo.textContent = formatCurrency(saldoDisponivel);
    }

    if (!cliente) {
        if (feedback) feedback.textContent = "Selecione um cliente para vincular o historico da venda e liberar cashback.";
        if (regra) regra.textContent = "Sem cliente selecionado.";
        if (cashbackFeedback) cashbackFeedback.textContent = "O cashback sera liberado quando houver cliente e empresa configurados.";
        if (cashbackInput) {
            cashbackInput.disabled = true;
            cashbackInput.value = "0,00";
        }
        return;
    }

    if (feedback) {
        feedback.textContent = `${cliente.nome} selecionado. Saldo em carteira disponivel para esta venda.`;
    }

    if (cashbackInput) {
        cashbackInput.disabled = !cashbackEstaAtivadoNaVenda();
    }

    if (!pdvPage.empresaId) {
        if (regra) regra.textContent = "Selecione a empresa para consultar a regra de cashback.";
        if (cashbackFeedback) cashbackFeedback.textContent = "A empresa define percentual, validade e minimo de uso.";
        sincronizarToggleCashbackVenda();
        return;
    }

    if (!configuracao.cashback_ativo) {
        if (regra) regra.textContent = "Cashback desabilitado para esta empresa.";
        if (cashbackFeedback) cashbackFeedback.textContent = "A venda ficara vinculada ao cliente, mas sem uso ou geracao de cashback.";
        if (cashbackInput) {
            cashbackInput.value = "0,00";
        }
        sincronizarToggleCashbackVenda();
        return;
    }

    sincronizarToggleCashbackVenda();

    if (!cashbackEstaAtivadoNaVenda()) {
        if (regra) regra.textContent = "Cashback desativado manualmente para esta venda.";
        if (cashbackFeedback) cashbackFeedback.textContent = "O cliente continua vinculado, mas esta venda nao vai usar nem gerar cashback.";
        if (cashbackInput) {
            cashbackInput.value = "0,00";
        }
        return;
    }

    const minimo = parseCurrencyValue(configuracao.cashback_valor_minimo_resgate || "0");
    const percentualLimite = parseCurrencyValue(configuracao.cashback_percentual_limite_resgate_venda || "100");
    const limiteVenda = obterBaseTotalAntesDoCashback() * (percentualLimite / 100);
    if (regra) {
        regra.textContent = `${configuracao.cashback_percentual || "0.00"}% de retorno, validade ${configuracao.cashback_validade_dias || 30} dias, uso minimo ${formatCurrency(minimo)} e limite de ${formatPercentValue(percentualLimite)} da venda.`;
    }

    if (cashbackFeedback) {
        cashbackFeedback.textContent = cashbackAplicado > 0
            ? `Serao usados ${formatCurrency(cashbackAplicado)} nesta venda. Limite atual: ${formatCurrency(limiteVenda)}.`
            : "Informe um valor dentro do saldo, respeitando o minimo e o limite percentual da venda.";
    }
}

function renderProdutos() {
    const grid = document.getElementById("pdv-produtos-grid");
    const paginacao = pdvPage.paginacao.produtos;
    if (!grid) return;

    if (!pdvPage.empresaId) {
        grid.innerHTML = `
            <article class="pdv-empty-state">
                <i data-lucide="shopping-bag" class="w-8 h-8"></i>
                <p>Selecione uma empresa para iniciar o PDV.</p>
            </article>
        `;
        renderPdvPagination("pdv-produtos-pagination", paginacao, 0, () => renderProdutos());
        if (window.lucide) lucide.createIcons();
        return;
    }

    if (!pdvPage.produtos.length) {
        grid.innerHTML = `
            <article class="pdv-empty-state">
                <i data-lucide="search-x" class="w-8 h-8"></i>
                <p>Nenhum produto encontrado para o filtro atual.</p>
            </article>
        `;
        renderPdvPagination("pdv-produtos-pagination", paginacao, 0, () => renderProdutos());
        if (window.lucide) lucide.createIcons();
        return;
    }

    const itensPagina = getPdvPageItems(pdvPage.produtos, paginacao);
    const podeRegistrarVenda = Boolean(window.__uiFlags?.can_manage_sales);

    grid.innerHTML = itensPagina.map((produto) => {
        const baixoEstoque = Number(produto.estoque_atual) <= Number(produto.estoque_minimo);
        const semEstoque = Number(produto.estoque_atual) <= 0;
        const possuiAtacado = produtoPossuiPrecoAtacado(produto);
        const quantidadeMinimaAtacado = Math.max(Number(produto.quantidade_minima_atacado || 1), 1);
        const botaoDesabilitado = semEstoque || !podeRegistrarVenda;
        const badge = semEstoque
            ? `<span class="pdv-tag pdv-tag-danger">Sem estoque</span>`
            : baixoEstoque
                ? `<span class="pdv-tag pdv-tag-danger">Reposicao urgente</span>`
                : `<span class="pdv-tag pdv-tag-success">Disponivel</span>`;

        return `
            <article class="pdv-product-card">
                <div class="pdv-product-body">
                    <div class="flex items-start justify-between gap-3">
                        <div class="pdv-product-summary">
                            <div>
                                <h3 class="pdv-product-title">${escapeHtml(produto.nome || "-")}</h3>
                                <p class="pdv-product-description">${escapeHtml(produto.descricao || "Sem descricao cadastrada.")}</p>
                            </div>
                            <p class="pdv-product-code">
                                Codigo: ${escapeHtml(produto.codigo_barras || "Nao informado")}
                            </p>
                        </div>
                        ${badge}
                    </div>

                    <div class="pdv-product-meta">
                        <span class="pdv-tag pdv-tag-neutral">${escapeHtml(produto.categoria_nome || "Sem categoria")}</span>
                        <span class="pdv-tag pdv-tag-neutral">Estoque ${formatInteger(produto.estoque_atual)}</span>
                    </div>

                    <div class="pdv-product-footer">
                        <div>
                            <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Tabela de preco</p>
                            <div class="space-y-1">
                                <div class="text-sm text-slate-300">Varejo ${formatCurrency(produto.valor_varejo ?? produto.valor_venda)}</div>
                                <div class="text-sm text-slate-300">
                                    Atacado ${formatCurrency(produto.valor_atacado ?? produto.valor_venda)}
                                    ${possuiAtacado ? `a partir de ${formatInteger(quantidadeMinimaAtacado)} un.` : "(nao configurado)"}
                                </div>
                            </div>
                        </div>

                        <button type="button"
                            class="pdv-product-action inline-flex items-center gap-2 rounded-xl ${botaoDesabilitado ? "bg-slate-800 text-slate-500 cursor-not-allowed" : "bg-sky-500 hover:bg-sky-400 text-slate-950"} font-semibold px-4 py-3 transition"
                            ${botaoDesabilitado ? "disabled" : ""}
                            onclick="adicionarAoCarrinho(${produto.id})">
                            <i data-lucide="plus" class="w-4 h-4"></i>
                            ${podeRegistrarVenda ? "Adicionar" : "Somente leitura"}
                        </button>
                    </div>
                </div>
            </article>
        `;
    }).join("");

    renderPdvPagination("pdv-produtos-pagination", paginacao, pdvPage.produtos.length, () => renderProdutos());

    if (window.lucide) {
        lucide.createIcons();
    }
}

function bindTopActions() {
    const salesBtn = document.getElementById("pdv-open-sales-modal");

    if (salesBtn) {
        salesBtn.addEventListener("click", () => abrirModal("pdv-sales-history-modal"));
    }
}

function bindCloseoutActions() {
    const openCloseoutBtn = document.getElementById("pdv-open-closeout-modal");
    const closeoutForm = document.getElementById("pdv-closeout-form");

    if (openCloseoutBtn) {
        openCloseoutBtn.addEventListener("click", () => {
            resetPdvCloseoutForm();
            abrirModal("pdv-closeout-modal");
        });
    }

    if (closeoutForm) {
        closeoutForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            try {
                const payload = {
                    empresa_id: document.getElementById("pdv-closeout-empresa")?.value || "",
                    data_fechamento: document.getElementById("pdv-closeout-data")?.value || "",
                    valor_inicial: normalizeMoneyForApi(document.getElementById("pdv-closeout-inicial")?.value || "0"),
                    valor_final: normalizeMoneyForApi(document.getElementById("pdv-closeout-final")?.value || "0"),
                    observacao: (document.getElementById("pdv-closeout-observacao")?.value || "").trim()
                };

                const result = await requestJson("/api/financeiro/fechamentos", {
                    method: "POST",
                    headers: getAuthHeaders(true),
                    body: JSON.stringify(payload)
                });

                showMessage(result.message || "Fechamento registrado com sucesso.", "success");
                fecharModal("pdv-closeout-modal");
            } catch (error) {
                showMessage(error.message || "Erro ao registrar o fechamento.", "error");
            }
        });
    }
}

function adicionarAoCarrinho(produtoId) {
    const produto = pdvPage.catalogoPorId[produtoId] || pdvPage.produtos.find((item) => Number(item.id) === Number(produtoId));
    if (!produto) {
        showMessage("Produto nao encontrado.", "error");
        return;
    }

    adicionarProdutoAoCarrinho(produto);
}

function adicionarProdutoAoCarrinho(produto) {
    const produtoId = Number(produto.id);
    const existente = pdvPage.carrinho.find((item) => Number(item.produto_id) === produtoId);
    if (existente) {
        if (existente.quantidade >= Number(produto.estoque_atual)) {
            showMessage("Nao ha estoque suficiente para aumentar a quantidade.", "error");
            return false;
        }
        existente.quantidade += 1;
        atualizarPrecoItemCarrinho(existente);
    } else {
        if (Number(produto.estoque_atual) <= 0) {
            showMessage("Produto sem estoque disponivel.", "error");
            return false;
        }
        const itemCarrinho = {
            produto_id: produtoId,
            nome: produto.nome,
            categoria_nome: produto.categoria_nome,
            valor_varejo: produto.valor_varejo ?? produto.valor_venda,
            valor_atacado: produto.valor_atacado ?? produto.valor_venda,
            quantidade_minima_atacado: Number(produto.quantidade_minima_atacado || 1),
            valor_venda: produto.valor_varejo ?? produto.valor_venda,
            estoque_atual: Number(produto.estoque_atual),
            quantidade: 1
        };
        atualizarPrecoItemCarrinho(itemCarrinho);
        pdvPage.carrinho.push(itemCarrinho);
    }

    marcarPagamentoPendente();
    atualizarResumoModalidadePreco();
    renderCarrinho();
    return true;
}

async function adicionarProdutoPorCodigoDeBarras() {
    if (!window.__uiFlags?.can_manage_sales) {
        showMessage("Seu perfil pode consultar o PDV, mas nao registrar vendas.", "error");
        return;
    }

    const input = document.getElementById("pdv-barcode-input");
    const codigo = normalizeBarcodeValue(input?.value || "");

    if (!pdvPage.empresaId) {
        showMessage("Selecione a empresa antes de usar o leitor.", "error");
        setBarcodeFeedback("Selecione a empresa para habilitar a leitura por codigo de barras.", "error");
        input?.focus();
        return;
    }

    if (!codigo) {
        setBarcodeFeedback("Leia um codigo valido para adicionar ao carrinho.", "muted");
        input?.focus();
        return;
    }

    try {
        setBarcodeFeedback("Buscando item no catalogo do caixa...", "info");
        let produto = pdvPage.catalogoPorCodigoBarras[codigo] || null;

        if (!produto) {
            const url = new URL("/api/pdv/produtos/codigo-barras", window.location.origin);
            url.searchParams.set("empresa_id", pdvPage.empresaId);
            url.searchParams.set("codigo_barras", codigo);
            const result = await requestJson(url.toString(), { method: "GET" });
            produto = result.data || null;
            if (produto) {
                reindexarCatalogoPdv([produto]);
            }
        }

        if (!produto) {
            throw new Error("Produto nao encontrado para o codigo de barras informado.");
        }

        const adicionado = adicionarProdutoAoCarrinho(produto);
        if (!adicionado) {
            setBarcodeFeedback("Produto localizado, mas sem saldo disponivel para nova inclusao.", "error");
            input?.focus();
            return;
        }

        if (input) {
            input.value = "";
            input.focus();
        }
        setBarcodeFeedback(`${produto.nome} adicionado ao carrinho.`, "success");
    } catch (error) {
        setBarcodeFeedback(error.message || "Nao foi possivel localizar o codigo de barras.", "error");
        showMessage(error.message || "Erro ao ler o codigo de barras.", "error");
        input?.focus();
    }
}

function alterarQuantidadeCarrinho(produtoId, delta) {
    const item = pdvPage.carrinho.find((row) => Number(row.produto_id) === Number(produtoId));
    if (!item) return;

    const novaQuantidade = item.quantidade + delta;
    if (novaQuantidade <= 0) {
        removerDoCarrinho(produtoId);
        return;
    }

    if (novaQuantidade > item.estoque_atual) {
        showMessage("Quantidade maior que o estoque disponivel.", "error");
        return;
    }

    item.quantidade = novaQuantidade;
    atualizarPrecoItemCarrinho(item);
    marcarPagamentoPendente();
    atualizarResumoModalidadePreco();
    renderCarrinho();
}

function removerDoCarrinho(produtoId) {
    pdvPage.carrinho = pdvPage.carrinho.filter((item) => Number(item.produto_id) !== Number(produtoId));
    marcarPagamentoPendente();
    atualizarResumoModalidadePreco();
    renderCarrinho();
}

function renderCarrinho() {
    const cartEmpty = document.getElementById("pdv-cart-empty");
    const cartItems = document.getElementById("pdv-cart-items");
    if (!cartEmpty || !cartItems) return;

    if (!pdvPage.carrinho.length) {
        cartEmpty.classList.remove("hidden");
        cartItems.classList.add("hidden");
        cartItems.innerHTML = "";
        resetPayments();
        atualizarResumoVenda();
        atualizarStatusPagamento();
        return;
    }

    cartEmpty.classList.add("hidden");
    cartItems.classList.remove("hidden");
    cartItems.innerHTML = pdvPage.carrinho.map((item) => `
        <article class="pdv-cart-item">
            <div>
                <p class="font-semibold text-white">${escapeHtml(item.nome)}</p>
                <p class="text-sm text-slate-400">${escapeHtml(item.categoria_nome || "Sem categoria")}</p>
                <p class="text-sm text-slate-500 mt-2">
                    ${formatModalidadePrecoLabel(item.modalidade_preco_aplicada)} ${formatCurrency(item.valor_venda)}
                </p>
                ${item.atacado_pendente ? `
                    <p class="text-xs text-amber-300 mt-2">
                        Faltam ${formatInteger(Math.max(Number(item.quantidade_minima_atacado || 1) - Number(item.quantidade || 0), 0))} un. para liberar atacado.
                    </p>
                ` : ""}
                ${item.atacado_indisponivel ? `
                    <p class="text-xs text-rose-300 mt-2">Produto sem preco de atacado configurado.</p>
                ` : ""}
            </div>

            <div class="flex flex-col items-end gap-3">
                <button type="button"
                    class="inline-flex items-center justify-center w-9 h-9 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 hover:bg-rose-500/20 transition"
                    onclick="removerDoCarrinho(${item.produto_id})"
                    title="Remover item">
                    <i data-lucide="trash-2" class="w-4 h-4"></i>
                </button>

                <div class="pdv-cart-qty">
                    <button type="button" class="pdv-icon-btn" aria-label="Diminuir quantidade de ${escapeHtml(item.nome)}" onclick="alterarQuantidadeCarrinho(${item.produto_id}, -1)">
                        <i data-lucide="minus" class="w-4 h-4"></i>
                    </button>
                    <strong class="min-w-[2rem] text-center text-white">${formatInteger(item.quantidade)}</strong>
                    <button type="button" class="pdv-icon-btn" aria-label="Aumentar quantidade de ${escapeHtml(item.nome)}" onclick="alterarQuantidadeCarrinho(${item.produto_id}, 1)">
                        <i data-lucide="plus" class="w-4 h-4"></i>
                    </button>
                </div>

                <strong class="text-white">${formatCurrency(multiplicar(item.valor_venda, item.quantidade))}</strong>
            </div>
        </article>
    `).join("");

    atualizarResumoModalidadePreco();
    atualizarResumoVenda();
    atualizarStatusPagamento();
    if (window.lucide) {
        lucide.createIcons();
    }
}

function renderPayments() {
    const container = document.getElementById("pdv-payment-rows");
    if (!container) return;

    if (!pdvPage.pagamentos.length) {
        pdvPage.pagamentos.push(criarPagamentoVazio());
    }

    container.innerHTML = pdvPage.pagamentos.map((pagamento) => `
        <div class="grid grid-cols-1 md:grid-cols-[minmax(0,1fr)_10rem_3rem] gap-3 items-center">
            <select aria-label="Forma de pagamento" class="pdv-payment-forma w-full bg-slate-950 border border-slate-800 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 rounded-xl px-4 py-3 text-white outline-none transition"
                data-payment-uid="${pagamento.uid}">
                <option value="">Forma de pagamento</option>
                ${pdvPage.auxiliares.formas_pagamento.map((forma) => `
                    <option value="${forma.id}" ${String(forma.id) === String(pagamento.forma_pagamento_id) ? "selected" : ""}>
                        ${escapeHtml(forma.nome)}
                    </option>
                `).join("")}
            </select>

            <input type="text" inputmode="decimal"
                aria-label="Valor do pagamento" class="pdv-payment-valor w-full bg-slate-950 border border-slate-800 focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 rounded-xl px-4 py-3 text-white outline-none transition"
                data-payment-uid="${pagamento.uid}"
                value="${pagamento.valor || ""}"
                placeholder="0,00">

            <button type="button"
                class="inline-flex items-center justify-center w-12 h-12 rounded-xl ${pdvPage.pagamentos.length === 1 ? "bg-slate-800 text-slate-600" : "bg-rose-500/10 border border-rose-500/20 text-rose-300 hover:bg-rose-500/20"} transition"
                ${pdvPage.pagamentos.length === 1 ? "disabled" : ""}
                data-remove-payment="${pagamento.uid}" aria-label="Remover pagamento">
                <i data-lucide="x" class="w-4 h-4"></i>
            </button>
        </div>
    `).join("");

    container.querySelectorAll(".pdv-payment-forma").forEach((select) => {
        select.addEventListener("change", () => {
            const payment = pdvPage.pagamentos.find((item) => String(item.uid) === String(select.dataset.paymentUid));
            if (!payment) return;
            payment.forma_pagamento_id = select.value || "";
            marcarPagamentoPendente();
            renderPaymentSnapshot();
        });
    });

    container.querySelectorAll(".pdv-payment-valor").forEach((input) => {
        bindMoneyMaskToElement(input);
        input.addEventListener("input", () => {
            const payment = pdvPage.pagamentos.find((item) => String(item.uid) === String(input.dataset.paymentUid));
            if (!payment) return;
            payment.valor = input.value;
            payment.touched = true;
            marcarPagamentoPendente();
            renderPaymentSnapshot();
        });
    });

    container.querySelectorAll("[data-remove-payment]").forEach((button) => {
        button.addEventListener("click", () => {
            pdvPage.pagamentos = pdvPage.pagamentos.filter((item) => String(item.uid) !== String(button.dataset.removePayment));
            marcarPagamentoPendente();
            renderPayments();
            atualizarResumoVenda();
        });
    });

    syncSinglePaymentWithTotal();
    renderPaymentSnapshot();

    if (window.lucide) {
        lucide.createIcons();
    }
}

function renderVendas() {
    const body = document.getElementById("pdv-vendas-body");
    const paginacao = pdvPage.paginacao.vendas;
    if (!body) return;

    if (!pdvPage.vendas.length) {
        body.innerHTML = `
            <tr>
                <td colspan="8" class="px-5 py-8 text-center text-slate-400">
                    Nenhuma venda encontrada para o filtro atual.
                </td>
            </tr>
        `;
        renderPdvPagination("pdv-vendas-pagination", paginacao, 0, () => renderVendas());
        return;
    }

    const itensPagina = getPdvPageItems(pdvPage.vendas, paginacao);

    body.innerHTML = itensPagina.map((venda) => {
        const pagamentos = venda.pagamentos.map((item) => item.forma_pagamento_nome).filter(Boolean).join(", ") || "-";
        const statusBadge = venda.status === "FINALIZADA"
            ? `<span class="inline-flex items-center rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1 text-[11px] font-medium text-emerald-300">Finalizada</span>`
            : `<span class="inline-flex items-center rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 text-[11px] font-medium text-rose-300">Cancelada</span>`;
        const podeCancelarVenda = Boolean(window.__uiFlags?.can_cancel_sales) && venda.permite_cancelamento;

        return `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle">
                    <p class="font-semibold text-white">${escapeHtml(venda.numero_unico)}</p>
                    <p class="text-xs text-slate-500">${escapeHtml(venda.funcionario_nome || "Sem operador")}</p>
                    <p class="text-xs text-slate-500">${escapeHtml(venda.cliente_nome || "Sem cliente")}</p>
                    <p class="text-xs text-slate-500">Preco ${escapeHtml(formatModalidadePrecoLabel(venda.modalidade_preco))}</p>
                </td>
                <td class="px-5 py-4 align-middle text-slate-300">${formatDateTime(venda.data_venda)}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(venda.empresa_nome || "-")}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${formatInteger(venda.itens_quantidade)}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(pagamentos)}</td>
                <td class="px-5 py-4 align-middle text-right text-white font-semibold">${formatCurrency(venda.total)}</td>
                <td class="px-5 py-4 align-middle text-center">${statusBadge}</td>
                <td class="px-5 py-4 align-middle">
                    <div class="flex items-center justify-center gap-2">
                        <button type="button"
                            class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-300 hover:bg-sky-500/20 transition"
                            onclick="abrirModalVenda(${venda.id}, false)">
                            <i data-lucide="file-text" class="w-4 h-4"></i>
                        </button>
                        <button type="button"
                            class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 text-slate-200 hover:border-sky-500/30 hover:text-white transition"
                            onclick="abrirComprovanteVenda(${venda.id})">
                            <i data-lucide="printer" class="w-4 h-4"></i>
                        </button>
                        ${podeCancelarVenda ? `
                            <button type="button"
                                class="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 hover:bg-rose-500/20 transition"
                                onclick="abrirModalVenda(${venda.id}, true)">
                                <i data-lucide="ban" class="w-4 h-4"></i>
                            </button>
                        ` : ""}
                    </div>
                </td>
            </tr>
        `;
    }).join("");

    renderPdvPagination("pdv-vendas-pagination", paginacao, pdvPage.vendas.length, () => renderVendas());

    if (window.lucide) {
        lucide.createIcons();
    }
}

function abrirModalVenda(vendaId, focarCancelamento) {
    const venda = pdvPage.vendas.find((item) => Number(item.id) === Number(vendaId));
    if (!venda) return;

    pdvPage.vendaSelecionada = venda;

    const content = document.getElementById("pdv-sale-detail-content");
    const cancelReason = document.getElementById("pdv-sale-cancel-reason");
    const cancelButton = document.getElementById("pdv-sale-cancel-button");

    if (content) {
        content.innerHTML = `
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Venda</p>
                    <strong class="block text-white mt-2">${escapeHtml(venda.numero_unico)}</strong>
                    <p class="text-sm text-slate-400 mt-2">${escapeHtml(venda.empresa_nome || "-")}</p>
                    <p class="text-sm text-slate-400">${formatDateTime(venda.data_venda)}</p>
                    <p class="text-sm text-slate-400">Modalidade ${escapeHtml(formatModalidadePrecoLabel(venda.modalidade_preco))}</p>
                </div>
                <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Resumo financeiro</p>
                    <strong class="block text-white mt-2">${formatCurrency(venda.total)}</strong>
                    <p class="text-sm text-slate-400 mt-2">Subtotal ${formatCurrency(venda.subtotal)}</p>
                    <p class="text-sm text-slate-400">Desconto ${formatCurrency(venda.desconto)}</p>
                    <p class="text-sm text-slate-400">Cashback na venda ${venda.cashback_ativado ? "ativado" : "desativado"}</p>
                    <p class="text-sm text-slate-400">Cashback usado ${formatCurrency(venda.cashback_utilizado || 0)}</p>
                    <p class="text-sm text-slate-400">Cashback gerado ${formatCurrency(venda.cashback_gerado || 0)}</p>
                </div>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500 mb-3">Cliente vinculado</p>
                <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <div>
                        <p class="font-medium text-white">${escapeHtml(venda.cliente_nome || "Venda sem cliente")}</p>
                        <p class="text-sm text-slate-400">${escapeHtml(formatDocumentValue(venda.cliente_documento) || "Sem documento")}</p>
                    </div>
                    <span class="text-sm text-slate-400">${escapeHtml(venda.status || "-")}</span>
                </div>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500 mb-3">Itens</p>
                <div class="space-y-3">
                    ${venda.itens.map((item) => `
                        <div class="flex items-start justify-between gap-4">
                            <div class="flex-1">
                                <p class="font-medium text-white">${escapeHtml(item.produto_nome || "-")}</p>
                                <p class="text-sm text-slate-400">
                                    ${formatInteger(item.quantidade)} x ${formatCurrency(item.valor_unitario)}
                                    (${escapeHtml(formatModalidadePrecoLabel(item.modalidade_preco_aplicada))})
                                </p>
                                <p class="text-xs text-slate-500">Cancelado ${formatInteger(item.quantidade_cancelada || 0)} | Disponivel ${formatInteger(item.quantidade_disponivel_cancelamento || 0)}</p>
                                ${item.motivo_cancelamento ? `<p class="text-xs text-rose-300 mt-2">${escapeHtml(item.motivo_cancelamento)}</p>` : ""}
                            </div>
                            <div class="flex flex-col items-end gap-3">
                                <strong class="text-white">${formatCurrency(item.valor_total)}</strong>
                                ${Boolean(window.__uiFlags?.can_cancel_sale_items) && item.permite_cancelamento ? `
                                    <label>Quantidade a devolver
                                        <input id="pdv-devolver-${item.id}" type="number" min="1" max="${item.quantidade_disponivel_cancelamento}" step="1" value="1" class="w-20 bg-slate-900 px-2 py-1">
                                    </label>
                                    <button type="button"
                                        class="inline-flex items-center justify-center gap-2 rounded-xl bg-amber-400/10 border border-amber-400/20 text-amber-300 hover:bg-amber-400/20 text-xs font-semibold px-3 py-2 transition"
                                        onclick="cancelarItemVenda(${item.id})">
                                        <i data-lucide="rotate-ccw" class="w-4 h-4"></i>
                                        Cancelar item
                                    </button>
                                ` : ""}
                            </div>
                        </div>
                    `).join("")}
                </div>
            </div>

            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500 mb-3">Pagamentos</p>
                <div class="space-y-3">
                    ${venda.pagamentos.map((pagamento) => `
                        <div class="flex items-center justify-between gap-4">
                            <div>
                                <p class="font-medium text-white">${escapeHtml(pagamento.forma_pagamento_nome || "-")}</p>
                                <p class="text-sm text-slate-400">${escapeHtml(pagamento.comprovante || "Sem comprovante")}</p>
                            </div>
                            <strong class="text-white">${formatCurrency(pagamento.valor)}</strong>
                        </div>
                    `).join("")}
                </div>
            </div>

            ${venda.observacao ? `
                <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                    <p class="text-xs uppercase tracking-[0.14em] text-slate-500 mb-2">Observacao</p>
                    <p class="text-sm text-slate-300 whitespace-pre-line">${escapeHtml(venda.observacao)}</p>
                </div>
            ` : ""}
        `;
    }

    if (cancelReason) {
        cancelReason.value = "";
    }

    if (cancelButton) {
        cancelButton.classList.toggle("hidden", !(Boolean(window.__uiFlags?.can_cancel_sales) && venda.permite_cancelamento));
    }

    abrirModal("pdv-sale-modal");
    if (focarCancelamento && cancelReason) {
        cancelReason.focus();
    }

    if (window.lucide) {
        lucide.createIcons();
    }
}

async function cancelarItemVenda(itemId) {
    if (!pdvPage.vendaSelecionada) return;

    pdvPage.cancelamentosPendentes ??= {};
    const operation = `${pdvPage.vendaSelecionada.id}:${itemId}`;
    const motivoAtual = (document.getElementById("pdv-sale-cancel-reason")?.value || "").trim();
    const quantidade = document.getElementById(`pdv-devolver-${itemId}`)?.value || "1";
    pdvPage.cancelamentosPendentes[operation] ??= { motivo: motivoAtual, quantidade, idempotency_key: crypto.randomUUID() };

    try {
        const motivo = (document.getElementById("pdv-sale-cancel-reason")?.value || "").trim();
        const result = await requestJson(`/api/pdv/vendas/${pdvPage.vendaSelecionada.id}/itens/${itemId}/cancelar`, {
            method: "POST",
            headers: getAuthHeaders(true),
            body: JSON.stringify(pdvPage.cancelamentosPendentes[operation])
        });

        delete pdvPage.cancelamentosPendentes[operation];
        showMessage(result.message || "Item cancelado com sucesso.", "success");
        await carregarDadosPdv();
        abrirModalVenda(pdvPage.vendaSelecionada.id, false);
    } catch (error) {
        showMessage(error.message || "Erro ao cancelar o item.", "error");
    }
}

function abrirModalConfirmacaoVenda(payload) {
    const content = document.getElementById("pdv-confirm-content");
    if (!content) return;

    const subtotal = obterSubtotalCarrinho();
    const desconto = parseCurrencyValue(document.getElementById("pdv-total-desconto")?.textContent || "0");
    const total = parseCurrencyValue(document.getElementById("pdv-total-geral")?.textContent || "0");
    const empresa = pdvPage.auxiliares.empresas.find((item) => String(item.id) === String(payload.empresa_id));
    const cliente = obterClienteSelecionadoPdv();
    const cashback = parseCurrencyValue(payload.cashback_utilizado || "0");
    const modalidadePreco = formatModalidadePrecoLabel(payload.modalidade_preco);

    content.innerHTML = `
        <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Empresa</p>
                <strong class="block text-white mt-2">${escapeHtml(empresa?.nome || "-")}</strong>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Itens</p>
                <strong class="block text-white mt-2">${formatInteger(payload.itens.length)}</strong>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Preco</p>
                <strong class="block text-white mt-2">${escapeHtml(modalidadePreco)}</strong>
            </div>
            <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Total</p>
                <strong class="block text-white mt-2">${formatCurrency(total)}</strong>
            </div>
        </div>

        <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div class="flex items-center justify-between gap-4">
                <div>
                    <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Cliente</p>
                    <p class="font-medium text-white mt-2">${escapeHtml(cliente?.nome || "Venda sem cliente")}</p>
                    <p class="text-sm text-slate-400">${escapeHtml(formatDocumentValue(cliente?.documento) || "Sem documento")}</p>
                </div>
                <div class="text-right">
                    <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Cashback usado</p>
                    <p class="font-semibold text-white mt-2">${formatCurrency(cashback)}</p>
                </div>
            </div>
        </div>

        <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <div class="flex items-center justify-between gap-4 mb-3">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">Itens confirmados</p>
                <span class="text-sm text-slate-400">Subtotal ${formatCurrency(subtotal)} · Desconto ${formatCurrency(desconto)}</span>
            </div>
            <div class="space-y-3">
                ${pdvPage.carrinho.map((item) => `
                    <div class="flex items-center justify-between gap-4">
                        <div>
                            <p class="font-medium text-white">${escapeHtml(item.nome)}</p>
                            <p class="text-sm text-slate-400">
                                ${formatInteger(item.quantidade)} x ${formatCurrency(item.valor_venda)}
                                (${escapeHtml(formatModalidadePrecoLabel(item.modalidade_preco_aplicada))})
                            </p>
                        </div>
                        <strong class="text-white">${formatCurrency(multiplicar(item.valor_venda, item.quantidade))}</strong>
                    </div>
                `).join("")}
            </div>
        </div>

        <div class="rounded-2xl border border-slate-800 bg-slate-950/60 p-4">
            <p class="text-xs uppercase tracking-[0.14em] text-slate-500 mb-3">Pagamentos</p>
            <div class="space-y-3">
                ${payload.pagamentos.length ? payload.pagamentos.map((pagamento) => {
                    const forma = pdvPage.auxiliares.formas_pagamento.find((item) => String(item.id) === String(pagamento.forma_pagamento_id));
                    return `
                        <div class="flex items-center justify-between gap-4">
                            <p class="font-medium text-white">${escapeHtml(forma?.nome || "-")}</p>
                            <strong class="text-white">${formatCurrency(pagamento.valor)}</strong>
                        </div>
                    `;
                }).join("") : `
                    <div class="flex items-center justify-between gap-4">
                        <p class="font-medium text-white">Sem pagamento adicional</p>
                        <strong class="text-white">${formatCurrency(0)}</strong>
                    </div>
                `}
            </div>
        </div>
    `;

    abrirModal("pdv-confirm-modal");
    if (window.lucide) {
        lucide.createIcons();
    }
}

function abrirModalSucessoVenda(venda) {
    if (!venda) return;

    const message = document.getElementById("pdv-success-message");
    const summary = document.getElementById("pdv-success-summary");

    if (message) {
        message.textContent = `${venda.numero_unico} finalizada em ${formatCurrency(venda.total)}.`;
    }

    if (summary) {
        summary.innerHTML = `
            <div class="space-y-2 text-sm text-slate-300">
                <div class="flex items-center justify-between gap-3">
                    <span>Empresa</span>
                    <strong class="text-white">${escapeHtml(venda.empresa_nome || "-")}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Itens</span>
                    <strong class="text-white">${formatInteger(venda.itens_quantidade)}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Preco</span>
                    <strong class="text-white">${escapeHtml(formatModalidadePrecoLabel(venda.modalidade_preco))}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Cliente</span>
                    <strong class="text-white">${escapeHtml(venda.cliente_nome || "Sem cliente")}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Cashback na venda</span>
                    <strong class="text-white">${venda.cashback_ativado ? "Ativado" : "Desativado"}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Cashback usado</span>
                    <strong class="text-white">${formatCurrency(venda.cashback_utilizado || 0)}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Cashback gerado</span>
                    <strong class="text-white">${formatCurrency(venda.cashback_gerado || 0)}</strong>
                </div>
                <div class="flex items-center justify-between gap-3">
                    <span>Total</span>
                    <strong class="text-white">${formatCurrency(venda.total)}</strong>
                </div>
            </div>
        `;
    }

    abrirModal("pdv-success-modal");
}

function abrirComprovanteVenda(vendaId) {
    if (!vendaId) return;
    const url = new URL(`/api/pdv/vendas/${vendaId}/comprovante`, window.location.origin);
    window.open(url.toString(), "_blank", "noopener");
}

async function emitirNotaFiscalPdv(vendaId) {
    try {
        const result = await requestJson("/api/fiscal/notas/emitir", {
            method: "POST",
            headers: getAuthHeaders(true),
            body: JSON.stringify({ venda_id: vendaId })
        });
        showMessage(result.message || "XML fiscal interno gerado com sucesso.", "success");
        await carregarVendas();
        if (result.data?.id) {
            const url = new URL(`/api/fiscal/notas/${result.data.id}/xml`, window.location.origin);
            window.open(url.toString(), "_blank", "noopener");
        }
    } catch (error) {
        showMessage(error.message || "Erro ao gerar XML fiscal interno.", "error");
    }
}

function atualizarKpis() {
    setText("pdv-kpi-produtos", String(pdvPage.produtos.length));
    setText(
        "pdv-kpi-baixo-estoque",
        String(pdvPage.produtos.filter((item) => Number(item.estoque_atual) <= Number(item.estoque_minimo)).length)
    );

    const hoje = new Date().toISOString().slice(0, 10);
    const vendasHoje = pdvPage.vendas.filter((item) => (item.data_venda || "").slice(0, 10) === hoje && item.status === "FINALIZADA");
    const totalHoje = vendasHoje.reduce((sum, item) => sum + parseCurrencyValue(item.total), 0);
    setText("pdv-kpi-vendas-hoje", String(vendasHoje.length));
    setText("pdv-kpi-faturamento", `${formatCurrency(totalHoje)} faturados hoje.`);
}

function montarPayloadVenda() {
    if (!pdvPage.empresaId) {
        throw new Error("Selecione a empresa antes de finalizar a venda.");
    }

    if (!pdvPage.carrinho.length) {
        throw new Error("Adicione pelo menos um item ao carrinho.");
    }

    validarModalidadePrecoCarrinho();
    const pagamentos = validarPagamentosConfigurados();

    return {
        empresa_id: pdvPage.empresaId,
        cliente_id: pdvPage.clienteId || "",
        modalidade_preco: obterModalidadePrecoSelecionada(),
        cashback_ativado: cashbackEstaAtivadoNaVenda(),
        cupom_codigo: (document.getElementById("pdv-cupom-codigo")?.value || "").trim(),
        desconto_manual: normalizeMoneyForApi(document.getElementById("pdv-desconto-manual")?.value || "0"),
        cashback_utilizado: normalizeMoneyForApi(document.getElementById("pdv-cashback-utilizado")?.value || "0"),
        observacao: (document.getElementById("pdv-observacao")?.value || "").trim(),
        itens: pdvPage.carrinho.map((item) => ({
            produto_id: item.produto_id,
            quantidade: item.quantidade,
            valor_unitario: String(parseCurrencyValue(item.valor_venda).toFixed(2))
        })),
        pagamentos
    };
}

function validarModalidadePrecoCarrinho() {
    if (obterModalidadePrecoSelecionada() !== "ATACADO") {
        return;
    }

    const indisponiveis = pdvPage.carrinho
        .filter((item) => item.atacado_indisponivel)
        .map((item) => item.nome);
    if (indisponiveis.length) {
        throw new Error(`Os produtos ${indisponiveis.join(", ")} nao possuem preco de atacado configurado.`);
    }

    const pendentes = pdvPage.carrinho
        .filter((item) => item.atacado_pendente)
        .map((item) => `${item.nome} (minimo ${formatInteger(item.quantidade_minima_atacado || 1)})`);
    if (pendentes.length) {
        throw new Error(`A venda em atacado exige quantidade minima nos itens: ${pendentes.join(", ")}.`);
    }
}

function atualizarResumoVenda() {
    recalcularPrecosCarrinho();
    const subtotal = obterSubtotalCarrinho();
    const descontoManual = parseCurrencyValue(document.getElementById("pdv-desconto-manual")?.value || "0");
    const cupom = obterCupomSelecionado();
    const descontoCupom = calcularDescontoCupom(cupom, subtotal);
    const descontoTotal = Math.min(subtotal, descontoManual + descontoCupom);
    const baseTotal = Math.max(subtotal - descontoTotal, 0);
    const cashbackAplicado = obterCashbackAplicado(baseTotal);
    const cashbackInput = document.getElementById("pdv-cashback-utilizado");
    if (cashbackInput && document.activeElement !== cashbackInput) {
        cashbackInput.value = formatCurrencyInput(cashbackAplicado);
    }
    const total = Math.max(baseTotal - cashbackAplicado, 0);

    setText("pdv-total-subtotal", formatCurrency(subtotal));
    setText("pdv-total-desconto", formatCurrency(descontoTotal));
    setText("pdv-total-geral", formatCurrency(total));
    atualizarResumoClientePdv();

    if (pdvPage.pagamentoConfirmado && !pagamentoEstaConfirmadoParaTotalAtual(total)) {
        marcarPagamentoPendente();
    }

    syncSinglePaymentWithTotal(total);
    renderPaymentSnapshot(total);
    atualizarStatusPagamento(total);
}

function obterCupomSelecionado() {
    const codigo = (document.getElementById("pdv-cupom-codigo")?.value || "").trim().toLowerCase();
    if (!codigo) return null;
    return (pdvPage.auxiliares.cupons || []).find((item) => String(item.codigo || "").toLowerCase() === codigo) || null;
}

function calcularDescontoCupom(cupom, subtotal) {
    if (!cupom) return 0;
    const hoje = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo" }).format(new Date());
    if ((cupom.empresa_id && String(cupom.empresa_id) !== String(pdvPage.empresaId))
        || (cupom.cliente_id && String(cupom.cliente_id) !== String(pdvPage.clienteId))
        || (cupom.data_inicio && cupom.data_inicio > hoje) || cupom.data_validade < hoje
        || (cupom.limite_usos && cupom.usos >= cupom.limite_usos)
        || subtotal < parseCurrencyValue(cupom.valor_minimo || "0")) return 0;
    const valor = parseCurrencyValue(cupom.valor_desconto);
    const descontoCentavos = cupom.tipo_desconto === "PERCENTUAL"
        ? Math.round(Math.round(subtotal * 100) * Math.round(valor * 100) / 10000)
        : Math.round(valor * 100);
    const limite = cupom.desconto_maximo ? parseCurrencyValue(cupom.desconto_maximo) : subtotal;
    return Math.min(descontoCentavos, Math.round(subtotal * 100), Math.round(limite * 100)) / 100;
}

function resetPayments() {
    pdvPage.pagamentos = [criarPagamentoVazio()];
    pdvPage.pagamentoConfirmado = false;
    pdvPage.pagamentoConfirmadoTotal = null;
    renderPayments();
    atualizarStatusPagamento();
}

function criarPagamentoVazio() {
    return {
        uid: pdvPage.paymentCounter++,
        forma_pagamento_id: "",
        valor: "",
        touched: false
    };
}

function syncSinglePaymentWithTotal(totalOverride) {
    if (pdvPage.pagamentos.length !== 1) return;

    const total = typeof totalOverride === "number"
        ? totalOverride
        : parseCurrencyValue(document.getElementById("pdv-total-geral")?.textContent || "0");
    const payment = pdvPage.pagamentos[0];

    if (!payment.touched || !payment.valor || parseCurrencyValue(payment.valor) === 0) {
        payment.valor = formatCurrencyInput(total);
        const input = document.querySelector(`.pdv-payment-valor[data-payment-uid="${payment.uid}"]`);
        if (input) {
            input.value = payment.valor;
        }
    }

    renderPaymentSnapshot(total);
}

function validarPagamentosConfigurados() {
    const totalVenda = obterTotalAtualVenda();
    if (totalVenda <= 0.009) {
        return [];
    }

    const pagamentosNormalizados = pdvPage.pagamentos.map((item) => {
        const formaPagamentoId = String(item.forma_pagamento_id || "").trim();
        const valorNumerico = parseCurrencyValue(item.valor);

        return {
            forma_pagamento_id: formaPagamentoId,
            valorNumerico,
            valor: normalizeMoneyForApi(item.valor || "0"),
            comprovante: ""
        };
    });

    const possuiLinhaIncompleta = pagamentosNormalizados.some((item) => {
        const temForma = Boolean(item.forma_pagamento_id);
        const temValor = item.valorNumerico > 0;
        return temForma !== temValor;
    });

    if (possuiLinhaIncompleta) {
        throw new Error("Preencha forma e valor em cada pagamento informado.");
    }

    const pagamentos = pagamentosNormalizados.filter((item) => item.forma_pagamento_id && item.valorNumerico > 0);

    if (!pagamentos.length) {
        throw new Error("Informe ao menos um pagamento valido.");
    }

    const totalInformado = pagamentos.reduce((sum, item) => sum + item.valorNumerico, 0);
    if (Math.abs(totalInformado - totalVenda) > 0.009) {
        throw new Error("A soma dos pagamentos deve ser igual ao total da venda.");
    }

    return pagamentos.map(({ forma_pagamento_id, valor, comprovante }) => ({
        forma_pagamento_id,
        valor,
        comprovante
    }));
}

function confirmarPagamentoAtual() {
    if (!pdvPage.carrinho.length) {
        throw new Error("Adicione itens ao carrinho antes de confirmar o pagamento.");
    }

    validarPagamentosConfigurados();
    pdvPage.pagamentoConfirmado = true;
    pdvPage.pagamentoConfirmadoTotal = normalizeMoneyForApi(obterTotalAtualVenda());
    atualizarStatusPagamento();
    fecharModal("pdv-payments-modal");
}

function marcarPagamentoPendente() {
    pdvPage.pagamentoConfirmado = false;
    pdvPage.pagamentoConfirmadoTotal = null;
    atualizarStatusPagamento();
}

function pagamentoEstaConfirmadoParaTotalAtual(totalOverride) {
    if (!pdvPage.pagamentoConfirmado) return false;
    const totalAtual = typeof totalOverride === "number" ? totalOverride : obterTotalAtualVenda();
    return pdvPage.pagamentoConfirmadoTotal === normalizeMoneyForApi(totalAtual);
}

function atualizarStatusPagamento(totalOverride) {
    const status = document.getElementById("pdv-payment-status");
    const finalizeBtn = document.getElementById("pdv-finalizar-venda");
    const totalAtual = typeof totalOverride === "number" ? totalOverride : obterTotalAtualVenda();
    const prontoParaFinalizar = pdvPage.carrinho.length > 0 && pagamentoEstaConfirmadoParaTotalAtual(totalAtual);

    if (status) {
        status.classList.remove("is-success", "is-warning");
        if (!pdvPage.carrinho.length) {
            status.textContent = "Adicione itens para liberar o pagamento.";
        } else if (prontoParaFinalizar) {
            status.textContent = "Pagamento confirmado. Venda pronta para finalizar.";
            status.classList.add("is-success");
        } else {
            status.textContent = "Pagamento ainda nao confirmado.";
            status.classList.add("is-warning");
        }
    }

    if (finalizeBtn) {
        finalizeBtn.disabled = !prontoParaFinalizar;
    }

    renderPaymentSnapshot(totalAtual);
}

function renderPaymentSnapshot(totalOverride) {
    const totalDueEl = document.getElementById("pdv-payment-total-due");
    const totalInformedEl = document.getElementById("pdv-payment-total-informed");
    const totalDiffEl = document.getElementById("pdv-payment-total-diff");
    if (!totalDueEl || !totalInformedEl || !totalDiffEl) return;

    const totalVenda = typeof totalOverride === "number" ? totalOverride : obterTotalAtualVenda();
    const totalInformado = pdvPage.pagamentos.reduce((sum, item) => {
        return sum + (item.forma_pagamento_id ? parseCurrencyValue(item.valor) : 0);
    }, 0);
    const diferenca = totalVenda - totalInformado;
    const diffRow = totalDiffEl.closest(".pdv-payment-summary-row");

    totalDueEl.textContent = formatCurrency(totalVenda);
    totalInformedEl.textContent = formatCurrency(totalInformado);
    totalDiffEl.textContent = formatCurrency(Math.abs(diferenca));

    if (diffRow) {
        diffRow.classList.remove("is-balanced", "is-warning", "is-error");
        if (Math.abs(diferenca) <= 0.009) {
            diffRow.classList.add("is-balanced");
            totalDiffEl.textContent = formatCurrency(0);
        } else if (diferenca > 0) {
            diffRow.classList.add("is-warning");
        } else {
            diffRow.classList.add("is-error");
        }
    }
}

function obterTotalAtualVenda() {
    return parseCurrencyValue(document.getElementById("pdv-total-geral")?.textContent || "0");
}

function limparCarrinho() {
    pdvPage.carrinho = [];
    pdvPage.payloadConfirmacaoPendente = null;
    pdvPage.clienteId = "";
    pdvPage.modalidadePreco = "AUTOMATICO";
    pdvPage.cashbackAtivadoNaVenda = cashbackPodeSerOperadoNaVenda();
    const cupom = document.getElementById("pdv-cupom-codigo");
    const cliente = document.getElementById("pdv-cliente");
    const modalidadePreco = document.getElementById("pdv-modalidade-preco");
    const cashback = document.getElementById("pdv-cashback-utilizado");
    const cashbackToggle = document.getElementById("pdv-cashback-ativado");
    const desconto = document.getElementById("pdv-desconto-manual");
    const observacao = document.getElementById("pdv-observacao");
    if (cupom) cupom.value = "";
    if (cliente) cliente.value = "";
    if (modalidadePreco) modalidadePreco.value = pdvPage.modalidadePreco;
    if (cashback) cashback.value = "0,00";
    if (cashbackToggle) cashbackToggle.checked = pdvPage.cashbackAtivadoNaVenda;
    if (desconto) desconto.value = "0,00";
    if (observacao) observacao.value = "";
    pdvPage.pagamentoConfirmado = false;
    pdvPage.pagamentoConfirmadoTotal = null;
    atualizarResumoClientePdv();
    atualizarResumoModalidadePreco();
    renderCarrinho();
}

function resetPdvCloseoutForm() {
    const empresa = document.getElementById("pdv-closeout-empresa");
    const data = document.getElementById("pdv-closeout-data");
    const inicial = document.getElementById("pdv-closeout-inicial");
    const final = document.getElementById("pdv-closeout-final");
    const observacao = document.getElementById("pdv-closeout-observacao");

    if (empresa) {
        empresa.value = pdvPage.empresaId || pdvPage.auxiliares.empresas[0]?.id || "";
    }
    if (data) {
        data.value = new Date().toISOString().slice(0, 10);
    }
    if (inicial) {
        inicial.value = "0,00";
    }
    if (final) {
        final.value = "0,00";
    }
    if (observacao) {
        observacao.value = "";
    }
}

function limparCatalogoPdv() {
    pdvPage.catalogoPorId = {};
    pdvPage.catalogoPorCodigoBarras = {};
}

function reindexarCatalogoPdv(produtos) {
    (produtos || []).forEach((produto) => {
        if (!produto || !produto.id) return;
        pdvPage.catalogoPorId[produto.id] = produto;

        const codigo = normalizeBarcodeValue(produto.codigo_barras);
        if (codigo) {
            pdvPage.catalogoPorCodigoBarras[codigo] = produto;
        }
    });
}

function normalizeBarcodeValue(value) {
    return String(value || "").replace(/\s+/g, "").trim();
}

function limparBarcodeField() {
    const input = document.getElementById("pdv-barcode-input");
    if (input) {
        input.value = "";
    }
}

function setBarcodeFeedback(message, type = "info") {
    const element = document.getElementById("pdv-barcode-feedback");
    if (!element) return;

    element.textContent = message;
    element.classList.remove("is-success", "is-error", "is-info", "is-muted");
    element.classList.add(`is-${type}`);
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
            result = { success: false, message: "Resposta invalida do servidor." };
        }

        if (!response.ok || result.success === false) {
            throw new Error(result.message || "Erro na requisicao.");
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
        ${type === "success" ? "bg-emerald-500 text-slate-950" : "bg-red-500 text-white"}
    `;
    div.textContent = message;
    document.body.appendChild(div);

    setTimeout(() => div.remove(), 3000);
}

function bindMoneyMask(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    bindMoneyMaskToElement(input);
}

function bindMoneyMaskToElement(input) {
    if (!input) return;

    const isDiscountInput = input.id === "pdv-desconto-manual";

    window.DecimalInput?.bind(input, {
        decimals: 2,
        allowEmpty: !isDiscountInput,
        onInput: () => {
            if (isDiscountInput) {
                atualizarResumoVenda();
            }
        },
        onBlur: () => {
            if (isDiscountInput) {
                atualizarResumoVenda();
            }
        }
    });
}

function parseCurrencyValue(value) {
    return window.DecimalInput?.parse(value) ?? 0;
}

function formatCurrencyInput(value) {
    return window.DecimalInput?.format(value, 2, {
        allowEmpty: false,
        useGrouping: true
    }) ?? "0,00";
}

function normalizeMoneyForApi(value) {
    return window.DecimalInput?.normalize(value, 2) ?? "0.00";
}

function obterSubtotalCarrinho() {
    return pdvPage.carrinho.reduce((centavos, item) =>
        centavos + Math.round(parseCurrencyValue(item.valor_venda) * 100) * Number(item.quantidade), 0) / 100;
}

function multiplicar(valor, quantidade) {
    return parseCurrencyValue(valor) * Number(quantidade || 0);
}

function formatCurrency(value) {
    const parsed = typeof value === "number" ? value : parseCurrencyValue(value);
    return new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL"
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatPercentValue(value) {
    const parsed = typeof value === "number" ? value : parseCurrencyValue(value);
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(Number.isNaN(parsed) ? 0 : parsed) + "%";
}

function formatDocumentValue(value) {
    return window.InputMask?.formatDocument(value) ?? String(value ?? "");
}

function formatInteger(value) {
    const digits = String(value ?? "").replace(/\D/g, "");
    const parsed = Number.parseInt(digits || "0", 10);
    return new Intl.NumberFormat("pt-BR", {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(Number.isNaN(parsed) ? 0 : parsed);
}

function formatDateTime(value) {
    if (!value) return "-";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "-";

    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "short",
        timeStyle: "short"
    }).format(date);
}

function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
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

function getPdvPageItems(items, paginacao) {
    const totalPaginas = Math.max(Math.ceil(items.length / paginacao.porPagina), 1);
    if (paginacao.paginaAtual > totalPaginas) {
        paginacao.paginaAtual = totalPaginas;
    }

    const inicio = (paginacao.paginaAtual - 1) * paginacao.porPagina;
    return items.slice(inicio, inicio + paginacao.porPagina);
}

function renderPdvPagination(containerId, paginacao, totalItens, onChange) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const totalPaginas = Math.max(Math.ceil(totalItens / paginacao.porPagina), 1);

    if (!totalItens) {
        container.innerHTML = "";
        return;
    }

    if (totalPaginas <= 1) {
        container.innerHTML = `<div class="pagination-summary px-1 py-4">Exibindo ${totalItens} registro(s).</div>`;
        return;
    }

    const inicio = ((paginacao.paginaAtual - 1) * paginacao.porPagina) + 1;
    const fim = Math.min(paginacao.paginaAtual * paginacao.porPagina, totalItens);
    const paginas = buildPdvPageNumbers(paginacao.paginaAtual, totalPaginas);

    container.innerHTML = `
        <div class="pagination-shell">
            <div class="pagination-summary">Exibindo ${inicio}-${fim} de ${totalItens} registros</div>
            <div class="pagination-controls">
                <button type="button" class="pagination-btn" data-page="${paginacao.paginaAtual - 1}" ${paginacao.paginaAtual === 1 ? "disabled" : ""}>Anterior</button>
                ${paginas.map((pagina) => pagina === "..."
                    ? `<span class="pagination-ellipsis">...</span>`
                    : `<button type="button" class="pagination-btn ${pagina === paginacao.paginaAtual ? "pagination-btn-active" : ""}" data-page="${pagina}">${pagina}</button>`
                ).join("")}
                <button type="button" class="pagination-btn" data-page="${paginacao.paginaAtual + 1}" ${paginacao.paginaAtual === totalPaginas ? "disabled" : ""}>Proxima</button>
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

function buildPdvPageNumbers(paginaAtual, totalPaginas) {
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
