const platformState = {
  tenants: [],
  plans: [],
  pagination: {
    currentPage: 1,
    pageSize: 10,
  },
};

const platformElements = {
  tenantGrid: document.getElementById("platformTenantGrid"),
  feedback: document.getElementById("platformFeedback"),
  totalTenants: document.getElementById("platformTotalTenants"),
  totalEmpresas: document.getElementById("platformTotalEmpresas"),
  totalAdmins: document.getElementById("platformTotalAdmins"),
  totalBloqueados: document.getElementById("platformTotalBloqueados"),
  refreshButton: document.getElementById("refreshPlatformBtn"),
  pagination: document.getElementById("platformTenantPagination"),
  overlay: document.getElementById("platformModalOverlay"),
  tenantModal: document.getElementById("tenantModal"),
  companyModal: document.getElementById("companyModal"),
  adminModal: document.getElementById("adminModal"),
  subscriptionModal: document.getElementById("subscriptionModal"),
  companyTenantName: document.getElementById("companyTenantName"),
  companyTenantId: document.getElementById("companyTenantId"),
  adminTenantName: document.getElementById("adminTenantName"),
  adminTenantId: document.getElementById("adminTenantId"),
  subscriptionTenantName: document.getElementById("subscriptionTenantName"),
  subscriptionTenantId: document.getElementById("subscriptionTenantId"),
  subscriptionPlano: document.getElementById("subscriptionPlano"),
  subscriptionStatus: document.getElementById("subscriptionStatus"),
  subscriptionTrialAte: document.getElementById("subscriptionTrialAte"),
  subscriptionLimiteEmpresas: document.getElementById("subscriptionLimiteEmpresas"),
  subscriptionLimiteFuncionarios: document.getElementById("subscriptionLimiteFuncionarios"),
  subscriptionLimiteProdutos: document.getElementById("subscriptionLimiteProdutos"),
  subscriptionLimiteVendasMes: document.getElementById("subscriptionLimiteVendasMes"),
  subscriptionCurrentState: document.getElementById("subscriptionCurrentState"),
  adminEmpresaId: document.getElementById("adminEmpresaId"),
  tenantForm: document.getElementById("tenantForm"),
  companyForm: document.getElementById("companyForm"),
  adminForm: document.getElementById("adminForm"),
  subscriptionForm: document.getElementById("subscriptionForm"),
  openTenantModalBtn: document.getElementById("openTenantModalBtn"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatPlatformCpf(value) {
  return window.InputMask?.formatCpf(value) || String(value ?? "");
}

function formatPlatformCnpj(value) {
  return window.InputMask?.formatCnpj(value) || String(value ?? "");
}

function showFeedback(message, type = "info") {
  if (!platformElements.feedback) {
    return;
  }

  platformElements.feedback.textContent = message;
  platformElements.feedback.className = `platform-feedback platform-feedback-${type}`;
  platformElements.feedback.classList.remove("hidden");
}

function clearFeedback() {
  if (!platformElements.feedback) {
    return;
  }

  platformElements.feedback.textContent = "";
  platformElements.feedback.className = "platform-feedback hidden";
}

async function requestJson(url, options = {}) {
  const config = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  };

  const response = await fetch(url, config);
  const payload = await response.json().catch(() => ({}));

  if (!response.ok || payload.success === false) {
    throw new Error(payload.message || "Nao foi possivel concluir a operacao.");
  }

  return payload;
}

function formatDate(value) {
  if (!value) {
    return "Sem data";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Sem data";
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(date);
}

function countTotals() {
  const totals = platformState.tenants.reduce((accumulator, tenant) => {
    accumulator.empresas += tenant.empresas.length;
    accumulator.admins += tenant.admins.length;
    accumulator.bloqueados += tenant.assinatura?.bloqueado ? 1 : 0;
    return accumulator;
  }, { empresas: 0, admins: 0, bloqueados: 0 });

  if (platformElements.totalTenants) {
    platformElements.totalTenants.textContent = String(platformState.tenants.length);
  }
  if (platformElements.totalEmpresas) {
    platformElements.totalEmpresas.textContent = String(totals.empresas);
  }
  if (platformElements.totalAdmins) {
    platformElements.totalAdmins.textContent = String(totals.admins);
  }
  if (platformElements.totalBloqueados) {
    platformElements.totalBloqueados.textContent = String(totals.bloqueados);
  }
}

function renderTenantGrid() {
  if (!platformElements.tenantGrid) {
    return;
  }

  if (!platformState.tenants.length) {
    platformElements.tenantGrid.innerHTML = `
      <article class="platform-empty-state">
        <h4 class="text-xl font-semibold text-white mb-3">Nenhum tenant provisionado ainda</h4>
        <p>Use o botao "Novo tenant" para iniciar a estrutura multi-tenant da plataforma.</p>
      </article>
    `;
    renderTenantPagination();
    lucide.createIcons();
    return;
  }

  const tenants = getPaginatedTenants();

  platformElements.tenantGrid.innerHTML = tenants.map((tenant) => {
    const empresasHtml = tenant.empresas.length
      ? tenant.empresas.map((empresa) => `
          <li class="platform-list-item">
            <div>
              <strong class="platform-list-title">${escapeHtml(empresa.nome_fantasia)}</strong>
              <span class="platform-list-subtitle">${escapeHtml(empresa.razao_social)}</span>
              <div class="platform-company-visual-row">
                <span class="platform-company-visual-badge ${empresa.visual_modo === "LEGADO" ? "is-classic" : "is-modern"}">
                  ${empresa.visual_modo === "LEGADO" ? "Visual legado" : "Visual atual"}
                </span>
                <button
                  type="button"
                  class="platform-inline-btn platform-inline-btn-compact"
                  data-action="toggle-visual-mode"
                  data-tenant-id="${tenant.id}"
                  data-empresa-id="${empresa.id}"
                  data-next-mode="${empresa.visual_modo === "LEGADO" ? "MODERNO" : "LEGADO"}"
                >
                  <i data-lucide="${empresa.visual_modo === "LEGADO" ? "sparkles" : "clock-3"}"></i>
                  ${empresa.visual_modo === "LEGADO" ? "Usar visual atual" : "Usar visual legado"}
                </button>
              </div>
            </div>
            <div class="text-right">
              <strong class="platform-list-title">${escapeHtml(empresa.tipo_empresa)}</strong>
              <span class="platform-list-subtitle">${escapeHtml(formatPlatformCnpj(empresa.cnpj))}</span>
            </div>
          </li>
        `).join("")
      : `
          <li class="platform-list-item">
            <div>
              <strong class="platform-list-title">Sem empresas</strong>
              <span class="platform-list-subtitle">Cadastre a primeira empresa deste tenant.</span>
            </div>
          </li>
        `;

    const adminsHtml = tenant.admins.length
      ? tenant.admins.map((admin) => `
          <li class="platform-list-item">
            <div>
              <strong class="platform-list-title">${escapeHtml(admin.nome)}</strong>
              <span class="platform-list-subtitle">@${escapeHtml(admin.usuario)}</span>
            </div>
            <div class="text-right">
              <strong class="platform-list-title">${admin.ativo ? "Ativo" : "Inativo"}</strong>
              <span class="platform-list-subtitle">${escapeHtml(formatPlatformCpf(admin.cpf))}</span>
            </div>
          </li>
        `).join("")
      : `
          <li class="platform-list-item">
            <div>
              <strong class="platform-list-title">Sem admins adicionais</strong>
              <span class="platform-list-subtitle">Crie novos acessos administrativos quando precisar.</span>
            </div>
          </li>
        `;

    return `
      <article class="platform-tenant-card">
        <div class="platform-tenant-card-header">
          <div>
            <span class="platform-chip">Tenant #${tenant.id}</span>
            <h4 class="platform-tenant-name">${escapeHtml(tenant.nome)}</h4>
            <p class="platform-tenant-meta">Provisionado em ${formatDate(tenant.criado_em)}</p>
          </div>
          <button type="button" class="platform-inline-btn" data-action="open-company-modal" data-tenant-id="${tenant.id}">
            <i data-lucide="building"></i>
            Nova empresa
          </button>
        </div>

        <div class="platform-tenant-badges">
          <span class="platform-badge"><i data-lucide="briefcase-business"></i>${tenant.quantidade_empresas} empresas</span>
          <span class="platform-badge"><i data-lucide="shield-check"></i>${tenant.quantidade_admins} admins</span>
          <span class="platform-badge ${tenant.assinatura?.bloqueado ? "is-blocked" : "is-active"}">
            <i data-lucide="${tenant.assinatura?.bloqueado ? "lock" : "badge-check"}"></i>
            ${escapeHtml(formatSubscriptionStatus(tenant.assinatura_status))}
          </span>
          <span class="platform-badge"><i data-lucide="credit-card"></i>${escapeHtml(tenant.plano?.nome || tenant.assinatura?.plano_nome || "-")}</span>
        </div>

        <div class="platform-subscription-summary ${tenant.assinatura?.bloqueado ? "is-blocked" : ""}">
          <strong>${tenant.assinatura?.bloqueado ? "Acesso bloqueado" : "Acesso liberado"}</strong>
          <span>${escapeHtml(getSubscriptionSummary(tenant))}</span>
        </div>

        <div class="platform-list-block">
          <div class="platform-list-head">
            <strong>Empresas</strong>
          </div>
          <ul class="platform-list">${empresasHtml}</ul>
        </div>

        <div class="platform-list-block">
          <div class="platform-list-head">
            <strong>Admins</strong>
          </div>
          <ul class="platform-list">${adminsHtml}</ul>
        </div>

        <div class="platform-tenant-card-footer">
          <span class="platform-inline-meta">Tenant pronto para estoque, PDV e financeiro.</span>
          <div class="platform-inline-actions">
            <button type="button" class="platform-inline-btn" data-action="open-subscription-modal" data-tenant-id="${tenant.id}">
              <i data-lucide="credit-card"></i>
              Assinatura
            </button>
            <button type="button" class="platform-inline-btn" data-action="open-admin-modal" data-tenant-id="${tenant.id}">
              <i data-lucide="user-plus"></i>
              Novo admin
            </button>
          </div>
        </div>
      </article>
    `;
  }).join("");

  renderTenantPagination();
  lucide.createIcons();
}

function getTotalTenantPages() {
  const pageSize = Math.max(Number(platformState.pagination.pageSize) || 10, 1);
  return Math.max(Math.ceil(platformState.tenants.length / pageSize), 1);
}

function getPaginatedTenants() {
  const pageSize = Math.max(Number(platformState.pagination.pageSize) || 10, 1);
  const totalPages = getTotalTenantPages();

  if (platformState.pagination.currentPage > totalPages) {
    platformState.pagination.currentPage = totalPages;
  }

  const start = (platformState.pagination.currentPage - 1) * pageSize;
  return platformState.tenants.slice(start, start + pageSize);
}

function buildPageNumbers(currentPage, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  if (currentPage <= 4) {
    return [1, 2, 3, 4, 5, "...", totalPages];
  }

  if (currentPage >= totalPages - 3) {
    return [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
  }

  return [1, "...", currentPage - 1, currentPage, currentPage + 1, "...", totalPages];
}

function renderTenantPagination() {
  if (!platformElements.pagination) {
    return;
  }

  const totalItems = platformState.tenants.length;
  const totalPages = getTotalTenantPages();
  const currentPage = platformState.pagination.currentPage;
  const pageSize = Math.max(Number(platformState.pagination.pageSize) || 10, 1);

  if (!totalItems) {
    platformElements.pagination.innerHTML = "";
    return;
  }

  if (totalPages <= 1) {
    platformElements.pagination.innerHTML = `
      <div class="pagination-shell pagination-shell-single">
        <div class="pagination-summary">Exibindo ${totalItems} tenant(s).</div>
      </div>
    `;
    return;
  }

  const start = ((currentPage - 1) * pageSize) + 1;
  const end = Math.min(currentPage * pageSize, totalItems);
  const pages = buildPageNumbers(currentPage, totalPages);

  platformElements.pagination.innerHTML = `
    <div class="pagination-shell">
      <div class="pagination-summary">Exibindo ${start}-${end} de ${totalItems} tenants</div>
      <div class="pagination-controls">
        <button type="button" class="pagination-btn" data-platform-page="${currentPage - 1}" ${currentPage === 1 ? "disabled" : ""}>
          Anterior
        </button>
        ${pages.map((page) => page === "..."
          ? `<span class="pagination-ellipsis">...</span>`
          : `<button type="button" class="pagination-btn ${page === currentPage ? "pagination-btn-active" : ""}" data-platform-page="${page}">${page}</button>`
        ).join("")}
        <button type="button" class="pagination-btn" data-platform-page="${currentPage + 1}" ${currentPage === totalPages ? "disabled" : ""}>
          Proxima
        </button>
      </div>
    </div>
  `;

  platformElements.pagination.querySelectorAll("[data-platform-page]").forEach((button) => {
    button.addEventListener("click", () => {
      const page = Number(button.getAttribute("data-platform-page"));
      if (!Number.isInteger(page)) {
        return;
      }

      platformState.pagination.currentPage = Math.min(Math.max(page, 1), totalPages);
      renderTenantGrid();
    });
  });
}

function getTenantById(tenantId) {
  return platformState.tenants.find((tenant) => tenant.id === Number(tenantId)) || null;
}

function openModal(modalElement) {
  if (!modalElement || !platformElements.overlay) {
    return;
  }

  clearFeedback();
  platformElements.overlay.classList.remove("hidden");
  modalElement.classList.remove("hidden");
  modalElement.setAttribute("aria-hidden", "false");
  lucide.createIcons();
}

function closeModals() {
  [platformElements.tenantModal, platformElements.companyModal, platformElements.adminModal, platformElements.subscriptionModal].forEach((modal) => {
    if (!modal) {
      return;
    }

    modal.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
  });

  if (platformElements.overlay) {
    platformElements.overlay.classList.add("hidden");
  }

  if (platformElements.tenantForm) {
    platformElements.tenantForm.reset();
  }
  if (platformElements.companyForm) {
    platformElements.companyForm.reset();
  }
  if (platformElements.adminForm) {
    platformElements.adminForm.reset();
  }
  if (platformElements.subscriptionForm) {
    platformElements.subscriptionForm.reset();
  }
}

function prepareCompanyModal(tenantId) {
  const tenant = getTenantById(tenantId);
  if (!tenant) {
    showFeedback("Tenant nao encontrado para cadastrar a empresa.", "error");
    return;
  }

  if (platformElements.companyTenantName) {
    platformElements.companyTenantName.textContent = tenant.nome;
  }
  if (platformElements.companyTenantId) {
    platformElements.companyTenantId.value = String(tenant.id);
  }

  openModal(platformElements.companyModal);
}

function prepareAdminModal(tenantId) {
  const tenant = getTenantById(tenantId);
  if (!tenant) {
    showFeedback("Tenant nao encontrado para cadastrar o admin.", "error");
    return;
  }

  if (!tenant.empresas.length) {
    showFeedback("Cadastre uma empresa antes de criar admins para esse tenant.", "error");
    return;
  }

  if (platformElements.adminTenantName) {
    platformElements.adminTenantName.textContent = tenant.nome;
  }
  if (platformElements.adminTenantId) {
    platformElements.adminTenantId.value = String(tenant.id);
  }
  if (platformElements.adminEmpresaId) {
      platformElements.adminEmpresaId.innerHTML = tenant.empresas.map((empresa) => `
      <option value="${empresa.id}">${escapeHtml(empresa.nome_fantasia)} - ${escapeHtml(formatPlatformCnpj(empresa.cnpj))}</option>
    `).join("");
  }

  openModal(platformElements.adminModal);
}

function prepareSubscriptionModal(tenantId) {
  const tenant = getTenantById(tenantId);
  if (!tenant) {
    showFeedback("Tenant nao encontrado para controlar assinatura.", "error");
    return;
  }

  fillPlanOptions();
  platformElements.subscriptionTenantName.textContent = tenant.nome;
  platformElements.subscriptionTenantId.value = String(tenant.id);
  platformElements.subscriptionPlano.value = tenant.plano?.codigo || tenant.assinatura?.plano_codigo || "starter";
  platformElements.subscriptionStatus.value = tenant.assinatura_status || "trial";
  platformElements.subscriptionTrialAte.value = tenant.trial_ate || "";
  platformElements.subscriptionLimiteEmpresas.value = tenant.limites?.empresas ?? "";
  platformElements.subscriptionLimiteFuncionarios.value = tenant.limites?.funcionarios ?? "";
  platformElements.subscriptionLimiteProdutos.value = tenant.limites?.produtos ?? "";
  platformElements.subscriptionLimiteVendasMes.value = tenant.limites?.vendas_mes ?? "";
  platformElements.subscriptionCurrentState.innerHTML = `
    <strong>${tenant.assinatura?.bloqueado ? "Bloqueado" : "Liberado"}</strong>
    <span>${escapeHtml(getSubscriptionSummary(tenant))}</span>
  `;
  openModal(platformElements.subscriptionModal);
}

function fillPlanOptions() {
  if (!platformElements.subscriptionPlano) return;
  platformElements.subscriptionPlano.innerHTML = (platformState.plans || []).map((plan) => `
    <option value="${escapeHtml(plan.codigo)}">${escapeHtml(plan.nome)} - R$ ${escapeHtml(plan.preco_mensal)}</option>
  `).join("");
}

function formatSubscriptionStatus(status) {
  return {
    trial: "Trial",
    active: "Ativa",
    past_due: "Inadimplente",
    suspended: "Suspensa",
    canceled: "Cancelada",
  }[status] || status || "-";
}

function getSubscriptionSummary(tenant) {
  const assinatura = tenant.assinatura || {};
  if (assinatura.bloqueado) {
    return assinatura.motivo_bloqueio || "Assinatura bloqueada.";
  }
  if (tenant.assinatura_status === "trial") {
    if (assinatura.dias_trial === null || assinatura.dias_trial === undefined) {
      return "Trial sem data final definida.";
    }
    return assinatura.dias_trial >= 0
      ? `Trial com ${assinatura.dias_trial} dia(s) restante(s).`
      : "Trial expirado.";
  }
  return "Assinatura ativa para uso operacional.";
}

async function loadTenants({ silent = false } = {}) {
  try {
    if (!silent) {
      showFeedback("Atualizando mapa da plataforma...", "info");
    }

    const response = await requestJson("/api/platform/tenants");
    platformState.tenants = response.data || [];
    platformState.pagination.currentPage = Math.min(platformState.pagination.currentPage, getTotalTenantPages());
    countTotals();
    renderTenantGrid();

    if (!silent) {
      showFeedback("Painel atualizado com sucesso.", "success");
      window.setTimeout(() => clearFeedback(), 1800);
    }
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function loadPlans() {
  try {
    const response = await requestJson("/api/platform/planos");
    platformState.plans = response.data || [];
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function handleVisualModeToggle(tenantId, empresaId, visualMode) {
  try {
    showFeedback("Atualizando visual da empresa...", "info");
    await requestJson(`/api/platform/tenants/${tenantId}/empresas/${empresaId}/visual`, {
      method: "PUT",
      body: { visual_modo: visualMode },
    });
    await loadTenants({ silent: true });
    showFeedback("Visual da empresa atualizado com sucesso.", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function handleTenantSubmit(event) {
  event.preventDefault();

  const payload = {
    tenant_nome: document.getElementById("tenantNome").value.trim(),
    empresa: {
      razao_social: document.getElementById("tenantEmpresaRazaoSocial").value.trim(),
      nome_fantasia: document.getElementById("tenantEmpresaNomeFantasia").value.trim(),
      cnpj: document.getElementById("tenantEmpresaCnpj").value.trim(),
      tipo_empresa: document.getElementById("tenantEmpresaTipo").value,
    },
    admin: {
      nome: document.getElementById("tenantAdminNome").value.trim(),
      usuario: document.getElementById("tenantAdminUsuario").value.trim(),
      cpf: document.getElementById("tenantAdminCpf").value.trim(),
      senha: document.getElementById("tenantAdminSenha").value,
    },
  };

  try {
    await requestJson("/api/platform/tenants", { method: "POST", body: payload });
    closeModals();
    await loadTenants({ silent: true });
    showFeedback("Tenant provisionado com sucesso.", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function handleCompanySubmit(event) {
  event.preventDefault();

  const tenantId = platformElements.companyTenantId?.value;
  const payload = {
    razao_social: document.getElementById("companyRazaoSocial").value.trim(),
    nome_fantasia: document.getElementById("companyNomeFantasia").value.trim(),
    cnpj: document.getElementById("companyCnpj").value.trim(),
    tipo_empresa: document.getElementById("companyTipoEmpresa").value,
  };

  try {
    await requestJson(`/api/platform/tenants/${tenantId}/empresas`, { method: "POST", body: payload });
    closeModals();
    await loadTenants({ silent: true });
    showFeedback("Empresa cadastrada com sucesso.", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function handleAdminSubmit(event) {
  event.preventDefault();

  const tenantId = platformElements.adminTenantId?.value;
  const payload = {
    empresa_id: platformElements.adminEmpresaId?.value,
    nome: document.getElementById("adminNome").value.trim(),
    usuario: document.getElementById("adminUsuario").value.trim(),
    cpf: document.getElementById("adminCpf").value.trim(),
    senha: document.getElementById("adminSenha").value,
  };

  try {
    await requestJson(`/api/platform/tenants/${tenantId}/admins`, { method: "POST", body: payload });
    closeModals();
    await loadTenants({ silent: true });
    showFeedback("Admin cadastrado com sucesso.", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

async function handleSubscriptionSubmit(event) {
  event.preventDefault();

  const tenantId = platformElements.subscriptionTenantId?.value;
  const payload = {
    plano_codigo: platformElements.subscriptionPlano?.value,
    assinatura_status: platformElements.subscriptionStatus?.value,
    trial_ate: platformElements.subscriptionTrialAte?.value || "",
    limite_empresas: platformElements.subscriptionLimiteEmpresas?.value,
    limite_funcionarios: platformElements.subscriptionLimiteFuncionarios?.value,
    limite_produtos: platformElements.subscriptionLimiteProdutos?.value,
    limite_vendas_mes: platformElements.subscriptionLimiteVendasMes?.value,
  };

  try {
    await requestJson(`/api/platform/tenants/${tenantId}/assinatura`, { method: "PUT", body: payload });
    closeModals();
    await loadTenants({ silent: true });
    showFeedback("Assinatura atualizada. O bloqueio dos modulos ja passa a obedecer este controle.", "success");
  } catch (error) {
    showFeedback(error.message, "error");
  }
}

function bindEvents() {
  platformElements.openTenantModalBtn?.addEventListener("click", () => openModal(platformElements.tenantModal));
  platformElements.refreshButton?.addEventListener("click", () => loadTenants());
  platformElements.tenantForm?.addEventListener("submit", handleTenantSubmit);
  platformElements.companyForm?.addEventListener("submit", handleCompanySubmit);
  platformElements.adminForm?.addEventListener("submit", handleAdminSubmit);
  platformElements.subscriptionForm?.addEventListener("submit", handleSubscriptionSubmit);
  platformElements.overlay?.addEventListener("click", closeModals);

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", closeModals);
  });

  document.addEventListener("click", (event) => {
    const actionElement = event.target.closest("[data-action]");
    if (!actionElement) {
      return;
    }

    const tenantId = Number(actionElement.dataset.tenantId);
    const action = actionElement.dataset.action;

    if (action === "open-company-modal") {
      prepareCompanyModal(tenantId);
    }

    if (action === "open-admin-modal") {
      prepareAdminModal(tenantId);
    }

    if (action === "open-subscription-modal") {
      prepareSubscriptionModal(tenantId);
    }

    if (action === "toggle-visual-mode") {
      const empresaId = Number(actionElement.dataset.empresaId);
      const nextMode = actionElement.dataset.nextMode || "MODERNO";
      handleVisualModeToggle(tenantId, empresaId, nextMode);
    }
  });
}

bindEvents();
loadPlans().then(() => loadTenants());
