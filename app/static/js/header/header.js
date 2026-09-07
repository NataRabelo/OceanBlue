document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("userMenuBtn");
    const dropdown = document.getElementById("userDropdown");
    const backButton = document.querySelector("[data-back-button]");
    const sidebar = document.getElementById("tenantSidebar");
    const sidebarToggleButtons = document.querySelectorAll("[data-sidebar-toggle]");
    const sidebarStateStorageKey = "oceanblue:tenant-sidebar-state";

    function updateSidebarToggleIcons(state) {
        document.querySelectorAll(".sidebar-toggle-expanded").forEach((icon) => {
            icon.classList.toggle("hidden", state !== "expanded");
        });
        document.querySelectorAll(".sidebar-toggle-collapsed").forEach((icon) => {
            icon.classList.toggle("hidden", state !== "collapsed");
        });
    }

    function setSidebarState(state, persist = true) {
        if (!sidebar) return;

        const normalizedState = state === "collapsed" ? "collapsed" : "expanded";
        document.body.classList.add("has-tenant-sidebar");
        document.body.dataset.sidebarState = normalizedState;
        updateSidebarToggleIcons(normalizedState);

        sidebarToggleButtons.forEach((toggleButton) => {
            toggleButton.setAttribute("aria-expanded", String(normalizedState === "expanded"));
            toggleButton.setAttribute(
                "aria-label",
                normalizedState === "expanded" ? "Recolher menu lateral" : "Expandir menu lateral"
            );
        });

        if (persist) {
            window.localStorage.setItem(sidebarStateStorageKey, normalizedState);
            if (window.innerWidth < 768) {
                const target = normalizedState === "expanded"
                    ? sidebar.querySelector(".sidebar-mobile-close")
                    : document.querySelector(".tenant-topbar [data-sidebar-toggle]");
                target?.focus();
            }
        }
    }

    if (btn && dropdown) {
        btn.addEventListener("click", (e) => {
            e.stopPropagation();
            dropdown.classList.toggle("hidden");
        });

        document.addEventListener("click", (e) => {
            if (!dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.classList.add("hidden");
            }
        });
    }

    if (sidebar && sidebarToggleButtons.length) {
        const storedSidebarState = window.localStorage.getItem(sidebarStateStorageKey);
        const defaultSidebarState = window.innerWidth <= 1440 ? "collapsed" : "expanded";
        const initialSidebarState = document.body.dataset.sidebarState || storedSidebarState || defaultSidebarState;
        setSidebarState(initialSidebarState, false);

        sidebarToggleButtons.forEach((toggleButton) => {
            toggleButton.addEventListener("click", () => {
                const nextState = document.body.dataset.sidebarState === "collapsed" ? "expanded" : "collapsed";
                setSidebarState(nextState);
            });
        });
    }

    if (backButton) {
        backButton.addEventListener("click", () => {
            const sameOriginReferrer = document.referrer && document.referrer.startsWith(window.location.origin);

            if (window.history.length > 1 && sameOriginReferrer) {
                window.history.back();
                return;
            }

            window.location.href = "/home";
        });
    }
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && window.innerWidth < 768 && document.body.dataset.sidebarState === "expanded") {
            setSidebarState("collapsed");
        }
    });
});
