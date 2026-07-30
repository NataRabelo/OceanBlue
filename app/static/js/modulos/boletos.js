(function () {
    const state = {
        boletos: [],
        filtros: {
            status: "",
            cliente: "",
            vencimento: "",
            venda: ""
        }
    };

    document.addEventListener("DOMContentLoaded", async () => {
        bindBoletoFilters();
        await carregarBoletos();
        if (window.lucide) {
            lucide.createIcons();
        }
        document.addEventListener("click", async (event) => {
            const registrarButton = event.target.closest("[data-boleto-registrar]");
            const consultarButton = event.target.closest("[data-boleto-consultar]");
            if (registrarButton) {
                event.preventDefault();
                await registrarBoleto(registrarButton.dataset.boletoRegistrar);
            }
            if (consultarButton) {
                event.preventDefault();
                await consultarBoleto(consultarButton.dataset.boletoConsultar);
            }
        });
    });

    function bindBoletoFilters() {
        bindInput("boleto-status", "status");
        bindInput("boleto-cliente", "cliente");
        bindInput("boleto-vencimento", "vencimento");
        bindInput("boleto-venda", "venda");

        document.getElementById("boleto-limpar-filtros")?.addEventListener("click", () => {
            Object.keys(state.filtros).forEach((key) => {
                state.filtros[key] = "";
            });
            ["boleto-status", "boleto-cliente", "boleto-vencimento", "boleto-venda"].forEach((id) => {
                const field = document.getElementById(id);
                if (field) field.value = "";
            });
            renderBoletos();
        });
    }

    function bindInput(id, key) {
        const field = document.getElementById(id);
        if (!field) return;
        field.addEventListener("input", () => {
            state.filtros[key] = field.value || "";
            renderBoletos();
        });
    }

    async function carregarBoletos() {
        try {
            const result = await requestJson("/api/financeiro/boletos?limite=500");
            state.boletos = Array.isArray(result.data) ? result.data : [];
            renderBoletos();
        } catch (error) {
            const body = document.getElementById("boleto-lista");
            if (body) {
                body.innerHTML = `<tr><td colspan="8" class="px-5 py-8 text-center text-rose-300">${escapeHtml(error.message || "Erro ao carregar boletos.")}</td></tr>`;
            }
        }
    }

    function renderBoletos() {
        const body = document.getElementById("boleto-lista");
        const resumo = document.getElementById("boleto-resumo");
        if (!body) return;

        const items = state.boletos.filter(matchesFilters);
        if (resumo) {
            resumo.textContent = `${items.length} de ${state.boletos.length} registro(s) exibido(s).`;
        }

        if (!items.length) {
            body.innerHTML = `<tr><td colspan="8" class="px-5 py-8 text-center text-slate-400">Nenhum boleto encontrado.</td></tr>`;
            return;
        }

        body.innerHTML = items.map((boleto) => `
            <tr class="hover:bg-slate-800/40 transition">
                <td class="px-5 py-4 align-middle">
                    <p class="font-medium text-white">${escapeHtml(boleto.numero_boleto || "-")}</p>
                    <p class="text-xs text-amber-200 mt-1">${escapeHtml(boleto.provider_codigo || "Controle interno")}</p>
                </td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(boleto.cliente_nome || `Cliente #${boleto.cliente_id || "-"}`)}</td>
                <td class="px-5 py-4 align-middle text-slate-300">${formatDate(boleto.data_vencimento)}</td>
                <td class="px-5 py-4 align-middle text-right">
                    <strong class="block text-white">${formatCurrency(boleto.valor_restante)}</strong>
                    <span class="text-xs text-slate-500">de ${formatCurrency(boleto.valor_nominal)}</span>
                </td>
                <td class="px-5 py-4 align-middle">
                    <span class="inline-flex items-center rounded-full border ${statusClass(boleto.status)} px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]">
                        ${escapeHtml(labelStatus(boleto.status))}
                    </span>
                </td>
                <td class="px-5 py-4 align-middle">
                    <span class="inline-flex items-center rounded-full border ${statusBancarioClass(boleto.status_bancario)} px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em]">
                        ${escapeHtml(labelStatusBancario(boleto.status_bancario))}
                    </span>
                    ${boleto.protocolo_registro ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(boleto.protocolo_registro)}</p>` : ""}
                    ${boleto.mensagem_retorno_banco ? `<p class="text-xs text-slate-500 mt-1">${escapeHtml(boleto.mensagem_retorno_banco)}</p>` : ""}
                    ${boleto.boleto_url ? `<a class="text-xs text-sky-300 mt-1 inline-block" href="${escapeHtml(boleto.boleto_url)}" target="_blank" rel="noopener">Boleto/PDF</a>` : ""}
                </td>
                <td class="px-5 py-4 align-middle text-slate-300">${escapeHtml(boleto.banco_emissor_nome || `Banco #${boleto.banco_emissor_id || "-"}`)}</td>
                <td class="px-5 py-4 align-middle">
                    <div class="flex justify-end gap-2">
                        <button type="button" class="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-slate-200" title="Visualizacao detalhada planejada">
                            <i data-lucide="eye" class="w-4 h-4"></i>
                        </button>
                        <button type="button" data-boleto-registrar="${escapeHtml(boleto.id)}" class="rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-emerald-200" title="Registrar boleto em homologacao">
                            <i data-lucide="send" class="w-4 h-4"></i>
                        </button>
                        <button type="button" data-boleto-consultar="${escapeHtml(boleto.id)}" class="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-sky-200" title="Consultar status no provider">
                            <i data-lucide="search" class="w-4 h-4"></i>
                        </button>
                        <button type="button" class="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-sky-200" title="Recalculo manual disponivel via endpoint">
                            <i data-lucide="refresh-cw" class="w-4 h-4"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `).join("");

        if (window.lucide) {
            lucide.createIcons();
        }
    }

    function matchesFilters(boleto) {
        const statusOk = !state.filtros.status || boleto.status === state.filtros.status;
        const cliente = `${boleto.cliente_nome || ""} ${boleto.cliente_id || ""}`.toLowerCase();
        const clienteOk = !state.filtros.cliente || cliente.includes(state.filtros.cliente.toLowerCase());
        const vencimentoOk = !state.filtros.vencimento || boleto.data_vencimento === state.filtros.vencimento;
        const venda = String(boleto.venda_id || "").toLowerCase();
        const vendaOk = !state.filtros.venda || venda.includes(state.filtros.venda.toLowerCase());
        return statusOk && clienteOk && vencimentoOk && vendaOk;
    }

    async function registrarBoleto(boletoId) {
        if (!boletoId) return;
        try {
            await requestJson(`/api/financeiro/boletos/${boletoId}/registrar`, {
                method: "POST",
                headers: getHeaders(true),
                body: JSON.stringify({})
            });
            await carregarBoletos();
        } catch (error) {
            alert(error.message || "Erro ao registrar boleto.");
        }
    }

    async function consultarBoleto(boletoId) {
        if (!boletoId) return;
        try {
            await requestJson(`/api/financeiro/boletos/${boletoId}/consultar-status`, {
                method: "POST",
                headers: getHeaders(true),
                body: JSON.stringify({})
            });
            await carregarBoletos();
        } catch (error) {
            alert(error.message || "Erro ao consultar boleto.");
        }
    }

    function requestJson(url, options = {}) {
        return fetch(url, {
            credentials: "same-origin",
            ...options,
            headers: {
                ...getHeaders(false),
                ...(options.headers || {})
            }
        }).then(async (response) => {
            const result = await response.json().catch(() => ({ success: false, message: "Resposta invalida do servidor." }));
            if (!response.ok || result.success === false) {
                throw new Error(result.message || "Erro na requisicao.");
            }
            return result;
        });
    }

    function getHeaders(isJson = false) {
        const token = localStorage.getItem("token");
        const headers = {};
        if (isJson) headers["Content-Type"] = "application/json";
        if (token) headers.Authorization = `Bearer ${token}`;
        return headers;
    }

    function labelStatus(status) {
        return {
            PENDENTE: "Pendente",
            EMITIDO: "Emitido interno",
            VENCIDO: "Vencido",
            PARCIALMENTE_PAGO: "Parcial pago",
            PAGO: "Pago",
            CANCELADO: "Cancelado",
            ESTORNADO: "Estornado",
            BAIXA_MANUAL: "Baixa manual"
        }[status] || status || "-";
    }

    function statusClass(status) {
        if (status === "PAGO") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
        if (status === "VENCIDO") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
        if (status === "PARCIALMENTE_PAGO") return "border-sky-500/30 bg-sky-500/10 text-sky-200";
        return "border-amber-500/30 bg-amber-500/10 text-amber-200";
    }

    function labelStatusBancario(status) {
        return {
            NAO_REGISTRADO: "Nao registrado",
            REGISTRO_SOLICITADO: "Registro solicitado",
            REGISTRADO: "Registrado",
            REJEITADO: "Rejeitado",
            PAGO: "Pago banco",
            BAIXADO: "Baixado banco",
            CANCELADO: "Cancelado banco"
        }[status] || status || "-";
    }

    function statusBancarioClass(status) {
        if (status === "REGISTRADO") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
        if (status === "REJEITADO") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
        if (status === "PAGO") return "border-sky-500/30 bg-sky-500/10 text-sky-200";
        return "border-slate-600 bg-slate-800/70 text-slate-200";
    }

    function formatDate(value) {
        if (!value) return "-";
        const date = new Date(`${value}T00:00:00`);
        if (Number.isNaN(date.getTime())) return "-";
        return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short" }).format(date);
    }

    function formatCurrency(value) {
        const number = Number(String(value || "0").replace(",", "."));
        return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number.isFinite(number) ? number : 0);
    }

    function escapeHtml(value) {
        return String(value ?? "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
})();
