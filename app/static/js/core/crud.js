window.CrudPage = class CrudPage {
    constructor(config) {
        this.config = {
            apiBaseUrl: "",
            tableBodyId: "",
            formCreateId: "",
            formEditId: "",
            formDeleteId: "",
            modalCreateId: "",
            modalEditId: "",
            modalDeleteId: "",
            searchInputId: "",
            fields: [],
            pageSize: 10,
            paginationContainerId: "",
            renderRow: null,
            mapItemToEditForm: null,
            beforeOpenCreateModal: null,
            beforeOpenEditModal: null,
            beforeSubmitCreate: null,
            beforeSubmitEdit: null,
            messages: {
                loadError: "Erro ao carregar registros.",
                createSuccess: "Registro criado com sucesso.",
                createError: "Erro ao criar registro.",
                updateSuccess: "Registro atualizado com sucesso.",
                updateError: "Erro ao atualizar registro.",
                deleteSuccess: "Registro deletado com sucesso.",
                deleteError: "Erro ao deletar registro."
            },
            ...config
        };

        this.items = [];
        this.filteredItems = [];
        this.currentEditId = null;
        this.currentDeleteId = null;
        this.currentPage = 1;
    }

    init() {
        this.bindCreateForm();
        this.bindEditForm();
        this.bindDeleteForm();
        this.bindSearch();
        this.bindModalClose();
        this.load();
    }

    getToken() {
        return localStorage.getItem("token");
    }

    getHeaders(isJson = true) {
        const headers = {};

        const token = this.getToken();
        if (token) {
            headers["Authorization"] = `Bearer ${token}`;
        }

        if (isJson) {
            headers["Content-Type"] = "application/json";
        }

        return headers;
    }

    async request(url, options = {}) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...options
        });

        let result;
        try {
            result = await response.json();
        } catch {
            result = {
                success: false,
                message: "Resposta inválida do servidor."
            };
        }

        if (!response.ok || result.success === false) {
            throw new Error(result.message || "Erro na requisição.");
        }

        return result;
    }

    async load() {
        try {
            const result = await this.request(this.config.apiBaseUrl, {
                method: "GET",
                headers: this.getHeaders(false)
            });

            this.items = Array.isArray(result.data) ? result.data : [];
            this.currentPage = 1;
            this.renderTable(this.items);
        } catch (error) {
            this.showMessage(error.message || this.config.messages.loadError, "error");
        }
    }

    renderTable(data) {
        const tableBody = document.getElementById(this.config.tableBodyId);
        if (!tableBody) return;

        this.filteredItems = Array.isArray(data) ? data : [];

        const totalPages = this.getTotalPages();
        if (this.currentPage > totalPages) {
            this.currentPage = totalPages;
        }

        const pageItems = this.getPaginatedItems();

        if (!pageItems.length) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="99" class="text-center py-6 text-slate-400">
                        Nenhum registro encontrado.
                    </td>
                </tr>
            `;
            this.renderPagination();
            return;
        }

        tableBody.innerHTML = pageItems.map(item => this.config.renderRow(item, this)).join("");
        this.renderPagination();

        if (window.lucide) {
            lucide.createIcons();
        }
    }

    filter(term) {
        const value = (term || "").toLowerCase().trim();
        const normalizedSearch = this.normalizeSearchValue(value);

        if (!value) {
            this.currentPage = 1;
            this.renderTable(this.items);
            return;
        }

        const filtered = this.items.filter(item => {
            return this.config.fields.some(field => {
                const fieldValue = item[field];
                const rawValue = String(fieldValue || "").toLowerCase();
                const normalizedValue = this.normalizeSearchValue(fieldValue);
                return rawValue.includes(value) || (normalizedSearch && normalizedValue.includes(normalizedSearch));
            });
        });

        this.currentPage = 1;
        this.renderTable(filtered);
    }

    normalizeSearchValue(value) {
        return String(value || "")
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .toLowerCase()
            .replace(/[^a-z0-9]/g, "");
    }

    getTotalPages() {
        const pageSize = Math.max(Number(this.config.pageSize) || 10, 1);
        const totalItems = this.filteredItems.length;
        return Math.max(Math.ceil(totalItems / pageSize), 1);
    }

    getPaginatedItems() {
        const pageSize = Math.max(Number(this.config.pageSize) || 10, 1);
        const start = (this.currentPage - 1) * pageSize;
        const end = start + pageSize;
        return this.filteredItems.slice(start, end);
    }

    renderPagination() {
        const container = document.getElementById(this.config.paginationContainerId);
        if (!container) return;

        const totalItems = this.filteredItems.length;
        const totalPages = this.getTotalPages();
        const pageSize = Math.max(Number(this.config.pageSize) || 10, 1);

        if (!totalItems) {
            container.innerHTML = "";
            return;
        }

        if (totalPages <= 1) {
            container.innerHTML = `
                <div class="pagination-shell pagination-shell-single">
                    <div class="pagination-summary">Exibindo ${totalItems} registro(s).</div>
                </div>
            `;
            return;
        }

        const startItem = ((this.currentPage - 1) * pageSize) + 1;
        const endItem = Math.min(this.currentPage * pageSize, totalItems);
        const pageNumbers = this.buildPageNumbers(totalPages);

        container.innerHTML = `
            <div class="pagination-shell">
                <div class="pagination-summary">Exibindo ${startItem}-${endItem} de ${totalItems} registros</div>
                <div class="pagination-controls">
                    <button type="button" class="pagination-btn" data-page="${this.currentPage - 1}" ${this.currentPage === 1 ? "disabled" : ""}>
                        Anterior
                    </button>
                    ${pageNumbers.map((page) => page === "..."
                        ? `<span class="pagination-ellipsis">...</span>`
                        : `<button type="button" class="pagination-btn ${page === this.currentPage ? "pagination-btn-active" : ""}" data-page="${page}">${page}</button>`
                    ).join("")}
                    <button type="button" class="pagination-btn" data-page="${this.currentPage + 1}" ${this.currentPage === totalPages ? "disabled" : ""}>
                        Próxima
                    </button>
                </div>
            </div>
        `;

        container.querySelectorAll("[data-page]").forEach((button) => {
            button.addEventListener("click", () => {
                const page = Number(button.getAttribute("data-page"));
                if (!Number.isInteger(page)) return;
                this.goToPage(page);
            });
        });
    }

    buildPageNumbers(totalPages) {
        if (totalPages <= 7) {
            return Array.from({ length: totalPages }, (_, index) => index + 1);
        }

        if (this.currentPage <= 4) {
            return [1, 2, 3, 4, 5, "...", totalPages];
        }

        if (this.currentPage >= totalPages - 3) {
            return [1, "...", totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages];
        }

        return [
            1,
            "...",
            this.currentPage - 1,
            this.currentPage,
            this.currentPage + 1,
            "...",
            totalPages
        ];
    }

    goToPage(page) {
        const totalPages = this.getTotalPages();
        this.currentPage = Math.min(Math.max(page, 1), totalPages);
        this.renderTable(this.filteredItems);
    }

    collectFormData(form) {
        const formData = new FormData(form);
        const data = {};

        for (const [key, value] of formData.entries()) {
            data[key] = typeof value === "string" ? value.trim() : value;
        }

        return data;
    }

    clearForm(formId) {
        const form = document.getElementById(formId);
        if (!form) return;

        form.reset();
    }

    fillForm(formId, data) {
        const form = document.getElementById(formId);
        if (!form) return;

        Object.keys(data).forEach(key => {
            const field = form.querySelector(`[name="${key}"]`);
            if (field) {
                if (field.type === "checkbox") {
                    field.checked = Boolean(data[key]);
                    return;
                }
                field.value = data[key] ?? "";
                window.InputMask?.refresh(field);
            }
        });
    }

    bindCreateForm() {
        if (!this.config.formCreateId) return;

        const form = document.getElementById(this.config.formCreateId);
        if (!form) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            try {
                let data = this.collectFormData(form);

                if (typeof this.config.beforeSubmitCreate === "function") {
                    data = await this.config.beforeSubmitCreate(data);
                }

                await this.request(this.config.apiBaseUrl, {
                    method: "POST",
                    headers: this.getHeaders(true),
                    body: JSON.stringify(data)
                });

                this.showMessage(this.config.messages.createSuccess, "success");
                this.closeModal(this.config.modalCreateId);
                this.clearForm(this.config.formCreateId);
                await this.load();
            } catch (error) {
                this.showMessage(error.message || this.config.messages.createError, "error");
            }
        });
    }

    bindEditForm() {
        if (!this.config.formEditId) return;

        const form = document.getElementById(this.config.formEditId);
        if (!form) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            if (!this.currentEditId) {
                this.showMessage("Registro de edição não definido.", "error");
                return;
            }

            try {
                let data = this.collectFormData(form);

                if (typeof this.config.beforeSubmitEdit === "function") {
                    data = await this.config.beforeSubmitEdit(data);
                }

                await this.request(`${this.config.apiBaseUrl}${this.currentEditId}`, {
                    method: "PUT",
                    headers: this.getHeaders(true),
                    body: JSON.stringify(data)
                });

                this.showMessage(this.config.messages.updateSuccess, "success");
                this.closeModal(this.config.modalEditId);
                this.currentEditId = null;
                await this.load();
            } catch (error) {
                this.showMessage(error.message || this.config.messages.updateError, "error");
            }
        });
    }

    bindDeleteForm() {
        if (!this.config.formDeleteId) return;

        const form = document.getElementById(this.config.formDeleteId);
        if (!form) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            if (!this.currentDeleteId) {
                this.showMessage("Registro de exclusão não definido.", "error");
                return;
            }

            try {
                await this.request(`${this.config.apiBaseUrl}${this.currentDeleteId}`, {
                    method: "DELETE",
                    headers: this.getHeaders(false)
                });

                this.showMessage(this.config.messages.deleteSuccess, "success");
                this.closeModal(this.config.modalDeleteId);
                this.currentDeleteId = null;
                await this.load();
            } catch (error) {
                this.showMessage(error.message || this.config.messages.deleteError, "error");
            }
        });
    }

    bindSearch() {
        if (!this.config.searchInputId) return;

        const input = document.getElementById(this.config.searchInputId);
        if (!input) return;

        input.addEventListener("input", () => {
            this.filter(input.value);
        });
    }

    bindModalClose() {
        document.addEventListener("click", (e) => {
            const closeTrigger = e.target.closest("[data-close-modal]");
            if (!closeTrigger) return;

            const modalId = closeTrigger.getAttribute("data-close-modal");
            if (modalId) {
                this.closeModal(modalId);
            }
        });

        window.addEventListener("click", (e) => {
            if (e.target.classList.contains("modal-overlay")) {
                e.target.classList.add("hidden");
            }
        });
    }

    async openCreateModal() {
        this.clearForm(this.config.formCreateId);
        if (typeof this.config.beforeOpenCreateModal === "function") {
            await this.config.beforeOpenCreateModal();
        }

        this.openModal(this.config.modalCreateId);
    }

    async openEditModal(id) {
        const item = this.items.find(x => String(x.id) === String(id));

        if (!item) {
            this.showMessage("Registro não encontrado para edição.", "error");
            return;
        }

        this.currentEditId = id;

        const mappedData = this.config.mapItemToEditForm
            ? this.config.mapItemToEditForm(item)
            : item;

        if (typeof this.config.beforeOpenEditModal === "function") {
            await this.config.beforeOpenEditModal(item);
        }

        this.fillForm(this.config.formEditId, mappedData);
        this.openModal(this.config.modalEditId);
    }

    openDeleteModal(id) {
        this.currentDeleteId = id;
        this.openModal(this.config.modalDeleteId);
    }

    openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.remove("hidden");
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add("hidden");
    }

    showMessage(message, type = "success") {
        const old = document.getElementById("crud-message");

        if (old) {
            old.remove();
        }

        const div = document.createElement("div");
        div.id = "crud-message";
        div.className = `
            fixed top-4 right-4 z-[9999] px-4 py-3 rounded-xl shadow-lg text-sm font-medium
            ${type === "success" ? "bg-emerald-500 text-white" : "bg-red-500 text-white"}
        `;
        div.textContent = message;

        document.body.appendChild(div);

        setTimeout(() => {
            div.remove();
        }, 3000);
    }
};
