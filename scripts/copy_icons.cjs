const { copyFileSync, mkdirSync } = require("node:fs");

mkdirSync("app/static/vendor", { recursive: true });
copyFileSync("node_modules/lucide/dist/umd/lucide.min.js", "app/static/vendor/lucide.min.js");
copyFileSync("node_modules/lucide/LICENSE", "app/static/vendor/lucide.LICENSE");
copyFileSync("node_modules/tailwindcss/LICENSE", "app/static/vendor/tailwind.LICENSE");
