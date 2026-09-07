document.addEventListener("DOMContentLoaded", () => {
    const element = (id) => document.getElementById(`ciclo-${id}`);
    const keys = new Map();
    const company = () => element("empresa").value;
    const reason = () => element("motivo").value.trim();
    async function request(url, data) {
        const options = { credentials: "same-origin" };
        if (data) {
            const signature = JSON.stringify([url, data]);
            if (!keys.has(signature)) keys.set(signature, crypto.randomUUID());
            options.method = "POST";
            options.headers = { "Content-Type": "application/json" };
            options.body = JSON.stringify({ ...data, idempotency_key: keys.get(signature) });
        }
        const response = await fetch(url, options);
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || "Operacao recusada.");
        return result.data;
    }
    async function execute(operation) {
        element("status").textContent = "Processando...";
        try {
            await operation();
            element("status").textContent = "Operacao concluida.";
        } catch (error) {
            element("status").textContent = error.message;
        }
    }
    function list(target, records, describe, actions = []) {
        const root = element(target);
        root.replaceChildren();
        if (!records.length) root.textContent = "Nenhum registro.";
        for (const record of records) {
            const row = document.createElement("div");
            row.className = "p-3 border-b border-slate-700 flex flex-wrap gap-3 items-center";
            const label = document.createElement("span");
            label.textContent = describe(record);
            row.append(label);
            for (const action of actions) {
                if (action.when && !action.when(record)) continue;
                const button = document.createElement("button");
                button.textContent = action.label;
                button.className = "btn-primary";
                button.addEventListener("click", () => execute(() => action.run(record)));
                row.append(button);
            }
            root.append(row);
        }
    }
    async function mutate(url, data) {
        await request(url, { ...data, motivo: reason() });
        await refresh();
    }
    function download(data, name) {
        const link = document.createElement("a");
        link.href = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
        link.download = name;
        link.click();
        URL.revokeObjectURL(link.href);
    }
    async function refresh() {
        const query = `?empresa_id=${encodeURIComponent(company())}`;
        const ledger = await request(`/api/financeiro/lancamentos${query}`);
        list("lancamentos", ledger, (record) => `#${record.id} ${record.tipo} ${record.valor} - ${record.descricao}${record.revertido ? " (estornado)" : ""}`, [
            { label: "Estornar", when: (record) => !record.revertido && !record.lancamento_origem_id && record.origem === "MANUAL",
                run: (record) => mutate(`/api/financeiro/lancamentos/${record.id}/estornar`, {}) }
        ]);
        const closures = await request(`/api/financeiro/fechamentos${query}`);
        list("fechamentos", closures, (record) => `Caixa #${record.id} ${record.data_fechamento} ${record.status} - revisao ${record.revisao}; diferenca ${record.diferenca}`, [
            { label: "Reabrir", when: (record) => record.status === "FECHADO",
                run: (record) => mutate(`/api/financeiro/fechamentos/${record.id}/ajustar`, { acao: "reabrir", revisao: record.revisao }) },
            { label: "Fechar com ajuste", when: (record) => record.status === "REABERTO",
                run: (record) => mutate(`/api/financeiro/fechamentos/${record.id}/ajustar`, { acao: "fechar", revisao: record.revisao,
                    valor_inicial: element("inicial").value, valor_final: element("final").value }) }
        ]);
        const advances = await request(`/api/adiantamentos/${query}`);
        const transitions = [["Autorizar", "autorizar", "PENDENTE"], ["Cancelar", "cancelar", "PENDENTE"],
            ["Baixar em folha", "baixar", "AUTORIZADO"], ["Estornar vale", "estornar", "AUTORIZADO"], ["Reverter baixa", "reverter_baixa", "BAIXADO"]];
        list("adiantamentos", advances, (record) => `Vale #${record.id} ${record.funcionario_nome} ${record.valor_total} - ${record.status}`,
            transitions.map(([label, action, status]) => ({ label, when: (record) => record.status === status,
                run: (record) => mutate(`/api/adiantamentos/${record.id}/transicao`, { acao: action, revisao: record.revisao }) })));
        const customers = await request("/api/clientes/");
        list("clientes", customers, (record) => `Cliente #${record.id} ${record.nome} - saldo ${record.saldo_cashback}`, [
            { label: "Exportar dados", run: async (record) => download(await request(`/api/clientes/${record.id}/exportar`), `cliente-${record.id}.json`) },
            { label: "Descadastrar comunicacoes", run: (record) => mutate(`/api/clientes/${record.id}/consentimento`, { aceita_email: false, aceita_sms: false, aceita_whatsapp: false }) },
            { label: "Anonimizar", run: async (record) => {
                if (confirm(`Anonimizar ${record.nome}? Dados cadastrais e conteudo das mensagens serao removidos. Historico financeiro sera preservado.`))
                    await mutate(`/api/clientes/${record.id}/anonimizar`, {});
            } },
            { label: "Acompanhar mensagens", run: async (record) => list("mensagens", await request(`/api/clientes/${record.id}/mensagens`),
                (message) => `#${message.id} ${message.status} - ${message.tentativas} tentativa(s) - ${message.erro || ""}`) }
        ]);
    }
    element("atualizar").onclick = () => execute(refresh);
    element("empresa").onchange = () => execute(refresh);
    element("conciliar").onclick = () => execute(async () => {
        const data = await request(`/api/financeiro/conciliacao?empresa_id=${company()}`);
        element("conciliacao").textContent = `${data.conciliado ? "Conciliado" : "Divergencia"}: PDV ${data.pdv_liquido}; financeiro ${data.financeiro_liquido}; ${data.vendas.length} vendas.`;
        download(data, "conciliacao.json");
    });
    element("folha").onclick = () => execute(async () => {
        const data = await request(`/api/adiantamentos/resumo?empresa_id=${company()}`);
        element("resumo").textContent = `Adiantado ${data.totais.adiantado}; saldo da folha ${data.totais.saldo_a_pagar}.`;
        download(data, "folha.json");
    });
    element("solicitacao").onsubmit = (event) => {
        event.preventDefault();
        execute(async () => {
            await mutate("/api/adiantamentos/solicitar", { empresa_id: company(), funcionario_id: element("funcionario").value,
                tipo_adiantamento: "DINHEIRO", valor_total: element("valor").value });
        });
    };
    element("processar").onclick = () => execute(async () => {
        const records = await request("/api/clientes/mensagens/processar", { limite: 100 });
        list("mensagens", records, (record) => `#${record.id} ${record.status} - ${record.tentativas} tentativa(s)`);
    });
    element("expirar").onclick = () => execute(() => mutate("/api/clientes/cashback/expirar", {}));
    execute(async () => {
        const data = await request("/api/adiantamentos/auxiliares");
        for (const record of data.empresas) element("empresa").add(new Option(record.nome, record.id));
        for (const record of data.funcionarios) element("funcionario").add(new Option(record.nome, record.id));
        await refresh();
    });
});
