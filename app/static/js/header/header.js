document.addEventListener("DOMContentLoaded", () => {
    const btn = document.getElementById("userMenuBtn");
    const dropdown = document.getElementById("userDropdown");
    const backButton = document.querySelector("[data-back-button]");
    const sidebar = document.getElementById("tenantSidebar");
    const sidebarToggleButtons = document.querySelectorAll("[data-sidebar-toggle]");
    const sidebarStateStorageKey = "oceanblue:tenant-sidebar-state";
    const mobileViewport = window.matchMedia("(max-width: 767px)");
    const sidebarOpener = document.querySelector(".tenant-topbar [data-sidebar-toggle]");
    const skipLink = document.querySelector(".skip-link");
    const mainContent = document.querySelector("main");
    let lastFocusedElement = document.activeElement;

    if (skipLink && mainContent) {
        mainContent.id ||= "main-content";
        mainContent.setAttribute("tabindex", "-1");
        skipLink.setAttribute("href", `#${mainContent.id}`);
    }

    document.addEventListener("focusin", (event) => {
        lastFocusedElement = event.target;
    });

    function setUserMenuState(expanded, restoreFocus = false) {
        if (!btn || !dropdown) return;
        dropdown.classList.toggle("hidden", !expanded);
        btn.setAttribute("aria-expanded", String(expanded));
        if (!expanded && (restoreFocus || dropdown.contains(document.activeElement))) {
            btn.focus();
        }
    }

    function updateSidebarFocus() {
        if (!sidebar) return;
        const focusedElement = document.activeElement === document.body ? lastFocusedElement : document.activeElement;
        if (mobileViewport.matches && document.body.dataset.sidebarState === "expanded") {
            setUserMenuState(false);
            sidebar.querySelector(".sidebar-mobile-close")?.focus();
        } else if (sidebar.contains(focusedElement)
            && (mobileViewport.matches || focusedElement.matches(".sidebar-mobile-close"))) {
            sidebarOpener?.focus();
        }
    }

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
            toggleButton.setAttribute("aria-controls", sidebar.id);
            toggleButton.setAttribute("aria-expanded", String(normalizedState === "expanded"));
            toggleButton.setAttribute(
                "aria-label",
                normalizedState === "expanded" ? "Recolher menu lateral" : "Expandir menu lateral"
            );
        });

        if (persist) {
            window.localStorage.setItem(sidebarStateStorageKey, normalizedState);
            if (mobileViewport.matches && normalizedState === "collapsed") {
                sidebarOpener?.focus();
            }
        }
        updateSidebarFocus();
    }

    if (btn && dropdown) {
        btn.setAttribute("aria-controls", dropdown.id);
        setUserMenuState(!dropdown.classList.contains("hidden"));
        btn.addEventListener("click", (event) => {
            event.stopPropagation();
            setUserMenuState(dropdown.classList.contains("hidden"));
        });

        document.addEventListener("click", (event) => {
            if (!dropdown.contains(event.target) && !btn.contains(event.target)) {
                setUserMenuState(false);
            }
        });
        document.addEventListener("focusin", (event) => {
            if (!dropdown.contains(event.target) && !btn.contains(event.target)) {
                setUserMenuState(false);
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
        mobileViewport.addEventListener("change", updateSidebarFocus);
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
        if (event.key === "Escape" && dropdown && !dropdown.classList.contains("hidden")) {
            event.preventDefault();
            setUserMenuState(false, true);
            return;
        }
        if (!sidebar || !mobileViewport.matches || document.body.dataset.sidebarState !== "expanded") return;
        if (event.key === "Escape") {
            event.preventDefault();
            setSidebarState("collapsed");
        } else if (event.key === "Tab") {
            const focusable = Array.from(sidebar.querySelectorAll(
                'a[href], button, input, select, textarea, [tabindex]'
            )).filter((element) => !element.disabled && element.tabIndex >= 0 && element.getClientRects().length);
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && (document.activeElement === first || !sidebar.contains(document.activeElement))) {
                event.preventDefault();
                last?.focus();
            } else if (!event.shiftKey && (document.activeElement === last || !sidebar.contains(document.activeElement))) {
                event.preventDefault();
                first?.focus();
            }
        }
    });
});
