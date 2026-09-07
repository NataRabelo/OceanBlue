window.importExportPage = {
    contexto: null,
    prevalidacao: null,
};

document.addEventListener("DOMContentLoaded", async () => {
    bindImportExportActions();

    try {
        await carregarContextoImportExport();
    } catch (error) {
        showImportExportMessage(error.message || "Erro ao carregar o modulo.", "error");
    }

    if (window.lucide) {
        lucide.createIcons();
    }
});

async function carregarContextoImportExport() {
    const result = await requestImportExportJson("/api/importacao-exportacao/contexto", { method: "GET" });
    importExportPage.contexto = result.data || null;

    popularResumoImportExport();
    popularSelectsImportExport();
    renderEntidadesImportExport();
}

function bindImportExportActions() {
    const importEntity = document.getElementById("import-entity");
    const exportEntity = document.getElementById("export-entity");
    const importButton = document.getElementById("import-submit");
    const templateButton = document.getElementById("import-download-template");
    const exportButton = document.getElementById("export-submit");

    if (importEntity) {
        importEntity.addEventListener("change", () => atualizarAjudaEntidade("import"));
    }

    const resetPreview = () => {
        importExportPage.prevalidacao = null;
        if (importButton) importButton.textContent = "Pre-validar arquivo";
    };
    importEntity?.addEventListener("change", resetPreview);
    document.getElementById("import-file")?.addEventListener("change", resetPreview);

    if (exportEntity) {
        exportEntity.addEventListener("change", () => atualizarAjudaEntidade("export"));
    }

    if (templateButton) {
        templateButton.addEventListener("click", async () => {
            const entidade = document.getElementById("import-entity")?.value || "";
            if (!entidade) {
                showImportExportMessage("Selecione uma entidade antes de baixar o modelo.", "error");
                return;
            }

            try {
                await downloadImportExportFile(`/api/importacao-exportacao/template?entidade=${encodeURIComponent(entidade)}`);
            } catch (error) {
                showImportExportMessage(error.message || "Erro ao baixar o modelo.", "error");
            }
        });
    }

    if (importButton) {
        importButton.addEventListener("click", async () => {
            const entidade = document.getElementById("import-entity")?.value || "";
            const input = document.getElementById("import-file");
            const arquivo = input?.files?.[0];

            if (!entidade) {
                showImportExportMessage("Selecione a entidade da importacao.", "error");
                return;
            }

            if (!arquivo) {
                showImportExportMessage("Selecione o arquivo XLSX que sera importado.", "error");
                return;
            }

            try {
                importButton.disabled = true;

                const formData = new FormData();
                formData.append("entidade", entidade);
                formData.append("arquivo", arquivo);
                const preview = importExportPage.prevalidacao?.arquivo !== arquivo || importExportPage.prevalidacao?.entidade !== entidade;
                formData.append("pre_validar", preview ? "true" : "false");

                const result = await requestImportExportJson("/api/importacao-exportacao/importar", {
                    method: "POST",
                    body: formData,
                });

                renderResultadoImportacao(result.data || null);
                showImportExportMessage(result.message || "Importacao concluida.", result.data?.falhas ? "error" : "success");

                if (preview && !result.data?.falhas && result.data?.validas > 0) {
                    importExportPage.prevalidacao = { arquivo, entidade };
                    importButton.textContent = "Confirmar importacao do lote";
                } else {
                    resetPreview();
                }
                if (input && result.data?.confirmado) {
                    input.value = "";
                }
            } catch (error) {
                showImportExportMessage(error.message || "Erro ao importar o arquivo.", "error");
            } finally {
                importButton.disabled = false;
            }
        });
    }

    if (exportButton) {
        exportButton.addEventListener("click", async () => {
            const entidade = document.getElementById("export-entity")?.value || "";
            const empresaId = document.getElementById("export-company")?.value || "";

            if (!entidade) {
                showImportExportMessage("Selecione a entidade da exportacao.", "error");
                return;
            }

            try {
                exportButton.disabled = true;
                const url = new URL("/api/importacao-exportacao/exportar", window.location.origin);
                url.searchParams.set("entidade", entidade);
                if (empresaId) {
                    url.searchParams.set("empresa_id", empresaId);
                }
                await downloadImportExportFile(url.toString());
            } catch (error) {
                showImportExportMessage(error.message || "Erro ao exportar a planilha.", "error");
            } finally {
                exportButton.disabled = false;
            }
        });
    }
}

function popularResumoImportExport() {
    const resumo = importExportPage.contexto?.resumo || {};
    setImportExportText("import-export-kpi-entidades", String(resumo.entidades || 0));
    setImportExportText("import-export-kpi-empresas", String(resumo.empresas || 0));
    setImportExportText("import-export-kpi-modelos", String(resumo.modelos || 0));
}

function popularSelectsImportExport() {
    const entidades = importExportPage.contexto?.entidades || [];
    const empresas = importExportPage.contexto?.empresas || [];
    const importSelect = document.getElementById("import-entity");
    const exportSelect = document.getElementById("export-entity");
    const empresaSelect = document.getElementById("export-company");

    if (importSelect) {
        importSelect.innerHTML = `<option value="">Selecione</option>`;
        entidades.forEach((entidade) => {
            const option = document.createElement("option");
            option.value = entidade.codigo;
            option.textContent = entidade.nome;
            option.disabled = !entidade.pode_importar;
            importSelect.appendChild(option);
        });

        const primeiraDisponivel = entidades.find((item) => item.pode_importar);
        if (primeiraDisponivel) {
            importSelect.value = primeiraDisponivel.codigo;
        }
    }

    if (exportSelect) {
        exportSelect.innerHTML = `<option value="">Selecione</option>`;
        entidades.forEach((entidade) => {
            const option = document.createElement("option");
            option.value = entidade.codigo;
            option.textContent = entidade.nome;
            option.disabled = !entidade.pode_exportar;
            exportSelect.appendChild(option);
        });

        const primeiraDisponivel = entidades.find((item) => item.pode_exportar);
        if (primeiraDisponivel) {
            exportSelect.value = primeiraDisponivel.codigo;
        }
    }

    if (empresaSelect) {
        empresaSelect.innerHTML = `<option value="">Todas as empresas visiveis</option>`;
        empresas.forEach((empresa) => {
            const option = document.createElement("option");
            option.value = empresa.id;
            option.textContent = empresa.nome;
            empresaSelect.appendChild(option);
        });
    }

    atualizarAjudaEntidade("import");
    atualizarAjudaEntidade("export");
}

function atualizarAjudaEntidade(mode) {
    const selectId = mode === "import" ? "import-entity" : "export-entity";
    const helpId = mode === "import" ? "import-entity-help" : "export-entity-help";
    const buttonId = mode === "import" ? "import-submit" : "export-submit";
    const templateButton = document.getElementById("import-download-template");
    const select = document.getElementById(selectId);
    const help = document.getElementById(helpId);
    const button = document.getElementById(buttonId);
    const empresaSelect = document.getElementById("export-company");

    const entidade = getEntidadeSelecionada(select?.value || "");
    if (!entidade) {
        if (help) {
            help.textContent = "Selecione uma entidade para visualizar o layout e as regras.";
        }
        if (button) {
            button.disabled = true;
        }
        if (templateButton && mode === "import") {
            templateButton.disabled = true;
        }
        if (empresaSelect && mode === "export") {
            empresaSelect.disabled = true;
        }
        return;
    }

    const colunas = (entidade.colunas || []).map((item) => `${item.nome}${item.obrigatoria ? "*" : ""}`).join(", ");
    const capability = mode === "import" ? entidade.pode_importar : entidade.pode_exportar;

    if (help) {
        if (mode === "import") {
            help.textContent = capability
                ? `Colunas esperadas: ${colunas}. O modelo XLSX ja sai com esse cabecalho pronto.`
                : "Seu perfil nao possui permissao para importar essa entidade.";
        } else {
            help.textContent = capability
                ? `Exportacao de ${entidade.nome}. ${entidade.filtra_empresa ? "Voce pode filtrar por empresa antes de baixar." : "Essa entidade sai consolidada no tenant."}`
                : "Seu perfil nao possui permissao para exportar essa entidade.";
        }
    }

    if (button) {
        button.disabled = !capability;
    }

    if (templateButton && mode === "import") {
        templateButton.disabled = !capability;
    }

    if (mode === "export" && empresaSelect) {
        empresaSelect.disabled = !entidade.filtra_empresa;
        if (!entidade.filtra_empresa) {
            empresaSelect.value = "";
        }
    }
}

function renderEntidadesImportExport() {
    const container = document.getElementById("import-export-entities");
    if (!container) return;

    const entidades = importExportPage.contexto?.entidades || [];
    if (!entidades.length) {
        container.innerHTML = `<p class="text-slate-400">Nenhuma entidade disponivel no momento.</p>`;
        return;
    }

    container.innerHTML = entidades.map((entidade) => {
        const colunas = (entidade.colunas || []).map((item) => item.obrigatoria ? `<strong>${escapeImportExportHtml(item.nome)}</strong>` : escapeImportExportHtml(item.nome)).join(", ");
        return `
            <article class="import-export-entity-card">
                <div class="import-export-entity-head">
                    <div>
                        <h3 class="import-export-entity-title">${escapeImportExportHtml(entidade.nome)}</h3>
                        <p class="import-export-entity-text">${escapeImportExportHtml(entidade.descricao || "")}</p>
                    </div>
                    <div class="import-export-icon import-export-icon-sky">
                        <i data-lucide="${escapeImportExportHtml(entidade.icone || "sheet")}" class="w-4 h-4"></i>
                    </div>
                </div>

                <div class="import-export-entity-columns">
                    <span class="text-slate-500">Colunas:</span> ${colunas || "-"}
                </div>

                <div class="import-export-badges">
                    <span class="import-export-badge ${entidade.pode_importar ? "import-export-badge-ok" : "import-export-badge-muted"}">
                        Importar
                    </span>
                    <span class="import-export-badge ${entidade.pode_exportar ? "import-export-badge-ok" : "import-export-badge-muted"}">
                        Exportar
                    </span>
                    ${entidade.filtra_empresa ? `
                        <span class="import-export-badge import-export-badge-muted">Por empresa</span>
                    ` : ""}
                </div>
            </article>
        `;
    }).join("");

    if (window.lucide) {
        lucide.createIcons();
    }
}

function renderResultadoImportacao(resultado) {
    const container = document.getElementById("import-export-result");
    if (!container) return;

    if (!resultado) {
        container.className = "mt-6 import-export-result-empty";
        container.textContent = "Nenhuma importacao executada nesta sessao.";
        return;
    }

    const erros = Array.isArray(resultado.erros) ? resultado.erros : [];
    container.className = "mt-6 import-export-result-box";
    container.innerHTML = `
        <div>
            <strong class="text-white text-lg">${escapeImportExportHtml(resultado.nome_entidade || "Importacao")}</strong>
            <p class="text-slate-400 mt-2">${resultado.confirmado ? "Lote confirmado integralmente." : `Nenhuma linha gravada. Linhas validas: ${Number(resultado.validas || 0)}.`}</p>
        </div>

        <div class="import-export-result-grid">
            <article class="import-export-result-stat">
                <span>Processadas</span>
                <strong>${Number(resultado.processadas || 0)}</strong>
            </article>
            <article class="import-export-result-stat">
                <span>Sucesso</span>
                <strong>${Number(resultado.sucesso || 0)}</strong>
            </article>
            <article class="import-export-result-stat">
                <span>Criadas</span>
                <strong>${Number(resultado.criadas || 0)}</strong>
            </article>
            <article class="import-export-result-stat">
                <span>Atualizadas</span>
                <strong>${Number(resultado.atualizadas || 0)}</strong>
            </article>
            <article class="import-export-result-stat">
                <span>Falhas</span>
                <strong>${Number(resultado.falhas || 0)}</strong>
            </article>
        </div>

        ${erros.length ? `
            <div class="import-export-error-list">
                ${erros.map((erro) => `
                    <article class="import-export-error-item">
                        <strong class="block text-white">Linha ${Number(erro.linha || 0)}</strong>
                        <p class="mt-2">${escapeImportExportHtml(erro.mensagem || "Falha nao identificada.")}</p>
                    </article>
                `).join("")}
            </div>
        ` : `
            <p class="text-emerald-300 mt-5">Nenhum erro encontrado no lote importado.</p>
        `}
    `;
}

function getEntidadeSelecionada(codigo) {
    return (importExportPage.contexto?.entidades || []).find((item) => item.codigo === codigo) || null;
}

async function downloadImportExportFile(url) {
    const response = await fetch(url, {
        method: "GET",
        credentials: "same-origin",
        headers: getImportExportHeaders(false),
    });

    if (!response.ok) {
        let result;
        try {
            result = await response.json();
        } catch {
            result = { message: "Nao foi possivel gerar o arquivo." };
        }
        throw new Error(result.message || "Erro ao gerar o arquivo.");
    }

    const blob = await response.blob();
    const disposition = response.headers.get("content-disposition") || "";
    const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
    const filename = match?.[1] || "arquivo.xlsx";

    const urlBlob = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = urlBlob;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(urlBlob);
}

function requestImportExportJson(url, options = {}) {
    return fetch(url, {
        credentials: "same-origin",
        ...options,
        headers: {
            ...getImportExportHeaders(false),
            ...(options.headers || {}),
        },
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

function getImportExportHeaders(isJson = false) {
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

function showImportExportMessage(message, type = "success") {
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

    setTimeout(() => div.remove(), 3500);
}

function setImportExportText(id, value) {
    const element = document.getElementById(id);
    if (element) {
        element.textContent = value;
    }
}

function escapeImportExportHtml(value) {
    if (value === null || value === undefined) return "";

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
