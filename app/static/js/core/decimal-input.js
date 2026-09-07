(function initDecimalInputToolkit(global) {
    function parseDecimal(value) {
        const raw = String(value ?? "").trim();
        if (!raw) return 0;

        const sanitized = raw.replace(/[^\d,.\-]/g, "");
        if (!sanitized) return 0;

        const negative = sanitized.startsWith("-");
        const unsigned = sanitized.replace(/-/g, "");
        const lastComma = unsigned.lastIndexOf(",");
        const lastDot = unsigned.lastIndexOf(".");
        const separatorIndex = Math.max(lastComma, lastDot);

        let integerDigits = unsigned;
        let decimalDigits = "";

        if (separatorIndex >= 0) {
            integerDigits = unsigned.slice(0, separatorIndex);
            decimalDigits = unsigned.slice(separatorIndex + 1);
        }

        integerDigits = integerDigits.replace(/\D/g, "");
        decimalDigits = decimalDigits.replace(/\D/g, "");

        if (!integerDigits && !decimalDigits) {
            return 0;
        }

        const normalized = `${negative ? "-" : ""}${integerDigits || "0"}${decimalDigits ? `.${decimalDigits}` : ""}`;
        const parsed = Number(normalized);
        return Number.isNaN(parsed) ? 0 : parsed;
    }

    function sanitizeDecimal(value, decimals = 2, options = {}) {
        const { allowEmpty = false, allowNegative = false } = options;
        const raw = String(value ?? "");

        if (!raw.trim()) {
            return allowEmpty ? "" : "";
        }

        const trimmed = raw.trim();
        const negative = allowNegative && trimmed.startsWith("-");
        const unsigned = trimmed.replace(/-/g, "");
        const hasComma = unsigned.includes(",");
        const hasDot = unsigned.includes(".");
        const lastComma = unsigned.lastIndexOf(",");
        const lastDot = unsigned.lastIndexOf(".");
        const separatorIndex = Math.max(lastComma, lastDot);

        let integerDigits = unsigned;
        let decimalDigits = "";
        let useDecimalSeparator = separatorIndex >= 0;

        if (separatorIndex >= 0) {
            integerDigits = unsigned.slice(0, separatorIndex);
            decimalDigits = unsigned.slice(separatorIndex + 1);
        }

        integerDigits = integerDigits.replace(/\D/g, "");
        decimalDigits = decimalDigits.replace(/\D/g, "").slice(0, Math.max(decimals, 0));

        const dotOnlyWithLongFraction = decimals > 0
            && !hasComma
            && hasDot
            && separatorIndex >= 0
            && unsigned.slice(separatorIndex + 1).replace(/\D/g, "").length > decimals;

        if (dotOnlyWithLongFraction) {
            integerDigits = unsigned.replace(/\D/g, "");
            decimalDigits = "";
            useDecimalSeparator = false;
        }

        if (!integerDigits && !decimalDigits) {
            return allowEmpty ? "" : "";
        }

        integerDigits = integerDigits.replace(/^0+(?=\d)/, "");
        if (!integerDigits && (decimalDigits || useDecimalSeparator)) {
            integerDigits = "0";
        }

        let normalized = `${negative ? "-" : ""}${integerDigits}`;

        if (useDecimalSeparator && decimals > 0) {
            normalized += `,${decimalDigits}`;
        }

        return normalized;
    }

    function formatDecimal(value, decimals = 2, options = {}) {
        const { allowEmpty = false, useGrouping = true } = options;
        const raw = String(value ?? "").trim();

        if (!raw) {
            return allowEmpty ? "" : new Intl.NumberFormat("pt-BR", {
                useGrouping,
                minimumFractionDigits: decimals,
                maximumFractionDigits: decimals
            }).format(0);
        }

        return new Intl.NumberFormat("pt-BR", {
            useGrouping,
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        }).format(parseDecimal(raw));
    }

    function normalizeDecimal(value, decimals = 2) {
        return parseDecimal(value).toFixed(decimals);
    }

    function bindDecimalInput(input, options = {}) {
        if (!input || input.dataset.decimalInputBound === "true") return;

        const {
            decimals = 2,
            allowEmpty = false,
            allowNegative = false,
            selectAllOnFocus = true,
            onInput = null,
            onBlur = null
        } = options;

        input.dataset.decimalInputBound = "true";
        input.setAttribute("inputmode", decimals > 0 ? "decimal" : "numeric");

        const currentValue = String(input.value ?? "").trim();
        if (currentValue) {
            input.value = formatDecimal(currentValue, decimals, { allowEmpty, useGrouping: true });
        } else if (!allowEmpty) {
            input.value = formatDecimal(0, decimals, { allowEmpty: false, useGrouping: true });
        }

        input.addEventListener("focus", () => {
            if (String(input.value ?? "").trim()) {
                input.value = formatDecimal(input.value, decimals, { allowEmpty, useGrouping: false });
            }

            if (selectAllOnFocus) {
                requestAnimationFrame(() => {
                    if (document.activeElement !== input) return;
                    try {
                        input.select();
                    } catch {
                        // Ignora erros de selecao em navegadores que nao suportam select neste momento.
                    }
                });
            }
        });

        input.addEventListener("input", () => {
            input.value = sanitizeDecimal(input.value, decimals, { allowEmpty, allowNegative });
            if (typeof onInput === "function") {
                onInput(input);
            }
        });

        input.addEventListener("blur", () => {
            const raw = String(input.value ?? "").trim();

            if (!raw) {
                input.value = allowEmpty ? "" : formatDecimal(0, decimals, { allowEmpty: false, useGrouping: true });
            } else {
                input.value = formatDecimal(raw, decimals, { allowEmpty, useGrouping: true });
            }

            if (typeof onBlur === "function") {
                onBlur(input);
            }
        });
    }

    global.DecimalInput = {
        bind: bindDecimalInput,
        parse: parseDecimal,
        sanitize: sanitizeDecimal,
        format: formatDecimal,
        normalize: normalizeDecimal
    };
})(window);
