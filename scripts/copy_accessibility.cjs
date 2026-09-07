const fs = require('fs');
fs.mkdirSync('tests/vendor', {recursive: true});
fs.copyFileSync('node_modules/axe-core/axe.min.js', 'tests/vendor/axe.min.js');
fs.copyFileSync('node_modules/axe-core/LICENSE', 'tests/vendor/axe.LICENSE');
